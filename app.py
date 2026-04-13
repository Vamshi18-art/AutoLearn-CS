# app.py — Unified Dashboard
# Combines AutoLearnCS (Instagram/slide generator) + AutoJob Broadcast (Telegram job bot)
# Run:  python app.py

from __future__ import annotations

import json
import os
import queue
import threading
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Generator

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from concurrent.futures import ThreadPoolExecutor
from flask import (
    Flask, Response, jsonify, render_template,
    request, redirect, url_for, flash, stream_with_context
)
from dotenv import load_dotenv

load_dotenv()

# ── App setup ─────────────────────────────────────────────────
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("FLASK_SECRET", "unified_secret_1234")
executor = ThreadPoolExecutor(max_workers=2)

STATIC_POSTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "static", "posts"))
os.makedirs(STATIC_POSTS, exist_ok=True)

# ════════════════════════════════════════════════════════════
# AutoLearnCS helpers (imported lazily to avoid hard crashes)
# ════════════════════════════════════════════════════════════

def _list_generated_posts():
    if not os.path.exists(STATIC_POSTS):
        return []
    posts = []
    for f in os.listdir(STATIC_POSTS):
        if f.lower().endswith(('.png', '.jpg', '.jpeg')):
            base = os.path.splitext(f)[0]
            title = base.replace('_', ' ').title()
            caption = f"Learn {title}! 📚\n\n#DSA #Programming #Coding #LearnToCode"
            posts.append({"filename": f, "title": title, "caption": caption})
    return posts


def parse_custom_content(custom_text: str, topic: str):
    import re
    lines = custom_text.strip().splitlines()
    slides = []
    current_title = topic
    current_content = []
    has_heading = any(line.strip().startswith('#') for line in lines)

    if not has_heading:
        bullets = [f"• {line.strip()}" for line in lines if line.strip()]
        return [{"title": topic, "content": bullets or ["• No content provided"]}]

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#'):
            if current_content:
                slides.append({"title": current_title, "content": current_content})
            current_title = re.sub(r'^#+\s*', '', stripped)
            current_content = []
        elif stripped.startswith(('-', '*')):
            bullet_text = stripped[1:].strip()
            if bullet_text:
                current_content.append(f"• {bullet_text}")
        elif stripped:
            current_content.append(stripped)

    if current_content or current_title:
        slides.append({"title": current_title, "content": current_content or ["• No content provided"]})

    return slides or [{"title": topic, "content": ["• No slides found"]}]


# ════════════════════════════════════════════════════════════
# AutoJob — SSE / pipeline state
# ════════════════════════════════════════════════════════════

_state_lock = threading.Lock()
_state: dict[str, Any] = {
    "status": "idle",
    "pipeline_step": -1,
    "step_counts": ["—", "—", "—", "—", "—"],
    "metrics": {"scraped": 0, "new": 0, "processed": 0, "sent": 0, "failed": 0},
    "progress": 0,
    "progress_label": "Not started",
    "jobs": [],
    "log": [],
    "scheduler_active": False,
    "next_run": None,
    "last_run": None,
    "run_count": 0,
}
_sse_queues: list[queue.Queue] = []
_sse_lock = threading.Lock()
_pipeline_thread: threading.Thread | None = None
_scheduler_thread: threading.Thread | None = None
_stop_flag = threading.Event()
_sched_stop_flag = threading.Event()


def _update_state(**kwargs) -> None:
    with _state_lock:
        _state.update(kwargs)
    _broadcast_sse("state", _get_state_snapshot())


def _get_state_snapshot() -> dict:
    with _state_lock:
        return dict(_state)


def _add_log(msg: str, level: str = "info") -> None:
    entry = {"ts": datetime.now(timezone.utc).strftime("%H:%M:%S"), "level": level, "msg": msg}
    with _state_lock:
        _state["log"].append(entry)
        if len(_state["log"]) > 200:
            _state["log"] = _state["log"][-200:]
    _broadcast_sse("log", entry)


def _broadcast_sse(event: str, data: Any) -> None:
    payload = f"event: {event}\ndata: {json.dumps(data)}\n\n"
    with _sse_lock:
        dead = []
        for q in _sse_queues:
            try:
                q.put_nowait(payload)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _sse_queues.remove(q)


def _set_step(idx: int, state_class: str, count: str = "—") -> None:
    with _state_lock:
        _state["pipeline_step"] = idx
        counts = list(_state["step_counts"])
        counts[idx] = count
        _state["step_counts"] = counts
    _broadcast_sse("pipeline", {"step": idx, "state": state_class, "count": count})


def _cleanup_run(reason: str) -> None:
    _add_log(reason, "warn")
    _update_state(status="idle", progress=0, progress_label=reason)
    _stop_flag.clear()


def _run_pipeline(query: str, location: str, max_jobs: int) -> None:
    global _pipeline_thread
    _add_log("══════ Pipeline started ══════", "info")
    _add_log(f"Query: {query} | Location: {location} | Max: {max_jobs}", "info")
    _update_state(
        status="running", pipeline_step=-1,
        step_counts=["—", "—", "—", "—", "—"],
        metrics={"scraped": 0, "new": 0, "processed": 0, "sent": 0, "failed": 0},
        progress=0, progress_label="Starting…", jobs=[],
    )

    try:
        if _stop_flag.is_set(): _cleanup_run("Stopped by user"); return
        _set_step(0, "running")
        _update_state(progress=5, progress_label="Scraping jobs…")
        _add_log("Scraping jobs from multiple sources…", "info")

        from job_module.scraper import scrape_jobs
        raw_jobs = scrape_jobs(query=query, location=location, max_jobs=max_jobs)
        n_scraped = len(raw_jobs)
        _set_step(0, "done", f"{n_scraped} found")
        with _state_lock: _state["metrics"]["scraped"] = n_scraped
        _broadcast_sse("metrics", _state["metrics"])
        _update_state(progress=20, progress_label=f"Scraped {n_scraped} jobs")
        _add_log(f"Scraped {n_scraped} raw jobs", "ok")

        if not raw_jobs: _cleanup_run("No jobs found"); return

        if _stop_flag.is_set(): _cleanup_run("Stopped by user"); return
        _set_step(1, "running")
        from job_module.deduplicator import filter_new_jobs
        new_jobs = filter_new_jobs(raw_jobs)
        n_new = len(new_jobs)
        _set_step(1, "done", f"{n_new} new")
        with _state_lock: _state["metrics"]["new"] = n_new
        _broadcast_sse("metrics", _state["metrics"])
        _update_state(progress=38, progress_label=f"{n_new} new jobs")
        _add_log(f"{n_scraped - n_new} duplicate(s) removed", "ok")

        if not new_jobs: _cleanup_run("All jobs already sent"); return

        if _stop_flag.is_set(): _cleanup_run("Stopped by user"); return
        _set_step(2, "running")
        _update_state(progress=42, progress_label="Structuring via GPT…")
        from job_module.ai_processor import process_jobs
        structured_jobs = process_jobs(new_jobs)
        n_proc = len(structured_jobs)
        _set_step(2, "done", f"{n_proc} ok")
        with _state_lock:
            _state["metrics"]["processed"] = n_proc
            _state["jobs"] = structured_jobs
        _broadcast_sse("metrics", _state["metrics"])
        _broadcast_sse("jobs", structured_jobs)
        _update_state(progress=65, progress_label=f"AI structured {n_proc} jobs")
        _add_log(f"GPT structured {n_proc}/{n_new} jobs", "ok")

        if not structured_jobs: _cleanup_run("No jobs survived AI processing"); return

        if _stop_flag.is_set(): _cleanup_run("Stopped by user"); return
        _set_step(3, "running")
        from job_module.formatter import format_all_jobs
        messages = format_all_jobs(structured_jobs, query=query)
        n_msgs = len(messages)
        _set_step(3, "done", f"{n_msgs} msgs")
        _broadcast_sse("preview", {"messages": messages})
        _update_state(progress=80, progress_label=f"{n_msgs} messages ready")
        _add_log(f"Formatted {n_msgs} messages", "ok")

        if _stop_flag.is_set(): _cleanup_run("Stopped by user"); return
        _set_step(4, "running")
        _update_state(progress=82, progress_label="Sending to Telegram…")
        from job_module.telegram_sender import send_jobs_to_telegram
        result = send_jobs_to_telegram(messages)
        n_sent = result["sent"]
        n_fail = result["failed"]
        _set_step(4, "done", f"{n_sent} sent")
        with _state_lock:
            _state["metrics"]["sent"] = n_sent
            _state["metrics"]["failed"] = n_fail
            _state["run_count"] += 1
            _state["last_run"] = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
        _broadcast_sse("metrics", _state["metrics"])
        _add_log(f"Sent {n_sent}/{n_msgs} messages to Telegram", "ok")
        _add_log(f"══════ Run complete ══════", "ok")
        _update_state(status="done", progress=100, progress_label=f"Done — {n_sent} messages sent")

    except Exception:
        tb = traceback.format_exc()
        _add_log(f"Pipeline crashed: {tb.splitlines()[-1]}", "err")
        _update_state(status="error", progress_label="Pipeline error — check log")
    finally:
        _stop_flag.clear()
        _pipeline_thread = None


# ════════════════════════════════════════════════════════════
# Main / Dashboard routes
# ════════════════════════════════════════════════════════════

@app.route("/")
def index():
    posts = _list_generated_posts()
    try:
        from modules.topic_tracker import get_all_topics
        topics = get_all_topics()
    except Exception:
        topics = []
    return render_template("index.html", posts=posts, topics=topics)


@app.route("/jobs")
def jobs_dashboard():
    return render_template("jobs.html")


# ════════════════════════════════════════════════════════════
# AutoLearnCS Routes
# ════════════════════════════════════════════════════════════

@app.route("/generate", methods=["POST"])
def generate():
    topic = request.form.get("topic", "").strip()
    if not topic:
        flash("Please enter a topic")
        return redirect(url_for("index"))
    try:
        from modules.slide_dispatcher import dispatch_slides
        from modules.slide_builder import generate_slides_and_save
        from modules.pinterest_agent import fetch_pinterest_images
        from utils.helpers import sanitize_filename
        import shutil

        slides = dispatch_slides(topic)
        topic_obj = {"topic": topic, "id": int(time.time())}
        image_paths = generate_slides_and_save(topic_obj, slides, output_dir=STATIC_POSTS)

        try:
            pinterest_images = fetch_pinterest_images(topic, count=3)
        except Exception:
            pinterest_images = []

        for idx, pint_img in enumerate(pinterest_images):
            try:
                src_path = pint_img.get("path") or ""
                if src_path and os.path.exists(src_path):
                    dest = os.path.join(STATIC_POSTS, f"{sanitize_filename(topic)}_pinterest_{idx+1}.jpg")
                    shutil.copy2(src_path, dest)
            except Exception:
                pass

        flash(f"Generated {len(image_paths)} slides for: {topic}")
    except Exception as e:
        flash(f"Generation failed: {str(e)}")
    return redirect(url_for("index"))


@app.route("/generate_quiz", methods=["POST"])
def generate_quiz():
    topic = request.form.get("topic", "").strip()
    if not topic:
        flash("Please enter a topic"); return redirect(url_for("index"))
    try:
        from modules.generator import generate_quiz_slides
        from modules.slide_builder import generate_slides_and_save
        slides = generate_quiz_slides(topic)
        topic_obj = {"topic": f"Quiz - {topic}", "id": int(time.time())}
        image_paths = generate_slides_and_save(topic_obj, slides, output_dir=STATIC_POSTS)
        flash(f"✅ Generated Weekly Quiz slides for: {topic}")
    except Exception as e:
        flash(f"❌ Quiz generation failed: {str(e)}")
    return redirect(url_for("index"))


@app.route("/generate_guess_output", methods=["POST"])
def generate_guess_output():
    topic = request.form.get("topic", "").strip()
    if not topic:
        flash("Please enter a topic"); return redirect(url_for("index"))
    try:
        from modules.generator import generate_guess_output_slides
        from modules.slide_builder import generate_slides_and_save
        slides = generate_guess_output_slides(topic)
        topic_obj = {"topic": f"Guess Output - {topic}", "id": int(time.time())}
        image_paths = generate_slides_and_save(topic_obj, slides, output_dir=STATIC_POSTS)
        flash(f"✅ Generated Guess the Output slides for: {topic}")
    except Exception as e:
        flash(f"❌ Guess Output generation failed: {str(e)}")
    return redirect(url_for("index"))


@app.route("/generate_logic_puzzle", methods=["POST"])
def generate_logic_puzzle():
    topic = request.form.get("topic", "").strip()
    if not topic:
        flash("Please enter a topic"); return redirect(url_for("index"))
    try:
        from modules.generator import generate_logic_puzzle_slides
        from modules.slide_builder import generate_slides_and_save
        slides = generate_logic_puzzle_slides(topic)
        if not slides:
            flash(f"❌ No slides generated for: {topic}"); return redirect(url_for("index"))
        topic_obj = {"topic": f"Logic Puzzle - {topic}", "id": int(time.time())}
        image_paths = generate_slides_and_save(topic_obj, slides, output_dir=STATIC_POSTS)
        flash(f"✅ Generated {len(image_paths)} Logic & Puzzle slides for: {topic}")
    except Exception as e:
        flash(f"❌ Logic Puzzle generation failed: {str(e)}")
    return redirect(url_for("index"))


@app.route("/generate_custom", methods=["POST"])
def generate_custom():
    topic = request.form.get("topic", "").strip()
    custom_content = request.form.get("custom_content", "").strip()
    if not topic:
        flash("Please enter a topic"); return redirect(url_for("index"))
    if not custom_content:
        flash("Please provide custom content"); return redirect(url_for("index"))
    try:
        from modules.slide_builder import generate_slides_and_save
        slides = parse_custom_content(custom_content, topic)
        if not slides:
            flash("No slides could be generated"); return redirect(url_for("index"))
        topic_obj = {"topic": f"Custom - {topic}", "id": int(time.time())}
        image_paths = generate_slides_and_save(topic_obj, slides, output_dir=STATIC_POSTS)
        flash(f"✅ Generated {len(image_paths)} custom slides for: {topic}")
    except Exception as e:
        flash(f"Custom generation failed: {str(e)}")
    return redirect(url_for("index"))


@app.route("/post_image", methods=["POST"])
def post_image():
    image = request.form.get("image", "")
    caption = request.form.get("caption", "")
    if not image:
        flash("No image selected"); return redirect(url_for("index"))
    image_path = os.path.join(STATIC_POSTS, image)
    if not os.path.exists(image_path):
        flash(f"Image not found: {image}"); return redirect(url_for("index"))
    try:
        from modules.insta_poster import post_single_image
        success = post_single_image(image_path, caption)
        flash(f"✅ Posted to Instagram: {image}" if success else f"❌ Failed to post: {image}")
    except Exception as e:
        flash(f"Error: {str(e)}")
    return redirect(url_for("index"))


@app.route("/post_carousel", methods=["POST"])
def post_carousel():
    images = request.form.getlist("images[]")
    caption = request.form.get("caption", "")
    if not images or len(images) < 2:
        flash("Select at least 2 images for carousel"); return redirect(url_for("index"))
    if len(images) > 10:
        flash("Maximum 10 images allowed"); return redirect(url_for("index"))
    image_paths = [os.path.join(STATIC_POSTS, img) for img in images]
    for path in image_paths:
        if not os.path.exists(path):
            flash(f"Image not found: {os.path.basename(path)}"); return redirect(url_for("index"))
    try:
        from modules.insta_poster import post_carousel_instagram
        success = post_carousel_instagram(image_paths, caption)
        flash(f"✅ Posted carousel with {len(images)} images!" if success else "❌ Carousel posting failed")
    except Exception as e:
        flash(f"Error: {str(e)}")
    return redirect(url_for("index"))


@app.route("/schedule", methods=["POST"])
def schedule_endpoint():
    try:
        howmany = int(request.form.get("howmany", 1))
    except Exception:
        howmany = 1
    try:
        from modules.topic_tracker import pick_next_topics, mark_topic_done, mark_topic_status
        from modules.scheduler import post_topic
        topics = pick_next_topics(howmany)
        if not topics:
            flash("No topics available to schedule"); return redirect(url_for("index"))
        flash(f"Scheduling {len(topics)} topics in background...")

        def background_post():
            for topic_obj in topics:
                try:
                    post_topic(topic_obj)
                    mark_topic_done(topic_obj['topic'])
                except Exception as e:
                    mark_topic_status(topic_obj['topic'], 'failed')

        executor.submit(background_post)
    except Exception as e:
        flash(f"Scheduling failed: {str(e)}")
    return redirect(url_for("index"))


@app.route("/reset", methods=["POST"])
def reset():
    try:
        from modules.topic_tracker import reset_scheduling
        reset_scheduling()
        flash("Reset all topics to pending")
    except Exception as e:
        flash(f"Reset failed: {str(e)}")
    return redirect(url_for("index"))


@app.route("/add_topic", methods=["POST"])
def add_topic_route():
    topic = request.form.get("topic", "").strip()
    category = request.form.get("category", "Other")
    if not topic:
        flash("Please enter a topic name"); return redirect(url_for("index"))
    try:
        from modules.topic_tracker import add_topic
        add_topic(topic, note=category)
        flash(f"✅ Added topic: {topic}")
    except Exception as e:
        flash(f"❌ Failed to add topic: {str(e)}")
    return redirect(url_for("index"))


@app.route("/mark_complete/<topic>", methods=["POST"])
def mark_complete(topic):
    try:
        from modules.topic_tracker import mark_topic_done
        mark_topic_done(topic)
        flash(f"✅ Marked {topic} as complete")
    except Exception as e:
        flash(f"❌ Error: {str(e)}")
    return redirect(url_for("index"))


@app.route("/delete_post/<filename>", methods=["POST"])
def delete_post(filename):
    try:
        path = os.path.join(STATIC_POSTS, filename)
        if os.path.exists(path):
            os.remove(path)
            flash(f"✅ Deleted: {filename}")
        else:
            flash(f"❌ File not found: {filename}")
    except Exception as e:
        flash(f"❌ Delete failed: {str(e)}")
    return redirect(url_for("index"))


@app.route("/api/topics")
def api_topics():
    try:
        from modules.topic_tracker import get_all_topics
        return jsonify(get_all_topics())
    except Exception:
        return jsonify([])


# ════════════════════════════════════════════════════════════
# AutoJob API Routes
# ════════════════════════════════════════════════════════════

@app.route("/stream")
def stream():
    q: queue.Queue = queue.Queue(maxsize=100)
    with _sse_lock:
        _sse_queues.append(q)

    def generate() -> Generator[str, None, None]:
        yield f"event: state\ndata: {json.dumps(_get_state_snapshot())}\n\n"
        try:
            while True:
                try:
                    msg = q.get(timeout=25)
                    yield msg
                except queue.Empty:
                    yield ": ping\n\n"
        except GeneratorExit:
            pass
        finally:
            with _sse_lock:
                if q in _sse_queues:
                    _sse_queues.remove(q)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@app.route("/api/run", methods=["POST"])
def api_run():
    global _pipeline_thread
    if _pipeline_thread and _pipeline_thread.is_alive():
        return jsonify({"error": "Pipeline already running"}), 409
    data = request.get_json(silent=True) or {}
    query    = data.get("query",    os.getenv("SCRAPE_QUERY", "Python developer"))
    location = data.get("location", os.getenv("SCRAPE_LOCATION", "Remote"))
    max_jobs = int(data.get("max_jobs", os.getenv("SCRAPE_MAX_JOBS", 10)))
    experience = data.get("experience", "")

    for key, env_key in [
        ("openai_key", "OPENAI_API_KEY"),
        ("bot_token", "TELEGRAM_BOT_TOKEN"),
        ("chat_id", "TELEGRAM_CHAT_ID"),
    ]:
        if data.get(key):
            os.environ[env_key] = str(data[key])

    # Append experience to query if provided
    if experience:
        query = f"{query} {experience} years experience"

    _stop_flag.clear()
    _pipeline_thread = threading.Thread(
        target=_run_pipeline, args=(query, location, max_jobs), daemon=True
    )
    _pipeline_thread.start()
    return jsonify({"status": "started"})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    _stop_flag.set()
    _add_log("Stop requested", "warn")
    return jsonify({"status": "stopping"})


@app.route("/api/state", methods=["GET"])
def api_state():
    return jsonify(_get_state_snapshot())


@app.route("/api/reset", methods=["POST"])
def api_reset():
    _update_state(
        status="idle", pipeline_step=-1, step_counts=["—"] * 5,
        metrics={"scraped": 0, "new": 0, "processed": 0, "sent": 0, "failed": 0},
        progress=0, progress_label="Reset", jobs=[],
    )
    with _state_lock:
        _state["log"] = []
    _broadcast_sse("log_clear", {})
    _add_log("State reset", "info")
    return jsonify({"status": "reset"})


@app.route("/api/test_telegram", methods=["POST"])
def api_test_telegram():
    data = request.get_json(silent=True) or {}
    if data.get("bot_token"):
        os.environ["TELEGRAM_BOT_TOKEN"] = data["bot_token"]
    if data.get("chat_id"):
        os.environ["TELEGRAM_CHAT_ID"] = data["chat_id"]
    try:
        import importlib, job_module.telegram_sender as ts_mod
        importlib.reload(ts_mod)
        ok = ts_mod.test_connection()
        msg = "Bot connection successful!" if ok else "Bot test failed"
        _add_log(f"Bot test: {msg}", "ok" if ok else "err")
        return jsonify({"ok": ok, "message": msg})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)})


@app.route("/api/scheduler/start", methods=["POST"])
def api_sched_start():
    global _scheduler_thread
    if _state.get("scheduler_active"):
        return jsonify({"error": "Scheduler already running"}), 409
    data = request.get_json(silent=True) or {}
    mode     = data.get("mode", "interval")
    hours    = int(data.get("hours", 6))
    query    = data.get("query", os.getenv("SCRAPE_QUERY", "Python developer"))
    location = data.get("location", os.getenv("SCRAPE_LOCATION", "Remote"))
    max_jobs = int(data.get("max_jobs", 10))
    interval_s = hours * 3600

    _sched_stop_flag.clear()

    def _sched_loop():
        _update_state(scheduler_active=True)
        _add_log(f"Scheduler started — every {hours}h", "ok")
        next_ts = time.time() + interval_s
        _update_state(next_run=datetime.fromtimestamp(next_ts, tz=timezone.utc).strftime("%H:%M UTC"))
        while not _sched_stop_flag.is_set():
            if time.time() >= next_ts:
                _add_log("Scheduled trigger fired", "info")
                _run_pipeline(query, location, max_jobs)
                next_ts = time.time() + interval_s
                _update_state(next_run=datetime.fromtimestamp(next_ts, tz=timezone.utc).strftime("%H:%M UTC"))
            time.sleep(5)
        _update_state(scheduler_active=False, next_run=None, status="idle")
        _add_log("Scheduler stopped", "warn")

    _scheduler_thread = threading.Thread(target=_sched_loop, daemon=True)
    _scheduler_thread.start()
    return jsonify({"status": "scheduler started"})


@app.route("/api/scheduler/stop", methods=["POST"])
def api_sched_stop():
    _sched_stop_flag.set()
    return jsonify({"status": "stopping"})


@app.route("/api/clear_seen", methods=["POST"])
def api_clear_seen():
    seen_file = os.path.join(os.path.dirname(__file__), "job_module", "seen_jobs.json")
    try:
        if os.path.exists(seen_file):
            os.remove(seen_file)
        _add_log("Deduplication history cleared", "ok")
        return jsonify({"ok": True})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)})


# ════════════════════════════════════════════════════════════
# Entry point
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "="*55)
    print("  Unified Dashboard — AutoLearnCS + AutoJob")
    print("  http://127.0.0.1:5000  (AutoLearnCS)")
    print("  http://127.0.0.1:5000/jobs  (AutoJob)")
    print("="*55 + "\n")

    try:
        from modules.topic_tracker import get_all_topics, add_topic
        if not get_all_topics():
            for topic, cat in [
                ("Arrays Basics", "Arrays"), ("Binary Search", "Searching"),
                ("Linked List", "Linked Lists"), ("Stack Implementation", "Stacks"),
            ]:
                add_topic(topic, note=cat)
    except Exception:
        pass

    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)

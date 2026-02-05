# main.py
import os
import time
import traceback
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from concurrent.futures import ThreadPoolExecutor
from utils.logger import logger
from modules.generator import (
    generate_topic_slides,
    generate_quiz_slides,
    generate_guess_output_slides,
    generate_logic_puzzle_slides

    
)
from modules.slide_builder import generate_slides_and_save
from modules.pinterest_agent import fetch_pinterest_images
from modules.insta_poster import post_carousel_instagram, post_single_image
from modules.topic_tracker import (
    pick_next_topics,
    reset_scheduling,
    add_topic,
    get_all_topics,
    mark_topic_done,
    mark_topic_status
)
from modules.scheduler import post_topic
from utils.helpers import ensure_dir, sanitize_filename
from dotenv import load_dotenv

load_dotenv()
import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


# Configuration (keep environment secrets in .env in production)
FLASK_SECRET = os.getenv("FLASK_SECRET", "your_secret_key_1234")
IG_USERNAME = os.getenv("IG_USERNAME", "")
IG_PASSWORD = os.getenv("IG_PASSWORD", "")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN", "")
INSTAGRAM_ID = os.getenv("INSTAGRAM_ID", "")

# Directory setup
STATIC_POSTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "static", "posts"))
ensure_dir(STATIC_POSTS)

app = Flask(__name__)
app.secret_key = FLASK_SECRET
executor = ThreadPoolExecutor(max_workers=2)

def _list_generated_posts():
    """List all generated post images"""
    if not os.path.exists(STATIC_POSTS):
        return []

    files = os.listdir(STATIC_POSTS)
    posts = []
    for f in files:
        if f.lower().endswith(('.png', '.jpg', '.jpeg')):
            base = os.path.splitext(f)[0]
            title = base.replace('_', ' ').title()
            caption = f"Learn {title}! 📚\n\n#DSA #Programming #Coding #LearnToCode"

            posts.append({
                "filename": f,
                "title": title,
                "caption": caption
            })
    return posts

@app.route("/")
def index():
    """Main dashboard"""
    posts = _list_generated_posts()
    topics = get_all_topics()
    return render_template("index.html", posts=posts, topics=topics)

@app.route("/generate", methods=["POST"])
def generate():
    """Generate slides for a single topic"""
    topic = request.form.get("topic", "").strip()
    if not topic:
        flash("Please enter a topic")
        return redirect(url_for("index"))

    try:
        logger.info(f"Generating slides for: {topic}")
        slides = generate_topic_slides(topic)
        topic_obj = {"topic": topic, "id": int(time.time())}
        image_paths = generate_slides_and_save(topic_obj, slides, output_dir=STATIC_POSTS)

        pinterest_images = []
        try:
            pinterest_images = fetch_pinterest_images(topic, count=3)
            if not pinterest_images:
                pinterest_images = [{"type": "local", "path": "", "resolution": "N/A", "source_url": ""}]
        except Exception as e:
            logger.error(f"Image fetch failed (non-fatal): {e}")
            pinterest_images = [{"type": "local", "path": "", "resolution": "N/A", "source_url": ""}]

        import shutil
        for idx, pint_img in enumerate(pinterest_images):
            try:
                src_path = pint_img.get("path") or ""
                if src_path and os.path.exists(src_path):
                    dest = os.path.join(STATIC_POSTS, f"{sanitize_filename(topic)}_pinterest_{idx+1}.jpg")
                    shutil.copy2(src_path, dest)
                    logger.info(f"Copied fetched image to: {dest}")
            except Exception as copy_err:
                logger.warning(f"Failed copying image {pint_img.get('path')}: {copy_err}")

        flash(f"Generated {len(image_paths)} slides + {len(pinterest_images)} images for: {topic}")

    except Exception as e:
        logger.error(f"Generation failed: {e}\n{traceback.format_exc()}")
        flash(f"Generation failed: {str(e)}")

    return redirect(url_for("index"))


# ------------------------ NEW FEATURES ------------------------

@app.route("/generate_quiz", methods=["POST"])
def generate_quiz():
    """Generate a Weekly Quiz carousel"""
    topic = request.form.get("topic", "").strip()
    if not topic:
        flash("Please enter a topic")
        return redirect(url_for("index"))

    try:
        slides = generate_quiz_slides(topic)
        topic_obj = {"topic": f"Quiz - {topic}", "id": int(time.time())}
        image_paths = generate_slides_and_save(topic_obj, slides, output_dir=STATIC_POSTS)
        flash(f"✅ Generated Weekly Quiz slides for: {topic}")
    except Exception as e:
        flash(f"❌ Quiz generation failed: {str(e)}")
    return redirect(url_for("index"))


@app.route("/generate_guess_output", methods=["POST"])
def generate_guess_output():
    """Generate an interactive 'Guess the Output' carousel"""
    topic = request.form.get("topic", "").strip()
    if not topic:
        flash("Please enter a topic")
        return redirect(url_for("index"))

    try:
        slides = generate_guess_output_slides(topic)
        topic_obj = {"topic": f"Guess Output - {topic}", "id": int(time.time())}
        image_paths = generate_slides_and_save(topic_obj, slides, output_dir=STATIC_POSTS)
        flash(f"✅ Generated Guess the Output slides for: {topic}")
    except Exception as e:
        flash(f"❌ Guess Output generation failed: {str(e)}")
    return redirect(url_for("index"))

@app.route("/generate_logic_puzzle", methods=["POST"])
def generate_logic_puzzle():
    """Generate Logic & Puzzle slides"""
    topic = request.form.get("topic", "").strip()
    if not topic:
        flash("Please enter a topic")
        return redirect(url_for("index"))

    try:
        slides = generate_logic_puzzle_slides(topic)
        
        if not slides:
            flash(f"❌ No slides generated for: {topic}. Please try again.")
            return redirect(url_for("index"))
            
        topic_obj = {"topic": f"Logic Puzzle - {topic}", "id": int(time.time())}
        image_paths = generate_slides_and_save(topic_obj, slides, output_dir=STATIC_POSTS)
        
        if image_paths:
            flash(f"✅ Generated {len(image_paths)} Logic & Puzzle slides for: {topic}")
            logger.info(f"✅ Successfully created {len(image_paths)} images in {STATIC_POSTS}")
        else:
            flash(f"❌ Failed to generate images for: {topic}")
            logger.error(f"❌ No images were saved for topic: {topic}")
            
    except Exception as e:
        flash(f"❌ Logic Puzzle generation failed: {str(e)}")
        logger.error(f"❌ Logic Puzzle generation error: {e}")

    return redirect(url_for("index"))



# ---------------------- REMAINING ORIGINAL ROUTES ----------------------

@app.route("/post_image", methods=["POST"])
def post_image():
    """Post single image to Instagram"""
    image = request.form.get("image", "")
    caption = request.form.get("caption", "")

    if not image:
        flash("No image selected")
        return redirect(url_for("index"))

    image_path = os.path.join(STATIC_POSTS, image)
    if not os.path.exists(image_path):
        flash(f"Image not found: {image}")
        return redirect(url_for("index"))

    try:
        if ACCESS_TOKEN and INSTAGRAM_ID:
            success = post_single_image(image_path, caption)
        else:
            from modules.insta_poster import post_local_image
            result = post_local_image(image_path, caption, IG_USERNAME, IG_PASSWORD)
            success = result is not None

        if success:
            flash(f"Posted to Instagram: {image}")
        else:
            flash(f"Failed to post: {image}")
    except Exception as e:
        logger.error(f"Post failed: {e}")
        flash(f"Error: {str(e)}")

    return redirect(url_for("index"))


@app.route("/post_carousel", methods=["POST"])
def post_carousel():
    """Post multiple images as carousel"""
    images = request.form.getlist("images[]")
    caption = request.form.get("caption", "")

    if not images or len(images) < 2:
        flash("Select at least 2 images for carousel")
        return redirect(url_for("index"))

    if len(images) > 10:
        flash("Maximum 10 images allowed")
        return redirect(url_for("index"))

    image_paths = [os.path.join(STATIC_POSTS, img) for img in images]

    for path in image_paths:
        if not os.path.exists(path):
            flash(f"Image not found: {os.path.basename(path)}")
            return redirect(url_for("index"))

    try:
        success = post_carousel_instagram(image_paths, caption)

        if success:
            flash(f"Posted carousel with {len(images)} images!")
        else:
            flash("Carousel posting failed")
    except Exception as e:
        logger.error(f"Carousel post failed: {e}")
        flash(f"Error: {str(e)}")

    return redirect(url_for("index"))


@app.route("/schedule", methods=["POST"])
def schedule_endpoint():
    """Schedule and post topics"""
    try:
        howmany = int(request.form.get("howmany", 1))
    except Exception:
        howmany = 1

    try:
        topics = pick_next_topics(howmany)

        if not topics:
            flash("No topics available to schedule")
            return redirect(url_for("index"))

        flash(f"Scheduling {len(topics)} topics in background...")

        def background_post():
            for topic_obj in topics:
                try:
                    post_topic(topic_obj)
                    mark_topic_done(topic_obj['topic'])
                    logger.info(f"Completed: {topic_obj['topic']}")
                except Exception as e:
                    logger.error(f"Failed to post {topic_obj['topic']}: {e}")
                    mark_topic_status(topic_obj['topic'], 'failed')

        executor.submit(background_post)

    except Exception as e:
        logger.error(f"Scheduling failed: {e}")
        flash(f"Scheduling failed: {str(e)}")

    return redirect(url_for("index"))


@app.route("/reset", methods=["POST"])
def reset():
    """Reset all topic scheduling"""
    try:
        reset_scheduling()
        flash("Reset all topics to pending")
    except Exception as e:
        flash(f"Reset failed: {str(e)}")

    return redirect(url_for("index"))


@app.route("/add_topic", methods=["POST"])
def add_topic_route():
    """Add a new topic"""
    topic = request.form.get("topic", "").strip()
    category = request.form.get("category", "Other")

    if not topic:
        flash("Please enter a topic name")
        return redirect(url_for("index"))

    try:
        add_topic(topic, note=category)
        flash(f"Added topic: {topic}")
    except Exception as e:
        flash(f"Failed to add topic: {str(e)}")

    return redirect(url_for("index"))


@app.route("/mark_complete/<topic>", methods=["POST"])
def mark_complete(topic):
    """Mark a topic as complete"""
    try:
        mark_topic_done(topic)
        flash(f"Marked {topic} as complete")
    except Exception as e:
        flash(f"Error: {str(e)}")

    return redirect(url_for("index"))


@app.route("/delete_post/<filename>", methods=["POST"])
def delete_post(filename):
    """Delete a generated post"""
    try:
        path = os.path.join(STATIC_POSTS, filename)
        if os.path.exists(path):
            os.remove(path)
            flash(f"Deleted: {filename}")
        else:
            flash(f"File not found: {filename}")
    except Exception as e:
        flash(f"Delete failed: {str(e)}")

    return redirect(url_for("index"))


@app.route("/api/topics")
def api_topics():
    """API endpoint to get all topics"""
    topics = get_all_topics()
    return jsonify(topics)


if __name__ == "__main__":
    logger.info("Starting AutoLearnCS Dashboard...")

    try:
        if os.environ.get("WERKZEUG_RUN_MAIN", "true") == "true":
            if not get_all_topics():
                default_topics = [
                    ("Arrays Basics", "Arrays"),
                    ("Binary Search", "Searching"),
                    ("Linked List", "Linked Lists"),
                    ("Stack Implementation", "Stacks"),
                    ("Queue Operations", "Queues"),
                    ("Hash Table", "Hashing"),
                    ("Binary Tree Traversal", "Trees"),
                ]
                for topic, cat in default_topics:
                    add_topic(topic, note=cat)
                logger.info("Initialized default topics")
    except Exception as e:
        logger.warning(f"Could not initialize topics: {e}")

    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
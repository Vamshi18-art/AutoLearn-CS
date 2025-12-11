# modules/scheduler.py
import os
import time
from utils.logger import logger
from modules.topic_tracker import pick_next_topics
from modules.generator import generate_topic_slides
from modules.slide_builder import generate_slides_and_save
from modules.pinterest_agent import fetch_pinterest_images
from modules.insta_poster import post_local_image
from utils.helpers import ensure_dir, sanitize_filename
from dotenv import load_dotenv

load_dotenv()

IG_USERNAME = os.getenv("IG_USERNAME")
IG_PASSWORD = os.getenv("IG_PASSWORD")
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "generated"))
ensure_dir(OUTPUT_DIR)

def post_topic(topic_obj):
    """Post a topic to Instagram with slides and Pinterest images"""
    topic_name = topic_obj['topic']
    logger.info("Preparing topic: %s", topic_name)
    
    # FIX: Ensure topic_obj has an ID
    if 'id' not in topic_obj:
        topic_obj['id'] = int(time.time())
    
    # Generate slides via LLM
    slides = generate_topic_slides(topic_name)
    image_paths = generate_slides_and_save(topic_obj, slides, output_dir=OUTPUT_DIR)
    
    # Fetch Pinterest images (2-3 images)
    pinterest_images = fetch_pinterest_images(topic_name, count=3)
    
    # Copy Pinterest images to output
    for idx, pint_img in enumerate(pinterest_images):
        if pint_img.get("path") and os.path.exists(pint_img["path"]):
            import shutil
            dest = os.path.join(OUTPUT_DIR, f"{sanitize_filename(topic_name)}_pinterest_{idx+1}.jpg")
            shutil.copy2(pint_img["path"], dest)
            image_paths.append(dest)
            logger.info(f"Added Pinterest image: {dest}")
    
    # Post images to Instagram
    captions = [
        f"{topic_name} - Introduction & Overview #DSA #{sanitize_filename(topic_name)}",
        f"{topic_name} - Syntax & Implementation #DSA #{sanitize_filename(topic_name)}",
        f"{topic_name} - Interview Questions #DSA #{sanitize_filename(topic_name)}",
    ]
    
    published = []
    for i, (img, cap) in enumerate(zip(image_paths, captions + ["Visual reference"] * 10)):
        if not os.path.exists(img):
            logger.warning(f"Image not found: {img}")
            continue
        
        try:
            result = post_local_image(img, cap, IG_USERNAME, IG_PASSWORD)
            published.append(result)
            logger.info(f"[OK] Posted image {i+1}/{len(image_paths)}")
            time.sleep(2)  # Rate limiting
        except Exception as e:
            logger.error(f"Failed to post {img}: {e}")
    
    return published

def schedule_daily_posts(posts_per_day=1):
    """Schedule and post daily topics"""
    logger.info("Scheduler started: posts_per_day=%s", posts_per_day)
    topics = pick_next_topics(posts_per_day)
    
    if not topics:
        logger.info("No pending topics to post.")
        return
    
    for t in topics:
        post_topic(t)

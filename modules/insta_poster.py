import os
import time
from PIL import Image
from utils.logger import logger
from dotenv import load_dotenv

load_dotenv()

# Instagrapi credentials (set via environment or defaults)
IG_USERNAME = os.getenv("IG_USERNAME", "")
IG_PASSWORD = os.getenv("IG_PASSWORD", "")

def optimize_image_for_instagram(image_path: str):
    """Optimize image for Instagram HD quality"""
    try:
        img = Image.open(image_path)
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            if img.mode in ('RGBA', 'LA'):
                background.paste(img, mask=img.split()[-1])
            else:
                background.paste(img)
            img = background
        width, height = img.size
        aspect_ratio = width / height

        if aspect_ratio > 1.91:
            target_width, target_height = 1080, 608
        elif aspect_ratio < 0.8:
            target_width, target_height = 1080, 1350
        else:
            target_width = 1080
            target_height = int(1080 / aspect_ratio)

        img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)

        output_path = image_path.replace('.png', '_optimized.jpg')
        if output_path == image_path:
            output_path = image_path.replace('.jpg', '_optimized.jpg')

        img.save(output_path, 'JPEG', quality=95, optimize=True, progressive=True, subsampling=0)

        logger.info(f"✓ Optimized: {output_path} ({target_width}x{target_height})")
        return output_path
    except Exception as e:
        logger.error(f"Optimization failed: {e}")
        return image_path

def _login_instagram_client(username: str, password: str):
    """Helper to login instagrapi Client with session caching"""
    try:
        from instagrapi import Client

        SESSION_FILE = os.path.join(os.path.dirname(__file__), "..", "ig_session.json")
        cl = Client()

        if os.path.exists(SESSION_FILE):
            try:
                cl.load_settings(SESSION_FILE)
                logger.info("Loaded IG session")
            except Exception as e:
                logger.warning(f"Failed to load IG session: {e}")

        try:
            cl.login(username, password)
            logger.info(f"Logged in as {username}")
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return None

        try:
            cl.dump_settings(SESSION_FILE)
        except Exception as e:
            logger.warning(f"Failed to save IG session: {e}")

        return cl
    except ImportError:
        logger.error("instagrapi not installed. Install with: pip install instagrapi")
        return None
    except Exception as e:
        logger.error(f"Instagram client login failed: {e}")
        return None

def post_single_image(image_path: str, caption: str, username: str = None, password: str = None):
    """Post single image to Instagram using instagrapi login"""
    username = username or IG_USERNAME
    password = password or IG_PASSWORD
    cl = _login_instagram_client(username, password)
    if cl is None:
        return False

    optimized = optimize_image_for_instagram(image_path)
    try:
        logger.info(f"Uploading single image: {optimized}")
        res = cl.photo_upload(optimized, caption)
        logger.info("Upload successful")
        if optimized != image_path and os.path.exists(optimized):
            try:
                os.remove(optimized)
            except Exception:
                pass
        return res
    except Exception as e:
        logger.error(f"Single image posting failed: {e}")
        return False

def post_carousel_instagram(image_paths: list, caption: str, username: str = None, password: str = None):
    """Post multiple images as a carousel using instagrapi"""
    username = username or IG_USERNAME
    password = password or IG_PASSWORD

    if not (2 <= len(image_paths) <= 10):
        logger.error("Carousel requires 2 to 10 images")
        return False

    cl = _login_instagram_client(username, password)
    if cl is None:
        return False

    optimized_paths = []
    for img_path in image_paths:
        optimized = optimize_image_for_instagram(img_path)
        optimized_paths.append(optimized)

    try:
        logger.info(f"Uploading carousel with {len(optimized_paths)} images")
        res = cl.album_upload(optimized_paths, caption)
        logger.info("Carousel upload successful")

        for opt_path in optimized_paths:
            if opt_path not in image_paths and os.path.exists(opt_path):
                try:
                    os.remove(opt_path)
                except Exception:
                    pass

        return res
    except Exception as e:
        logger.error(f"Carousel posting failed: {e}")
        return False

# Backward compatible alias
def post_local_image(local_path: str, caption: str, username: str = None, password: str = None):
    """Legacy alias for single image posting"""
    return post_single_image(local_path, caption, username, password)


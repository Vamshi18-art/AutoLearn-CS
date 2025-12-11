import os
import requests
import time
from io import BytesIO
from PIL import Image
from playwright.sync_api import sync_playwright
from utils.logger import logger
from utils.helpers import sanitize_filename, ensure_dir

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "generated")
ensure_dir(OUTPUT_DIR)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"

def download_and_optimize_image(url, topic, index):
    """Download and optimize image to HD quality"""
    try:
        headers = {
            'User-Agent': USER_AGENT,
            'Referer': 'https://www.bing.com/'
        }
        response = requests.get(url, headers=headers, timeout=20, stream=True)
        response.raise_for_status()
        
        img = Image.open(BytesIO(response.content))
        
        # Convert to RGB
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
        
        # Skip small images
        if width < 400 or height < 200:
            logger.debug(f"Image too small: {width}x{height}")
            return None
        
        # Optimize to 1080px width
        target_width = 1080
        aspect_ratio = width / height
        target_height = int(target_width / aspect_ratio)
        
        img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
        
        safe = sanitize_filename(topic)
        output_path = os.path.join(OUTPUT_DIR, f"{safe}_diagram_{index}.jpg")
        img.save(output_path, 'JPEG', quality=94, optimize=True, progressive=True, subsampling=0)
        
        logger.info(f"[OK] Downloaded image {index}: {output_path}")
        return {
            "type": "local",
            "path": output_path,
            "resolution": f"{target_width}x{target_height}",
            "source_url": url
        }
    except Exception as e:
        logger.warning(f"Failed to download image: {e}")
        return None

def fetch_bing_images(topic, count=3):
    """Fetch images from Bing Images using Playwright"""
    images = []
    query = f"{topic} data structure diagram geeksforgeeks"
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled']
            )
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent=USER_AGENT
            )
            page = context.new_page()
            
            # Navigate to Bing Images
            search_url = f"https://www.bing.com/images/search?q={requests.utils.quote(query)}&FORM=HDRSC2"
            logger.info(f"Searching Bing Images for: {query}")
            
            try:
                page.goto(search_url, wait_until='networkidle', timeout=30000)
                page.wait_for_timeout(4000)
                
                # Scroll to load more images
                for _ in range(5):
                    page.keyboard.press("End")
                    page.wait_for_timeout(1500)
                
                # Method 1: Extract from mimg class (Bing's image containers)
                image_urls = set()
                
                # Get all image elements
                img_elements = page.query_selector_all('img.mimg')
                
                for img in img_elements:
                    try:
                        src = img.get_attribute('src')
                        if src and src.startswith('http') and len(src) > 100:
                            # Filter out Bing's thumbnails
                            if 'th?id=' not in src or 'tse' in src:
                                image_urls.add(src)
                                logger.info(f"Found Bing image: {src[:80]}...")
                    except Exception:
                        continue
                
                # Method 2: Extract from data attributes and links
                all_images = page.query_selector_all('a.iusc')
                
                for link in all_images:
                    try:
                        m_attr = link.get_attribute('m')
                        if m_attr:
                            import json
                            try:
                                data = json.loads(m_attr)
                                img_url = data.get('murl') or data.get('turl')
                                if img_url and img_url.startswith('http'):
                                    image_urls.add(img_url)
                                    logger.info(f"Extracted from metadata: {img_url[:80]}...")
                            except:
                                pass
                    except Exception:
                        continue
                
                logger.info(f"Found {len(image_urls)} unique image URLs from Bing")
                
            except Exception as e:
                logger.error(f"Failed to scrape Bing Images: {e}")
                browser.close()
                return []
            
            browser.close()
            
            # Download images
            for i, url in enumerate(list(image_urls)[:count * 2]):
                if len(images) >= count:
                    break
                img_data = download_and_optimize_image(url, topic, len(images) + 1)
                if img_data:
                    images.append(img_data)
                time.sleep(0.6)
            
    except Exception as e:
        logger.error(f"Bing Images fetch failed: {e}")
    
    return images

def fetch_combined_images(topic, count=3):
    """Fetch images using Bing (most reliable scraping target)"""
    logger.info(f"Fetching images for '{topic}' using Bing Images...")
    images = fetch_bing_images(topic, count)
    
    if images:
        logger.info(f"[OK] Successfully fetched {len(images)} images")
        return images
    else:
        logger.error("Failed to fetch images from Bing")
        return [{"type": "local", "path": "", "resolution": "N/A"}]

# Main export functions
def fetch_pinterest_images(topic, count=3, timeout=40):
    return fetch_combined_images(topic, count)

def fetch_pinterest_image(topic, timeout=40):
    result = fetch_combined_images(topic, count=1)
    return result[0] if result else {"type": "local", "path": "", "resolution": "N/A"}

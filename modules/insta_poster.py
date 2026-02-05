# modules/insta_poster.py - FIXED VERSION
import os
import time
import requests
from PIL import Image
from dotenv import load_dotenv
from typing import List, Optional, Dict, Any
import json

load_dotenv()

# Load credentials from environment
INSTAGRAM_BUSINESS_ID = os.getenv("INSTAGRAM_BUSINESS_ID")
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN")
IG_USERNAME = os.getenv("IG_USERNAME")  # Fixed typo: was IG_USERNAM
IG_PASSWORD = os.getenv("IG_PASSWORD")

try:
    from utils.logger import logger
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)


class InstagramGraphAPI:
    """
    Instagram Graph API uploader v24.0 using GitHub URLs
    """
    
    def __init__(self):
        # SET ATTRIBUTES FIRST before calling methods
        self.graph_api_version = "v24.0"
        self.github_repo = "Vamshi18-art/AutoLearn-CS"
        self.github_branch = "main"
        
        # Now validate credentials
        self._validate_credentials()
        
    def _validate_credentials(self):
        """Validate credentials"""
        if not INSTAGRAM_BUSINESS_ID or not INSTAGRAM_ACCESS_TOKEN:
            raise ValueError(
                "Instagram Graph API credentials not found. "
                "Please set INSTAGRAM_BUSINESS_ID and INSTAGRAM_ACCESS_TOKEN in .env file"
            )
        logger.info("✓ Instagram Graph API credentials validated")
        logger.info(f"✓ Using Graph API version: {self.graph_api_version}")
    
    def _get_github_raw_url(self, local_path: str) -> str:
        """
        Convert local path to GitHub raw URL
        """
        try:
            # Extract filename from local path
            filename = os.path.basename(local_path)
            
            # Construct GitHub raw URL
            github_url = f"https://raw.githubusercontent.com/{self.github_repo}/{self.github_branch}/static/posts/{filename}"
            
            logger.info(f"Converted to GitHub URL: {github_url}")
            return github_url
            
        except Exception as e:
            logger.error(f"Failed to create GitHub URL: {e}")
            raise
    
    def _check_github_image_exists(self, github_url: str) -> bool:
        """Check if image exists on GitHub"""
        try:
            response = requests.head(github_url, timeout=10)
            return response.status_code == 200
        except:
            return False
    
    def create_media_container(self, image_url: str, caption: str = "", 
                              is_carousel_item: bool = False) -> Optional[str]:
        """
        Create media container on Instagram
        """
        try:
            url = f"https://graph.facebook.com/{self.graph_api_version}/{INSTAGRAM_BUSINESS_ID}/media"
            
            params = {
                'image_url': image_url,
                'access_token': INSTAGRAM_ACCESS_TOKEN,
            }
            
            if is_carousel_item:
                params['is_carousel_item'] = 'true'
            else:
                if caption:
                    params['caption'] = caption
            
            logger.info(f"Creating media container for: {image_url}")
            response = requests.post(url, params=params)
            result = response.json()
            
            if 'id' in result:
                media_id = result['id']
                logger.info(f"✓ Created media container: {media_id}")
                return media_id
            else:
                logger.error(f"Media container creation failed: {result}")
                return None
                
        except Exception as e:
            logger.error(f"Create media container failed: {e}")
            return None
    
    def publish_media(self, creation_id: str) -> bool:
        """Publish media container"""
        try:
            url = f"https://graph.facebook.com/{self.graph_api_version}/{INSTAGRAM_BUSINESS_ID}/media_publish"
            data = {
                'creation_id': creation_id,
                'access_token': INSTAGRAM_ACCESS_TOKEN
            }
            
            logger.info(f"Publishing media: {creation_id}")
            response = requests.post(url, data=data)
            result = response.json()
            
            if 'id' in result:
                logger.info(f"✓ Media published successfully: {result['id']}")
                return True
            else:
                logger.error(f"Publish failed: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Publish media failed: {e}")
            return False
    
    def post_single_image(self, local_image_path: str, caption: str = "") -> bool:
        """
        Post single image to Instagram using GitHub URL
        """
        logger.info(f"Posting single image: {local_image_path}")
        
        if not os.path.exists(local_image_path):
            logger.error(f"Local image not found: {local_image_path}")
            return False
        
        try:
            # Step 1: Convert to GitHub URL
            image_url = self._get_github_raw_url(local_image_path)
            
            # Step 2: Verify image exists on GitHub
            logger.info(f"Checking if image exists on GitHub...")
            if not self._check_github_image_exists(image_url):
                logger.error(f"Image not found on GitHub: {image_url}")
                logger.info("Please upload the image to your GitHub repository first")
                return False
            
            logger.info(f"✓ Image found on GitHub: {image_url}")
            
            # Step 3: Create media container
            media_id = self.create_media_container(image_url, caption, is_carousel_item=False)
            if not media_id:
                logger.error("Failed to create media container")
                return False
            
            # Step 4: Publish (don't wait for processing - let API handle it)
            logger.info(f"Publishing media {media_id}...")
            return self.publish_media(media_id)
            
        except Exception as e:
            logger.error(f"Post single image failed: {e}")
            return False
    
    def post_carousel(self, local_image_paths: List[str], caption: str = "") -> bool:
        """
        Post carousel to Instagram using GitHub URLs
        """
        if len(local_image_paths) < 2 or len(local_image_paths) > 10:
            logger.error("Carousel requires 2 to 10 images")
            return False
        
        logger.info(f"Posting carousel with {len(local_image_paths)} images")
        
        # Check all images exist locally
        for path in local_image_paths:
            if not os.path.exists(path):
                logger.error(f"Local image not found: {path}")
                return False
        
        try:
            media_ids = []
            
            # Step 1: Create media containers for all images
            for i, img_path in enumerate(local_image_paths):
                logger.info(f"Processing image {i+1}/{len(local_image_paths)}")
                
                # Convert to GitHub URL
                image_url = self._get_github_raw_url(img_path)
                
                # Verify image exists on GitHub
                if not self._check_github_image_exists(image_url):
                    logger.error(f"Image not found on GitHub: {image_url}")
                    return False
                
                # Create media container for carousel item
                media_id = self.create_media_container(image_url, "", is_carousel_item=True)
                
                if media_id:
                    media_ids.append(media_id)
                    logger.info(f"  Got media ID: {media_id}")
                else:
                    logger.error(f"Failed to create media container for image {i+1}")
                    return False
            
            if len(media_ids) < 2:
                logger.error("Not enough images processed successfully")
                return False
            
            # Step 2: Create carousel
            logger.info(f"Creating carousel with {len(media_ids)} images")
            
            url = f"https://graph.facebook.com/{self.graph_api_version}/{INSTAGRAM_BUSINESS_ID}/media"
            
            # Prepare children parameter
            children = ','.join(media_ids)
            
            data = {
                'media_type': 'CAROUSEL',
                'caption': caption,
                'children': children,
                'access_token': INSTAGRAM_ACCESS_TOKEN
            }
            
            response = requests.post(url, data=data)
            result = response.json()
            
            if 'id' not in result:
                logger.error(f"Carousel creation failed: {result}")
                return False
            
            carousel_id = result['id']
            logger.info(f"Carousel container created: {carousel_id}")
            
            # Step 3: Publish carousel
            time.sleep(2)  # Brief wait
            return self.publish_media(carousel_id)
            
        except Exception as e:
            logger.error(f"Post carousel failed: {e}")
            return False


# ===== SIMPLE UPLOADER FUNCTIONS =====

def post_single_image(image_path: str, caption: str = "", 
                     username: str = None, password: str = None) -> bool:
    """Simple function for single image posting"""
    try:
        logger.info(f"Attempting to post single image: {image_path}")
        
        # Check if file exists
        if not os.path.exists(image_path):
            logger.error(f"Image not found: {image_path}")
            return False
        
        # Try Graph API if credentials available
        if INSTAGRAM_BUSINESS_ID and INSTAGRAM_ACCESS_TOKEN:
            logger.info("Using Instagram Graph API")
            try:
                uploader = InstagramGraphAPI()
                return uploader.post_single_image(image_path, caption)
            except Exception as e:
                logger.error(f"Graph API failed: {e}")
                return False
        else:
            logger.error("Instagram Graph API credentials not configured")
            return False
            
    except Exception as e:
        logger.error(f"post_single_image failed: {e}")
        return False

def post_carousel_instagram(image_paths: List[str], caption: str = "",
                           username: str = None, password: str = None) -> bool:
    """Simple function for carousel posting"""
    try:
        logger.info(f"Attempting to post carousel with {len(image_paths)} images")
        
        # Check if files exist
        for path in image_paths:
            if not os.path.exists(path):
                logger.error(f"Image not found: {path}")
                return False
        
        # Validate carousel requirements
        if len(image_paths) < 2 or len(image_paths) > 10:
            logger.error("Carousel requires 2 to 10 images")
            return False
        
        # Try Graph API if credentials available
        if INSTAGRAM_BUSINESS_ID and INSTAGRAM_ACCESS_TOKEN:
            logger.info("Using Instagram Graph API")
            try:
                uploader = InstagramGraphAPI()
                return uploader.post_carousel(image_paths, caption)
            except Exception as e:
                logger.error(f"Graph API failed: {e}")
                return False
        else:
            logger.error("Instagram Graph API credentials not configured")
            return False
            
    except Exception as e:
        logger.error(f"post_carousel_instagram failed: {e}")
        return False

def post_local_image(local_path: str, caption: str = "",
                    username: str = None, password: str = None) -> bool:
    """Alias for single image posting"""
    return post_single_image(local_path, caption, username, password)

def optimize_image_for_instagram(image_path: str) -> str:
    """Legacy optimization function"""
    return image_path


# ===== EXPORTS =====
__all__ = [
    'InstagramGraphAPI',
    'post_single_image',
    'post_carousel_instagram',
    'post_local_image',
    'optimize_image_for_instagram'
]


# ===== TEST =====
if __name__ == "__main__":
    print("Testing Instagram Graph API...")
    
    # Check credentials
    print(f"INSTAGRAM_BUSINESS_ID: {INSTAGRAM_BUSINESS_ID or 'Not set'}")
    print(f"INSTAGRAM_ACCESS_TOKEN: {'Set' if INSTAGRAM_ACCESS_TOKEN else 'Not set'}")
    
    # Test creating uploader
    try:
        uploader = InstagramGraphAPI()
        print("✅ InstagramGraphAPI created successfully")
        print(f"  API Version: {uploader.graph_api_version}")
    except Exception as e:
        print(f"❌ Failed to create InstagramGraphAPI: {e}")
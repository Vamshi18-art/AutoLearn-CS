# modules/instagram_story_poster.py
import requests
import json
import os
from utils.logger import logger

class InstagramStoryPoster:
    def __init__(self, access_token: str = None, instagram_account_id: str = None):
        # Try to get credentials from environment variables if not provided
        self.access_token = access_token or os.getenv('INSTAGRAM_ACCESS_TOKEN')
        self.instagram_account_id = instagram_account_id or os.getenv('INSTAGRAM_BUSINESS_ID')
        self.base_url = "https://graph.facebook.com/v18.0"
        
        # Validate credentials
        if not self.access_token or not self.instagram_account_id:
            logger.warning("⚠️ Instagram Story Poster not initialized - missing credentials")
            self.initialized = False
        else:
            self.initialized = True
            logger.info("✅ Instagram Story Poster initialized successfully")
    
    def post_story_from_image(self, image_path: str, caption: str = ""):
        """Post a story to Instagram using Graph API"""
        if not self.initialized:
            logger.error("❌ Instagram Story Poster not initialized - missing credentials")
            return False
            
        try:
            # Step 1: Upload image and get media ID
            media_id = self._upload_image(image_path)
            if not media_id:
                return False
            
            # Step 2: Create story container
            story_id = self._create_story_container(media_id, caption)
            if story_id:
                logger.info(f"✅ Story posted successfully! Story ID: {story_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"❌ Story posting failed: {e}")
            return False
    
    def _upload_image(self, image_path: str):
        """Upload image to Instagram"""
        try:
            upload_url = f"{self.base_url}/{self.instagram_account_id}/media"
            
            # Check if file exists
            if not os.path.exists(image_path):
                logger.error(f"❌ Image file not found: {image_path}")
                return None
            
            with open(image_path, 'rb') as image_file:
                files = {'file': image_file}
                data = {
                    'access_token': self.access_token,
                    'media_type': 'STORIES',
                    'is_carousel_item': 'false'
                }
                
                logger.info(f"📤 Uploading image to: {upload_url}")
                response = requests.post(upload_url, files=files, data=data)
                result = response.json()
                
                logger.info(f"📦 Upload response: {result}")
                
                if 'id' in result:
                    logger.info(f"✅ Image uploaded successfully. Media ID: {result['id']}")
                    return result['id']
                else:
                    logger.error(f"❌ Image upload failed: {result}")
                    # Check for specific error messages
                    if 'error' in result:
                        error_msg = result['error'].get('message', 'Unknown error')
                        logger.error(f"❌ API Error: {error_msg}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Image upload error: {e}")
            return None
    
    def _create_story_container(self, media_id: str, caption: str = ""):
        """Create story from uploaded media"""
        try:
            create_url = f"{self.base_url}/{self.instagram_account_id}/media_publish"
            
            data = {
                'access_token': self.access_token,
                'creation_id': media_id,
                'caption': caption
            }
            
            logger.info(f"📝 Creating story with media ID: {media_id}")
            response = requests.post(create_url, data=data)
            result = response.json()
            
            logger.info(f"📦 Story creation response: {result}")
            
            if 'id' in result:
                return result['id']
            else:
                logger.error(f"❌ Story creation failed: {result}")
                if 'error' in result:
                    error_msg = result['error'].get('message', 'Unknown error')
                    logger.error(f"❌ API Error: {error_msg}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Story creation error: {e}")
            return None
    
    def get_account_info(self):
        """Get Instagram account information"""
        if not self.initialized:
            logger.error("❌ Instagram Story Poster not initialized")
            return None
            
        try:
            url = f"{self.base_url}/{self.instagram_account_id}"
            params = {
                'access_token': self.access_token,
                'fields': 'id,username,media_count,followers_count'
            }
            
            response = requests.get(url, params=params)
            result = response.json()
            
            if 'error' in result:
                logger.error(f"❌ Account info failed: {result['error']}")
                return None
                
            return result
        except Exception as e:
            logger.error(f"❌ Account info failed: {e}")
            return None

    def validate_credentials(self):
        """Validate Instagram API credentials"""
        if not self.initialized:
            return False, "Credentials not provided"
            
        try:
            account_info = self.get_account_info()
            if account_info and 'username' in account_info:
                return True, f"✅ Connected to Instagram account: @{account_info['username']}"
            else:
                return False, "❌ Invalid credentials or permissions"
        except Exception as e:
            return False, f"❌ Validation failed: {e}"
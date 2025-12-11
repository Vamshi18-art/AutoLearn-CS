# modules/story_generator.py
import os
import random
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from utils.logger import logger
from utils.helpers import ensure_dir, sanitize_filename

class StoryGenerator:
    def __init__(self):
        self.story_width = 1080
        self.story_height = 1920  # Instagram Story dimensions
        self.output_dir = os.path.join("static", "stories")
        ensure_dir(self.output_dir)
        
        # Professional Instagram Story themes
        self.themes = {
            "python": {
                "bg_color": (41, 128, 185),    # Instagram Blue
                "text_color": (255, 255, 255),
                "accent_color": (255, 223, 0),  # Gold accent
                "icon": "🐍"
            },
            "algorithms": {
                "bg_color": (39, 174, 96),     # Instagram Green
                "text_color": (255, 255, 255),
                "accent_color": (255, 168, 0),  # Orange accent
                "icon": "⚡"
            },
            "data_structures": {
                "bg_color": (142, 68, 173),    # Instagram Purple
                "text_color": (255, 255, 255),
                "accent_color": (255, 138, 216), # Pink accent
                "icon": "🏗️"
            },
            "computer_science": {
                "bg_color": (231, 76, 60),     # Instagram Red
                "text_color": (255, 255, 255),
                "accent_color": (255, 223, 0),  # Gold accent
                "icon": "💻"
            },
            "web_development": {
                "bg_color": (52, 73, 94),      # Dark Blue
                "text_color": (255, 255, 255),
                "accent_color": (26, 188, 156), # Teal accent
                "icon": "🌐"
            }
        }

    def generate_cs_fact_story(self, fact_data: dict):
        """Generate professional CS fact story for Instagram"""
        theme = self.themes[fact_data["category"]]
        
        # Create background
        img = Image.new('RGB', (self.story_width, self.story_height), theme["bg_color"])
        draw = ImageDraw.Draw(img)
        
        # Add decorative elements
        self._add_decorative_elements(draw, theme)
        
        # Add header with icon
        self._add_header(draw, f"{theme['icon']} CS FACT", theme)
        
        # Add day badge
        self._add_day_badge(draw, fact_data["day"], fact_data["week"], theme)
        
        # Add main fact
        self._add_main_fact(draw, fact_data["fact"], theme)
        
        # Add explanation
        self._add_explanation(draw, fact_data["explanation"], theme)
        
        # Add footer
        self._add_footer(draw, theme)
        
        # Save story
        filename = f"cs_fact_day_{fact_data['day']}_{datetime.now().strftime('%H%M%S')}.jpg"
        return self._save_story(img, filename)

    def _add_decorative_elements(self, draw, theme):
        """Add decorative elements to the story"""
        # Add corner accents
        circle_radius = 150
        positions = [
            (-50, -50),  # Top-left
            (self.story_width - circle_radius + 50, -50),  # Top-right
            (-50, self.story_height - circle_radius + 50),  # Bottom-left
            (self.story_width - circle_radius + 50, self.story_height - circle_radius + 50)  # Bottom-right
        ]
        
        for x, y in positions:
            draw.ellipse([x, y, x + circle_radius, y + circle_radius], 
                        fill=theme["accent_color"])

    def _add_header(self, draw, text, theme):
        """Add story header"""
        try:
            font = ImageFont.truetype("arialbd.ttf", 80)
        except:
            font = ImageFont.load_default()
        
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        x = (self.story_width - text_width) // 2
        y = 120
        
        # Text shadow
        draw.text((x + 3, y + 3), text, font=font, fill=(0, 0, 0, 100))
        # Main text
        draw.text((x, y), text, font=font, fill=theme["accent_color"])

    def _add_day_badge(self, draw, day, week, theme):
        """Add day and week badge"""
        badge_text = f"📅 Day {day} • Week {week}"
        try:
            font = ImageFont.truetype("arial.ttf", 40)
        except:
            font = ImageFont.load_default()
        
        bbox = draw.textbbox((0, 0), badge_text, font=font)
        text_width = bbox[2] - bbox[0]
        x = (self.story_width - text_width) // 2
        y = 220
        
        draw.text((x, y), badge_text, font=font, fill=theme["text_color"])

    def _add_main_fact(self, draw, fact, theme):
        """Add main fact text"""
        try:
            font = ImageFont.truetype("arialbd.ttf", 64)
        except:
            font = ImageFont.load_default()
        
        # Wrap text
        lines = self._wrap_text(fact, font, self.story_width - 100)
        y = 400
        
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            x = (self.story_width - text_width) // 2
            
            # Text shadow for depth
            draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, 150))
            # Main text
            draw.text((x, y), line, font=font, fill=theme["text_color"])
            
            y += 80

    def _add_explanation(self, draw, explanation, theme):
        """Add explanation text"""
        try:
            font = ImageFont.truetype("arial.ttf", 48)
        except:
            font = ImageFont.load_default()
        
        # Wrap text
        lines = self._wrap_text(explanation, font, self.story_width - 120)
        y = 650
        
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            x = (self.story_width - text_width) // 2
            
            draw.text((x, y), line, font=font, fill=theme["accent_color"])
            y += 60

    def _add_footer(self, draw, theme):
        """Add footer with hashtags"""
        try:
            font = ImageFont.truetype("arial.ttf", 36)
        except:
            font = ImageFont.load_default()
        
        footer_text = "#CSFacts #Programming #LearnToCode"
        bbox = draw.textbbox((0, 0), footer_text, font=font)
        text_width = bbox[2] - bbox[0]
        x = (self.story_width - text_width) // 2
        y = self.story_height - 100
        
        draw.text((x, y), footer_text, font=font, fill=theme["text_color"])

    def _wrap_text(self, text: str, font, max_width: int):
        """Wrap text to fit within max width"""
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            bbox = ImageDraw.Draw(Image.new('RGB', (1, 1))).textbbox((0, 0), test_line, font=font)
            test_width = bbox[2] - bbox[0]
            
            if test_width <= max_width:
                current_line.append(word)
            else:
                lines.append(' '.join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines

    def _save_story(self, img, filename: str):
        """Save story image and return path"""
        safe_filename = sanitize_filename(filename)
        output_path = os.path.join(self.output_dir, safe_filename)
        
        img.save(output_path, "JPEG", quality=95)
        logger.info(f"✅ Story generated: {output_path}")
        
        # Return web-accessible path
        return f"stories/{safe_filename}"
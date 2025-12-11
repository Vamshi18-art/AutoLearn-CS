# modules/slide_builder.py
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from utils.logger import logger
from utils.helpers import ensure_dir, sanitize_filename


WIDTH, HEIGHT = 1080, 1080
PADDING = 60


# Professional Color Themes
THEMES = {
    "blue": {
        "gradient_top": (240, 248, 255),
        "gradient_bottom": (189, 224, 254),
        "header": (37, 99, 235),
        "header_text": (255, 255, 255),
        "heading": (15, 23, 42),
        "body": (30, 41, 59),
        "code_bg": (15, 23, 42),
        "code_text": (224, 242, 254),
        "panel": (255, 255, 255, 245),
        "accent": (59, 130, 246),
    },
    "purple": {
        "gradient_top": (250, 245, 255),
        "gradient_bottom": (221, 214, 254),
        "header": (109, 40, 217),
        "header_text": (255, 255, 255),
        "heading": (17, 24, 39),
        "body": (31, 41, 55),
        "code_bg": (17, 24, 39),
        "code_text": (233, 213, 255),
        "panel": (255, 255, 255, 245),
        "accent": (147, 51, 234),
    },
    "light_cream": {
        "gradient_top": (255, 252, 244),      # Soft cream background
        "gradient_bottom": (250, 240, 215),   # Light beige for subtle contrast
        "header": (210, 180, 140),            # Tan brown for warmth
        "header_text": (255, 255, 255),       # White header text
        "heading": (101, 67, 33),             # Deep brown heading
        "body": (80, 54, 22),                 # Earth-toned readable text
        "code_bg": (220, 198, 156),           # Slightly darker cream for code blocks
        "code_text": (40, 30, 10),            # Dark brown for code text
        "panel": (255, 255, 255, 245),        # Light white semi-transparent panel
        "accent": (205, 133, 63),
    }, 
                                # Bronze accent color
"logic_light": {
    "gradient_top": (255, 255, 255),      # White top
    "gradient_bottom": (230, 230, 230),   # Light gray
    "header": (30, 30, 30),               # Deep charcoal
    "header_text": (255, 255, 255),       # White
    "heading": (20, 20, 20),              # Black
    "body": (50, 50, 50),                 # Dark gray
    "code_bg": (240, 240, 240),           # Light gray code box
    "code_text": (30, 30, 30),            # Black text
    "panel": (255, 255, 255, 245),        # White translucent
    "accent": (0, 0, 0)                   # Pure black for dots/bullets
}


}


DEFAULT_THEME = "blue"


def _font_path(name):
    return os.path.join(os.path.dirname(__file__), "..", "fonts", name)


def load_font(size=36, bold=False):
    candidates = []
    if bold:
        candidates.append(_font_path("Inter-Bold.ttf"))
    candidates.append(_font_path("Inter-Regular.ttf"))
    candidates.append("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    candidates.append("C:\\Windows\\Fonts\\arialbd.ttf" if bold else "C:\\Windows\\Fonts\\arial.ttf")
    for f in candidates:
        if f and os.path.exists(f):
            try:
                return ImageFont.truetype(f, size=size)
            except Exception:
                continue
    return ImageFont.load_default()


# Professional font hierarchy
TITLE_FONT = load_font(64, bold=True)
HEADING_FONT = load_font(52, bold=True)
BODY_FONT = load_font(36)
BULLET_FONT = load_font(36)
CODE_FONT = load_font(26)
SMALL_FONT = load_font(22)
WATERMARK_FONT = load_font(32, bold=True)


def _modern_gradient(size, theme_colors):
    W, H = size
    top_color = theme_colors["gradient_top"]
    bottom_color = theme_colors["gradient_bottom"]
    
    base = Image.new("RGB", (W, H), top_color)
    overlay = Image.new("RGB", (W, H), bottom_color)
    mask = Image.linear_gradient("L").rotate(90).resize((W, H))
    grad = Image.composite(overlay, base, mask)
    return grad.filter(ImageFilter.GaussianBlur(radius=2))


def text_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def split_body_to_lines(body: str):
    body = body.replace("\r\n", "\n").replace("\r", "\n")
    parts = []
    for para in body.split("\n\n"):
        lines = para.split("\n")
        for ln in lines:
            trimmed = ln.strip()
            if trimmed:
                parts.append(trimmed)
    return parts


def wrap_text_for_width(draw, text, font, max_w):
    words = text.split()
    if not words:
        return [""]
    lines = []
    cur = words[0]
    for w in words[1:]:
        test = cur + " " + w
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] <= max_w:
            cur = test
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def _draw_text_with_shadow(draw, pos, text, font, fill, shadow_offset=2):
    x, y = pos
    draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=(0, 0, 0, 60))
    draw.text((x, y), text, font=font, fill=fill)


def make_slide(topic_title, heading, body, out_path, slide_number, theme=DEFAULT_THEME, no_topic=False):
    try:
        ensure_dir(os.path.dirname(out_path))
        
        colors = THEMES.get(theme, THEMES[DEFAULT_THEME])
        img = _modern_gradient((WIDTH, HEIGHT), colors)
        draw = ImageDraw.Draw(img)

        # Header with accent bar
        header_h = 100
        draw.rectangle([(0, 0), (WIDTH, header_h)], fill=colors["header"])
        draw.rectangle([(0, 0), (WIDTH, 8)], fill=colors["accent"])

        # Show topic title unless suppressed
        if not no_topic:
            draw.text((PADDING, header_h // 2 - 16), topic_title.upper(), font=SMALL_FONT, fill=colors["header_text"])

        # Heading
        heading_x = PADDING
        heading_y = header_h + 50
        heading_lines = wrap_text_for_width(draw, heading, HEADING_FONT, WIDTH - 2 * PADDING)
        for i, line in enumerate(heading_lines[:3]):
            y = heading_y + i * (text_size(draw, line, HEADING_FONT)[1] + 10)
            _draw_text_with_shadow(draw, (heading_x, y), line, HEADING_FONT, colors["heading"])

        # Content panel
        body_top = heading_y + len(heading_lines) * (text_size(draw, "A", HEADING_FONT)[1] + 10) + 30
        panel_margin = PADDING
        panel_left = panel_margin
        panel_right = WIDTH - panel_margin
        panel_bottom = HEIGHT - 140
        panel_box = [panel_left, body_top, panel_right, panel_bottom]

        # Shadow and panel overlay
        shadow_offset = 8
        shadow_box = [panel_left + shadow_offset, body_top + shadow_offset, 
                      panel_right + shadow_offset, panel_bottom + shadow_offset]
        overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
        od = ImageDraw.Draw(overlay)
        od.rounded_rectangle(shadow_box, radius=20, fill=(0, 0, 0, 30))
        od.rounded_rectangle(panel_box, radius=20, fill=colors["panel"])
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(img)

        # Render body content
        text_x = panel_left + 40
        text_y = body_top + 35
        max_w = (panel_right - panel_left) - 80

        desc = body or ""
        if "```" in desc:
            parts = desc.split("```")
            seq = []
            for i, part in enumerate(parts):
                if i % 2 == 0:
                    if part.strip():
                        seq.append(("text", part.strip()))
                else:
                    code_content = part.strip()
                    if code_content.startswith(("python", "js", "javascript", "java", "cpp")):
                        lines = code_content.split("\n", 1)
                        code_content = lines[1] if len(lines) > 1 else ""
                    seq.append(("code", code_content.strip()))
        else:
            seq = [("text", desc.strip())]

        for kind, chunk in seq:
            if kind == "code":
                code_lines = chunk.splitlines()
                _, sample_h = text_size(draw, "A", CODE_FONT)
                box_h = max(80, (sample_h + 10) * (len(code_lines) + 1))
                code_box = [text_x, text_y, panel_right - 40, text_y + box_h]
                code_overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
                code_draw = ImageDraw.Draw(code_overlay)
                code_draw.rounded_rectangle(code_box, radius=12, fill=colors["code_bg"])
                img = Image.alpha_composite(img.convert("RGBA"), code_overlay).convert("RGB")
                draw = ImageDraw.Draw(img)
                cy = text_y + 15
                for line in code_lines:
                    draw.text((text_x + 15, cy), line, font=CODE_FONT, fill=colors["code_text"])
                    _, lh = text_size(draw, line, CODE_FONT)
                    cy += lh + 8
                text_y = code_box[3] + 20
                continue

            lines = split_body_to_lines(chunk)
            for raw_line in lines:
                bullet_prefix = None
                for p in ("*", "-", "•"):
                    if raw_line.startswith(p):
                        bullet_prefix = p
                        break
                if bullet_prefix:
                    content = raw_line[len(bullet_prefix):].strip()
                    wrapped = wrap_text_for_width(draw, content, BULLET_FONT, max_w - 40)
                    for wi, wl in enumerate(wrapped):
                        if wi == 0:
                            draw.ellipse([(text_x, text_y + 8), (text_x + 10, text_y + 18)], fill=colors["accent"])
                            draw.text((text_x + 25, text_y), wl, font=BULLET_FONT, fill=colors["body"])
                        else:
                            draw.text((text_x + 25, text_y), wl, font=BULLET_FONT, fill=colors["body"])
                        _, h = text_size(draw, wl, BULLET_FONT)
                        text_y += h + 10
                else:
                    wrapped = wrap_text_for_width(draw, raw_line, BODY_FONT, max_w)
                    for wl in wrapped:
                        draw.text((text_x, text_y), wl, font=BODY_FONT, fill=colors["body"])
                        _, h = text_size(draw, wl, BODY_FONT)
                        text_y += h + 10
                text_y += 8

        # Footer
        footer_y = HEIGHT - 80
        footer_box = [panel_left, footer_y, panel_right, HEIGHT - 20]
        footer_overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
        footer_draw = ImageDraw.Draw(footer_overlay)
        footer_draw.rounded_rectangle(footer_box, radius=15, fill=(*colors["header"], 250))
        img = Image.alpha_composite(img.convert("RGBA"), footer_overlay).convert("RGB")
        draw = ImageDraw.Draw(img)
        draw.text((panel_left + 30, footer_y + 20), f"Slide {slide_number}", font=SMALL_FONT, fill=(255, 255, 255))
        brand = "Krish@18"
        brand_w, _ = text_size(draw, brand, SMALL_FONT)
        draw.text((panel_right - brand_w - 30, footer_y + 20), brand, font=SMALL_FONT, fill=(255, 255, 255))

        # Watermark
        watermark = "DSA"
        tw, th = text_size(draw, watermark, WATERMARK_FONT)
        margin = 25
        wx = WIDTH - margin - tw
        wy = HEIGHT - margin - th
        wm_overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
        wm_draw = ImageDraw.Draw(wm_overlay)
        wm_draw.text((wx, wy), watermark, font=WATERMARK_FONT, fill=(*colors["accent"], 120))
        img = Image.alpha_composite(img.convert("RGBA"), wm_overlay).convert("RGB")

        img.save(out_path, format="PNG", optimize=True, quality=95)
        logger.info("✅ Successfully saved slide: %s (theme: %s)", out_path, theme)
        return True  # ADD THIS LINE - return True for success

    except Exception as e:
        logger.error(f"❌ Failed to create slide {out_path}: {e}")
        return False  # ADD THIS LINE - return False for failure


def generate_slides_and_save(topic_obj, slides, output_dir="static/posts"):
    """Generate and save slides as images - FIXED VERSION"""
    try:
        ensure_dir(output_dir)
        base = sanitize_filename(topic_obj['topic'])
        out_paths = []

        # Determine theme
        topic_lower = topic_obj['topic'].lower()
        if 'quiz' in topic_lower:
            theme = "purple"
            logger.info("🟣 Using PURPLE theme for quiz content: %s", topic_obj['topic'])
        elif 'guess' in topic_lower or 'output' in topic_lower:
            theme = "light_cream"
            logger.info("🟤 Using LIGHT CREAM theme for guess-output content: %s", topic_obj['topic'])
        elif 'logic' in topic_lower or 'puzzle' in topic_lower:
            theme = "logic_light"
            logger.info("🟡 Using LIGHT LOGIC-PUZZLE theme: %s", topic_obj['topic'])
        else:
            theme = "blue"
            logger.info("🔵 Using BLUE theme for standard content: %s", topic_obj['topic'])

        no_topic = theme == "light_cream"

        # Generate each slide
        for i, slide in enumerate(slides, start=1):
            filename = f"{topic_obj['id']}_{base}_{i}.png"
            path = os.path.join(output_dir, filename)
            
            heading = slide.get('heading', f'Slide {i}')
            body = slide.get('body', 'Content not available.')
            
            success = make_slide(
                topic_obj['topic'], 
                heading, 
                body, 
                path, 
                i, 
                theme=theme, 
                no_topic=no_topic
            )
            
            if success:
                out_paths.append(path)
            else:
                logger.error(f"❌ Failed to generate slide {i} for {topic_obj['topic']}")

        logger.info("✅ Successfully generated %d/%d slides for: %s", len(out_paths), len(slides), topic_obj['topic'])
        return out_paths

    except Exception as e:
        logger.error(f"❌ Error in generate_slides_and_save: {e}")
        return []

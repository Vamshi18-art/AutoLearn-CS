# utils/image_creator.py
from PIL import Image, ImageDraw, ImageFont
import textwrap
import os

def generate_image_dynamic(topic: str, content: str, output_dir="data/generated"):
    """
    Generates a clean educational image with topic and text content.
    Saves the image as JPG and returns its file path.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Image size and base color
    img = Image.new("RGB", (1080, 1080), color=(245, 245, 250))
    draw = ImageDraw.Draw(img)

    # Fonts (use defaults for portability)
    try:
        title_font = ImageFont.truetype("arialbd.ttf", 70)
        text_font = ImageFont.truetype("arial.ttf", 40)
    except:
        title_font = ImageFont.load_default()
        text_font = ImageFont.load_default()

    # Draw title
    margin = 60
    y_text = 80
    draw.text((margin, y_text), topic.upper(), font=title_font, fill=(30, 30, 60))
    y_text += 130

    # Wrap content text
    wrapped = textwrap.fill(content, width=40)
    for line in wrapped.split("\n"):
        draw.text((margin, y_text), line, font=text_font, fill=(60, 60, 60))
        y_text += 55

    # Save image
    file_path = os.path.join(output_dir, f"{topic.replace(' ', '_')}.jpg")
    img.save(file_path)
    return file_path


# quick test run
if __name__ == "__main__":
    test = generate_image_dynamic(
        "What is Array?",
        "An array is a linear data structure that stores elements in contiguous memory locations. "
        "It allows random access and efficient traversal of elements using an index."
    )
    print("✅ Image generated at:", test)

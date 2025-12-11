# modules/test_post_instagram.py
import os, sys
from dotenv import load_dotenv
load_dotenv()
from modules.insta_poster import get_instagram_client, post_local_image
from PIL import Image, ImageDraw, ImageFont

u = os.getenv("IG_USERNAME")
p = os.getenv("IG_PASSWORD")
if not u or not p:
    print("ERROR: IG_USERNAME or IG_PASSWORD missing in .env")
    sys.exit(1)

# create test image if missing
test_img = os.path.join("data","generated","test_post.png")
os.makedirs(os.path.dirname(test_img), exist_ok=True)
if not os.path.exists(test_img):
    img = Image.new("RGB",(1080,1080),(30,120,200))
    d = ImageDraw.Draw(img)
    try:
        f = ImageFont.truetype("arial.ttf", 64)
    except Exception:
        f = None
    d.text((60,500), "AutoLearnCS IG test", fill=(255,255,255), font=f)
    img.save(test_img)

print("Logging in as", u)
cl = get_instagram_client(u, p)   # will prompt for challenge if required
print("Logged in OK:", getattr(cl, "username", "<unknown>"))

print("Uploading", test_img)
res = post_local_image(test_img, "AutoLearnCS test (delete after)", username=u, password=p, cl=cl)
print("Upload result:", res)

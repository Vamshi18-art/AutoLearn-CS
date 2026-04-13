import sys
import os

# Fix import path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

from modules.rag_agent import add_document

# ✅ Build absolute path (VERY IMPORTANT)
file_path = os.path.join(BASE_DIR, "data", "docs", "python.txt")

print("📂 Looking for file at:", file_path)

# ✅ Check manually before sending
if not os.path.exists(file_path):
    print("❌ FILE NOT FOUND HERE!")
    exit()

# ✅ Now call RAG
success = add_document(file_path)

if success:
    print("✅ Document added successfully!")
else:
    print("❌ Failed to add document!")
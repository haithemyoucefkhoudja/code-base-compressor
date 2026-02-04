from PIL import Image
from PIL import ImageDraw, ImageFont
Image.MAX_IMAGE_PIXELS = None
import os
import io
import json
# --- Configuration ---
# API_KEY = "AIzaSyBvvlaZaKCY9RWYwOa_f1jlOJkO0p6mV2Q"
ATLAS_PATH = "repo_patterns_tiles.png"          # The big image with code details
# LEGEND_PATH = "pattern_tiles_legend.png"  # The visual inventory/menu
# COORDS_PATH = "pattern_tiles.coords.json" # The map
# OUTPUT_DIR = "ai-thinking"
# META_DATA_PATH = 'pattern_tiles.meta.json'

# --- 2. The Tool Implementation ---
def execute_crop(label):
    # print(f"[Tool] Searching for family: '{label}'...")
    
    # if not os.path.exists(COORDS_PATH):
    #     raise FileNotFoundError(f"{COORDS_PATH} not found.")
    
    # with open(COORDS_PATH, "r") as f:
    #     coords_list = json.load(f)

    # # Find the bbox
    # target_bbox = None
    # for item in coords_list:
    #     if item.get("family") == label:
    #         target_bbox = item.get("bbox")
    #         break
    
    # # Fallback: Case-insensitive
    # if not target_bbox:
    #     for item in coords_list:
    #         if item.get("family", "").lower() == label.lower():
    #             target_bbox = item.get("bbox")
    #             break

    # if not target_bbox:
    #     print(f"[Tool] Family '{label}' not found → using fallback image")
    #     return render_text_fallback(label)

    x, y, w, h = (4608,6312,848,1160)
    # print(f"[Tool] Found bbox: {target_bbox}. Cropping Atlas...")

    if not os.path.exists(ATLAS_PATH):
        raise FileNotFoundError(f"{ATLAS_PATH} not found.")

    with Image.open(ATLAS_PATH) as img:
        crop_area = (x, y, x + w, y + h)
        cropped_img = img.crop(crop_area)
        
        safe_label = "".join(c for c in label if c.isalnum() or c in (' ', '_', '-')).strip().replace(" ", "_")
        
        # Save local copy for debug
        filename = f"{safe_label}.png"
        cropped_img.save(filename)
        
        # Return bytes + simple filename
        img_byte_arr = io.BytesIO()
        cropped_img.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue(), f"{safe_label}.png"

execute_crop("\"zod\"::z")
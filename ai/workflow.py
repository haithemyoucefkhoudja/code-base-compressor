
import os
import json
import hashlib
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass
from PIL import Image, ImageDraw, ImageFont

# Configuration Constants
# (Adjust paths to match your environment)
ATLAS_PATH = r"c:\Users\haithem-yk\Desktop\Projects\reposoul-python-job\repo_patterns_tiles.png"
COORDS_PATH = r"c:\Users\haithem-yk\Desktop\Projects\reposoul-python-job\repo_patterns_tiles.coords.json"
MAP_PATH = r"c:\Users\haithem-yk\Desktop\Projects\reposoul-python-job\repo_patterns_tiles.map.json"
OUTPUT_DIR = r"c:\Users\haithem-yk\Desktop\Projects\reposoul-python-job\ai\output"
FONT_PATH = "arial.ttf"

# --- Helper: Color Logic ---

def _hash_bytes(s: str) -> bytes:
    return hashlib.sha256(s.encode("utf-8")).digest()

def get_family_color(family: str) -> Tuple[int, int, int]:
    """Replicates the color generation logic from tiles.py to classify pixels."""
    if family == "PAD": return (255, 255, 255)
    if family == "SEP": return (0, 0, 0)
    
    h = _hash_bytes(family)
    r, g, b = h[0], h[1], h[2]
    r = int(40 + (r / 255) * 175)
    g = int(40 + (g / 255) * 175)
    b = int(40 + (b / 255) * 175)
    return (r, g, b)

# --- Tool 1: Visual Decoder (The Eyes) ---

@dataclass
class VisualContext:
    image: Image.Image
    coords: Dict[str, Dict]
    palette: Dict[Tuple[int, int, int], str]

class VisualDecoder:
    def __init__(self, atlas_path: str = ATLAS_PATH, coords_path: str = COORDS_PATH, map_path: str = MAP_PATH):
        self.atlas_path = atlas_path
        self.coords_path = coords_path
        self.map_path = map_path
        self.context = self._initialize_context()
        
    def _initialize_context(self) -> VisualContext:
        print("👁️ VisualDecoder: Loading Atlas and calibrating palette...")
        if not os.path.exists(self.atlas_path): raise FileNotFoundError(self.atlas_path)
        img = Image.open(self.atlas_path).convert("RGB")
        
        with open(self.coords_path, 'r') as f:
            coords_list = json.load(f)
            coords_map = {item["family"]: item for item in coords_list}
            
        with open(self.map_path, 'r') as f:
            family_keys = list(json.load(f).keys())
            
        palette = {}
        palette[(255, 255, 255)] = "PAD"
        palette[(0, 0, 0)] = "SEP"
        
        # Precompute palette using simulated texture logic
        import numpy as np
        def simulate_tile_color(fam: str) -> Tuple[int, int, int]:
             h = _hash_bytes(fam)
             r, g, b = h[0], h[1], h[2]
             r = int(40 + (r / 255) * 175)
             g = int(40 + (g / 255) * 175)
             b = int(40 + (b / 255) * 175)
             
             strength = 40 + (h[4] % 80)
             r2 = int(np.clip(r + (strength if (h[5] & 1) else -strength), 0, 255))
             g2 = int(np.clip(g + (strength if (h[6] & 1) else -strength), 0, 255))
             b2 = int(np.clip(b + (strength if (h[7] & 1) else -strength), 0, 255))
             return (r2, g2, b2)

        for fam in family_keys:
            palette[simulate_tile_color(fam)] = fam
            
        return VisualContext(img, coords_map, palette)

    def crop_and_decode(self, family: str) -> Tuple[Optional[Image.Image], List[str]]:
        """
        Tool: Look at a family's bbox, return the image crop and list of found sub-families.
        """
        if family not in self.context.coords: return None, []
        meta = self.context.coords[family]
        x, y, w, h = meta["bbox"]
        
        # Validations
        if w <= 0 or h <= 0: return None, []
        
        crop = self.context.image.crop((x, y, x + w, y + h))
        
        found_families = set()
        HEADER_H, TILE_SIZE = 24, 16
        
        current_y = HEADER_H
        while current_y < h - TILE_SIZE: 
            current_x = 0
            while current_x < w:
                try:
                    pixel = crop.getpixel((current_x, current_y))
                    if pixel in self.context.palette:
                        decoded = self.context.palette[pixel]
                        if decoded not in ["PAD", "SEP", family]:
                            found_families.add(decoded)
                except: pass
                current_x += TILE_SIZE
            current_y += TILE_SIZE
            
        return crop, list(found_families)

# --- Tool 2: Composer (The Artist) ---

class Composer:
    def __init__(self):
        self.crops: List[Tuple[Image.Image, str]] = []

    def add_thought(self, image: Image.Image, label: str):
        self.crops.append((image, label))

    def compose(self, output_path: str):
        print(f"🎨 Composer: Stitching {len(self.crops)} visual thoughts...")
        if not self.crops: return

        # Shelf Algorithm
        MAX_WIDTH = 2048 
        positions = []
        current_x, current_y = 0, 0
        row_h = 0
        total_w, total_h = 0, 0
        PAD = 20
        
        for img, label in self.crops:
            w, h = img.size
            if current_x + w > MAX_WIDTH:
                current_y += row_h + PAD
                current_x = 0
                row_h = 0
            
            positions.append((img, current_x, current_y, label))
            current_x += w + PAD
            row_h = max(row_h, h)
            total_w = max(total_w, current_x)
            
        total_h = current_y + row_h + PAD
        total_w = max(total_w + 200, 1024)

        canvas = Image.new("RGB", (total_w, total_h), (40, 44, 52))
        draw = ImageDraw.Draw(canvas)
        
        try: font = ImageFont.truetype(FONT_PATH, 20)
        except: font = ImageFont.load_default()

        for img, x, y, label in positions:
            draw.rectangle([x-2, y-2, x+img.width+2, y+img.height+2], fill=(20,20,20))
            canvas.paste(img, (x, y))
            draw.text((x, y - 25), label, fill=(200, 200, 200), font=font)
            
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        canvas.save(output_path)
        print(f"✅ Final Composition saved: {output_path}")


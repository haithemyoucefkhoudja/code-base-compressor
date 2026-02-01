"""
Visual RAG Workflow Tools
=========================
Provides the visual inspection and composition capabilities for the Agent.
"""

import os
import json
import hashlib
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
from PIL import Image, ImageDraw, ImageFont
import io

# Configuration Constants
ATLAS_PATH = r"c:\Users\haithem-yk\Desktop\Projects\reposoul-python-job\repo_patterns_tiles.png"
COORDS_PATH = r"c:\Users\haithem-yk\Desktop\Projects\reposoul-python-job\repo_patterns_tiles.coords.json"
MAP_PATH = r"c:\Users\haithem-yk\Desktop\Projects\reposoul-python-job\repo_patterns_tiles.map.json"
VOCAB_PATH = r"c:\Users\haithem-yk\Desktop\Projects\reposoul-python-job\repo_patterns_tiles.vocab.json"
FONT_PATH = "arial.ttf"

# --- Helper: Color Logic ---

def _hash_bytes(s: str) -> bytes:
    return hashlib.sha256(s.encode("utf-8")).digest()

def get_family_color(family: str) -> Tuple[int, int, int]:
    """Replicates the color generation logic from tiles.py."""
    if family == "PAD": return (255, 255, 255)
    if family == "SEP": return (0, 0, 0)
    
    h = _hash_bytes(family)
    r, g, b = h[0], h[1], h[2]
    r = int(40 + (r / 255) * 175)
    g = int(40 + (g / 255) * 175)
    b = int(40 + (b / 255) * 175)
    return (r, g, b)

# --- Data Classes ---

@dataclass
class VisualContext:
    image: Image.Image
    coords: Dict[str, Dict]
    palette: Dict[Tuple[int, int, int], str]

@dataclass
class InspectionResult:
    """Result of inspecting a component's visual tile."""
    family: str
    image_bytes: bytes
    neighbors: List[str]
    color_analysis: Dict[str, int]  # family -> pixel count
    density: str  # "sparse", "medium", "dense"

# --- Tool 1: Visual Decoder (The Eyes) ---

class VisualDecoder:
    def __init__(self, atlas_path: str = ATLAS_PATH, coords_path: str = COORDS_PATH, map_path: str = MAP_PATH):
        self.atlas_path = atlas_path
        self.coords_path = coords_path
        self.map_path = map_path
        self.context = self._initialize_context()
        
    def _initialize_context(self) -> VisualContext:
        print("👁️ VisualDecoder: Loading Atlas and calibrating palette...")
        if not os.path.exists(self.atlas_path): 
            raise FileNotFoundError(self.atlas_path)
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
        Inspect a single family's bbox, return the image crop and list of found sub-families.
        """
        if family not in self.context.coords: 
            return None, []
        meta = self.context.coords[family]
        x, y, w, h = meta["bbox"]
        
        if w <= 0 or h <= 0: 
            return None, []
        
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
                except: 
                    pass
                current_x += TILE_SIZE
            current_y += TILE_SIZE
            
        return crop, list(found_families)

    def inspect(self, family: str) -> Optional[InspectionResult]:
        """
        Full inspection of a component - returns structured data.
        """
        crop, neighbors = self.crop_and_decode(family)
        if not crop:
            return None
            
        # Analyze color distribution
        color_counts: Dict[str, int] = {}
        HEADER_H, TILE_SIZE = 24, 16
        total_tiles = 0
        
        for y in range(HEADER_H, crop.height - TILE_SIZE, TILE_SIZE):
            for x in range(0, crop.width, TILE_SIZE):
                try:
                    pixel = crop.getpixel((x, y))
                    if pixel in self.context.palette:
                        fam = self.context.palette[pixel]
                        if fam not in ["PAD", "SEP"]:
                            color_counts[fam] = color_counts.get(fam, 0) + 1
                            total_tiles += 1
                except:
                    pass
        
        # Determine density
        if total_tiles < 20:
            density = "sparse"
        elif total_tiles < 100:
            density = "medium"
        else:
            density = "dense"
        
        # Convert to bytes
        buf = io.BytesIO()
        crop.save(buf, format='PNG')
        
        return InspectionResult(
            family=family,
            image_bytes=buf.getvalue(),
            neighbors=neighbors,
            color_analysis=color_counts,
            density=density
        )

    def bulk_inspect(self, families: List[str]) -> Tuple[bytes, List[InspectionResult]]:
        """
        Bulk inspection - inspect multiple families and return a stitched grid image.
        Returns (stitched_image_bytes, list of individual results).
        """
        results: List[InspectionResult] = []
        crops: List[Tuple[Image.Image, str]] = []
        
        for family in families:
            result = self.inspect(family)
            if result:
                results.append(result)
                # Re-get crop for stitching
                crop, _ = self.crop_and_decode(family)
                if crop:
                    crops.append((crop, family))
        
        if not crops:
            return b"", results
        
        # Stitch into grid
        stitched = self._stitch_grid(crops)
        buf = io.BytesIO()
        stitched.save(buf, format='PNG')
        
        return buf.getvalue(), results

    def _stitch_grid(self, crops: List[Tuple[Image.Image, str]], max_cols: int = 3) -> Image.Image:
        """Create a labeled grid of component crops."""
        if not crops:
            return Image.new("RGB", (100, 100), (40, 44, 52))
        
        PAD = 10
        LABEL_H = 30
        
        # Calculate dimensions
        max_w = max(c[0].width for c in crops)
        max_h = max(c[0].height for c in crops)
        
        cols = min(len(crops), max_cols)
        rows = (len(crops) + cols - 1) // cols
        
        total_w = cols * (max_w + PAD) + PAD
        total_h = rows * (max_h + LABEL_H + PAD) + PAD
        
        canvas = Image.new("RGB", (total_w, total_h), (40, 44, 52))
        draw = ImageDraw.Draw(canvas)
        
        try:
            font = ImageFont.truetype(FONT_PATH, 16)
        except:
            font = ImageFont.load_default()
        
        for i, (crop, label) in enumerate(crops):
            col = i % cols
            row = i // cols
            
            x = PAD + col * (max_w + PAD)
            y = PAD + row * (max_h + LABEL_H + PAD)
            
            # Draw label
            draw.text((x, y), label[:30], fill=(200, 200, 200), font=font)
            
            # Draw border and paste
            y += LABEL_H
            draw.rectangle([x-2, y-2, x+crop.width+2, y+crop.height+2], outline=(100, 100, 100))
            canvas.paste(crop, (x, y))
        
        return canvas


# --- Tool 2: Composer (The Artist) ---

class Composer:
    """Collects and composes visual thoughts into a trace."""
    
    def __init__(self):
        self.crops: List[Tuple[Image.Image, str]] = []

    def add_thought(self, image: Image.Image, label: str):
        self.crops.append((image, label))

    def compose(self, output_path: str):
        print(f"🎨 Composer: Stitching {len(self.crops)} visual thoughts...")
        if not self.crops: 
            return

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
        
        try: 
            font = ImageFont.truetype(FONT_PATH, 20)
        except: 
            font = ImageFont.load_default()

        for img, x, y, label in positions:
            draw.rectangle([x-2, y-2, x+img.width+2, y+img.height+2], fill=(20,20,20))
            canvas.paste(img, (x, y))
            draw.text((x, y - 25), label, fill=(200, 200, 200), font=font)
            
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        canvas.save(output_path)
        print(f"✅ Final Composition saved: {output_path}")


# --- Tool 3: Vocabulary Index ---

class VocabularyIndex:
    """Searchable vocabulary from the codebase."""
    
    def __init__(self, vocab_path: str = VOCAB_PATH):
        with open(vocab_path, 'r') as f:
            raw = json.load(f)
            self.vocab = list(raw.keys()) if isinstance(raw, dict) else raw
        print(f"📚 Vocabulary loaded: {len(self.vocab)} families")
    
    def search(self, concept: str) -> List[str]:
        """Substring search in vocabulary."""
        concept = concept.strip().lower()
        matches = [k for k in self.vocab if concept in k.lower()]
        matches.sort(key=len)
        return matches[:10]
    
    def bulk_search(self, concepts: List[str]) -> Dict[str, List[str]]:
        """Search multiple concepts at once."""
        results = {}
        for concept in concepts:
            results[concept] = self.search(concept)
        return results
    
    def get_all(self) -> List[str]:
        """Return full vocabulary."""
        return self.vocab.copy()

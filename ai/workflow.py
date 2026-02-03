"""
Visual RAG Workflow Tools
=========================
Provides the visual inspection and composition capabilities for the Agent.
"""

import os
import json
import hashlib
import glob
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from PIL import Image, ImageDraw, ImageFont
import io

# Default Configuration (can be overridden via constructor)
DEFAULT_TILES_DIR = None  # Must be set explicitly
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
    # image_bytes: bytes
    neighbors: List[str]
    color_analysis: Dict[str, int]  # family -> pixel count
    density: str  # "sparse", "medium", "dense"
    props: List[str]

# --- Tool 1: Visual Decoder (The Eyes) ---

class VisualDecoder:
    def __init__(self, tiles_dir: str):
        """
        Initialize VisualDecoder from a tiles directory.
        
        Expected directory structure:
        tiles_dir/
            tiles.png OR tiles_1.png, tiles_2.png, ...
            tiles.coords.json
            tiles.vocab.json
            map.json
        
        Also requires patterns.json in parent directory.
        """
        self.tiles_dir = tiles_dir
        
        # Discover paths
        self.atlas_paths = self._discover_tile_images()
        self.coords_path = os.path.join(tiles_dir, "tiles.coords.json")
        self.map_path = os.path.join(tiles_dir, "map.json")
        self.vocab_path = os.path.join(tiles_dir, "tiles.vocab.json")
        
        # Patterns file is in parent directory with repo name
        parent_dir = os.path.dirname(tiles_dir)
        repo_name = os.path.basename(tiles_dir).replace("_tiles", "")
        self.patterns_path = os.path.join(parent_dir, f"{repo_name}_patterns.json")
        
        # Load patterns registry
        if os.path.exists(self.patterns_path):
            with open(self.patterns_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {}
    
        registry = {}
    
        def register(name, src, kind, props):
            if not name: return
            if not src: src = "unknown"
            key = f"{src}::{name}"
            registry[key] = {"name": name, "source": src, "type": kind, "props": props}
            
        for p in data.get("call_patterns", []): register(p.get("chain"), p.get("source_import"), "call", [])
        for p in data.get("jsx_patterns", []): register(p.get("component"), p.get("source_import"), "jsx", p.get("common_props"))
        for p in data.get("constant_patterns", []): register(p.get("constant"), p.get("source_import"), "const", [])
        for p in data.get("component_definitions", []): register(p.get("component"), p.get("file"), "def", p.get("props"))
        for p in data.get("reference_patterns", []): register(p.get("name"), p.get("source_import"), "ref", [])
        self.registry = registry
        
        self.context = self._initialize_context()
    
    def _discover_tile_images(self) -> List[str]:
        """Find all tile images in the directory."""
        # Check for single tile
        single_tile = os.path.join(self.tiles_dir, "tiles.png")
        if os.path.exists(single_tile):
            return [single_tile]
        
        # Check for numbered tiles
        pattern = os.path.join(self.tiles_dir, "tiles_*.png")
        tiles = sorted(glob.glob(pattern))
        
        if not tiles:
            raise FileNotFoundError(f"No tile images found in {self.tiles_dir}")
        
        return tiles
    
    def get_legend_path(self) -> str:
        """Return path to the legend image."""
        return os.path.join(self.tiles_dir, "tiles_legend.png")
        
    def _initialize_context(self) -> VisualContext:
        print("👁️ VisualDecoder: Loading Atlas and calibrating palette...")
        
        # Load and stitch all tile images
        tile_images = []
        for tile_path in self.atlas_paths:
            if not os.path.exists(tile_path): 
                raise FileNotFoundError(tile_path)
            tile_images.append(Image.open(tile_path).convert("RGB"))
        
        # Stitch tiles vertically (they were split by height)
        if len(tile_images) == 1:
            img = tile_images[0]
        else:
            total_width = tile_images[0].width
            total_height = sum(t.height for t in tile_images)
            img = Image.new("RGB", (total_width, total_height))
            y_offset = 0
            for tile in tile_images:
                img.paste(tile, (0, y_offset))
                y_offset += tile.height
            print(f"   Stitched {len(tile_images)} tiles -> {total_width}x{total_height}")
        
        with open(self.coords_path, 'r') as f:
            coords_list = json.load(f)
            # Handle coords that may have tile_index (for split images)
            # Reconstruct original y coordinates
            coords_map = {}
            for item in coords_list:
                family = item["family"]
                if family in coords_map:
                    continue  # Skip duplicates from split tiles
                # If tile_index present, use original_y if available
                if "original_y" in item:
                    item["bbox"][1] = item["original_y"]
                coords_map[family] = item
            
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

    def _normalize_family(self, family: str) -> str:
        """Standardize family names for robust lookup."""
        if not family: return family
        
        # 1. Clean up outer quotes and whitespace
        cleaned = family.strip().strip('"').strip("'")
        
        # 2. Normalize path separators to backslashes
        normalized = cleaned.replace('/', '\\')
        
        # 3. Direct match
        if normalized in self.context.coords:
            return normalized
            
        # 4. Handle mixed separators (some tools might use both)
        # Already handled by .replace('/', '\\') but let's be sure
        
        # 5. Handle internal quoting inconsistencies (e.g., "source"::name)
        if '::' in normalized:
            source, name = normalized.split('::', 1)
            # Try variations of the source part
            variations = [
                f'"{source}"::{name}',    # Add quotes
                f'{source.strip('"')}::{name}' # Remove quotes
            ]
            for var in variations:
                if var in self.context.coords:
                    return var
                    
        # 6. Try adding/removing quotes from the entire string
        if f'"{normalized}"' in self.context.coords:
            return f'"{normalized}"'
            
        return normalized

    def crop_and_decode(self, family: str) -> Tuple[Optional[Image.Image], List[str]]:
        """
        Inspect a single family's bbox, return the image crop and list of found sub-families.
        """
        family = self._normalize_family(family)
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

    def inspect(self, family: str) -> Optional[Tuple[bytes,InspectionResult]]:
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
        
        # Normalize family for registry lookup
        norm_family = self._normalize_family(family)
        reg_entry = self.registry.get(norm_family) or {}
        
        return buf.getvalue(), InspectionResult(
            props=reg_entry.get('props') or [],
            family=family,
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
            res = self.inspect(family)

            if res:
                _,result  = res
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
        
        canvas = Image.new("RGB", (total_w, total_h), 0)
        draw = ImageDraw.Draw(canvas)
        
        
        for i, (crop, _) in enumerate(crops):
            col = i % cols
            row = i // cols
            x = PAD + col * (max_w + PAD)
            y = PAD + row * (max_h + LABEL_H + PAD)
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

        canvas = Image.new("RGB", (total_w, total_h),0)
        draw = ImageDraw.Draw(canvas)
        
        # try: 
        #     font = ImageFont.truetype(FONT_PATH, 20)
        # except: 
        #     font = ImageFont.load_default()

        for img, x, y, label in positions:
            draw.rectangle([x-2, y-2, x+img.width+2, y+img.height+2], fill=(20,20,20))
            canvas.paste(img, (x, y))
            # draw.text((x, y - 25), label, fill=(200, 200, 200), font=font)
            
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        canvas.save(output_path)
        print(f"✅ Final Composition saved: {output_path}")


# --- Tool 3: Vocabulary Index ---

class VocabularyIndex:
    """Searchable vocabulary from the codebase."""
    
    def __init__(self, tiles_dir: str):
        vocab_path = os.path.join(tiles_dir, "tiles.vocab.json")
        
        with open(vocab_path, 'r') as f:
            raw = json.load(f)
            self.vocab = list(raw.keys()) if isinstance(raw, dict) else raw
        print(f"📚 Vocabulary loaded: {len(self.vocab)} families")
        
    def get_all(self) -> List[str]:
        """Return full vocabulary."""
        return self.vocab.copy()

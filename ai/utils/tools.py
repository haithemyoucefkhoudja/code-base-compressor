"""
Visual RAG Workflow Tools
=========================
Provides the visual inspection and composition capabilities for the Agent.
"""

import os
import json
import hashlib
import glob
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from PIL import Image, ImageDraw
import io
import math

# Disable Image Size Limit for massive datasets
Image.MAX_IMAGE_PIXELS = None

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
    image: Optional[Image.Image]
    coords: Dict[str, Dict]
    palette: Dict[Tuple[int, int, int], str]

@dataclass
class InspectionResult:
    """Result of inspecting a component's visual tile."""
    family: str
    density: str # sparse, medium, dense
    color_analysis: Dict[str, int] # Now represents CHILDREN (contained elements)
    most_frequent_parents: Dict[str, int] # NEW: Represents PARENTS (usage context)
    props: List[str]
    # Detailed Context
    prop_types: Optional[Dict[str, Any]] = None
    return_type: Optional[str] = None
    variations: Optional[List[Dict[str, Any]]] = None
    signature: Optional[Dict[str, Any]] = None
    shapes: Optional[List[Dict[str, Any]]] = None
    subs:Optional[List[str]] = None

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
        self.element_analysis_path = os.path.join(tiles_dir, "tiles.element_analysis.json")
        
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
    
        self.sub_to_parents = {}
    
        def register(name, src, kind, props, prop_types=None, ret_type=None, variations=None, sig=None, shapes=None, subs=None):
            if not name: return None
            if not src: src = "unknown"
            
            # Disambiguate name with kind (Matches tiles.py and VocabularyIndex logic)
            distinct_name = name
            if kind == "jsx": distinct_name = f"{name}::JSX"
            elif kind == "call": distinct_name = f"{name}::CALL"
            elif kind == "const": distinct_name = f"{name}::CONST"
            elif kind == "def": distinct_name = f"{name}::DEF"
            
            key = f"{src}::{distinct_name}"
            
            new_data = {
                "name": distinct_name, 
                "source": src, 
                "type": kind, 
                "props": props or [],
                "prop_types": prop_types or {},
                "return_type": ret_type or "",
                "variations": variations or [],
                "signature": sig or {},
                "shapes": shapes or [],
                "subs": subs or []
            }

            if key in registry:
                # Merge logic: Prioritize non-empty/richer data
                old = registry[key]
                for k, v in new_data.items():
                    if v and not old.get(k):
                        old[k] = v
                    elif isinstance(v, list) and isinstance(old.get(k), list):
                        # Combine lists without duplicates
                        for item in v:
                            if item not in old[k]: old[k].append(item)
                    elif isinstance(v, dict) and isinstance(old.get(k), dict):
                        # Shallow merge dicts
                        old[k].update({mk: mv for mk, mv in v.items() if mv})
                return key

            registry[key] = new_data
            return key
            
        for p in data.get("call_patterns", []): 
            sig = p.get('signature') or {}
            subs = p.get("sub_patterns", [])
            hkey = register(p.get("chain"), p.get("source_import"), "call", [], 
                     variations=p.get('call_variations'), 
                     sig=sig,
                     subs=subs)
            
            # Track sub-patterns
            if hkey:
                for sub in subs:
                    skey = register(sub, p.get("source_import"), "call", [])
                    if skey and skey != hkey:
                        if skey not in self.sub_to_parents: self.sub_to_parents[skey] = []
                        if hkey not in self.sub_to_parents[skey]:
                            self.sub_to_parents[skey].append(hkey)
                     
        for p in data.get("jsx_patterns", []): 
            subs = p.get("sub_components", [])
            hkey = register(p.get("component"), p.get("source_import"), "jsx", p.get("common_props"),shapes=p.get('shapes'), subs=subs)
            
            # Track sub-components
            if hkey:
                for sub in subs:
                    skey = register(sub, p.get("source_import"), "jsx", [])
                    if skey and skey != hkey:
                        if skey not in self.sub_to_parents: self.sub_to_parents[skey] = []
                        if hkey not in self.sub_to_parents[skey]:
                            self.sub_to_parents[skey].append(hkey)
                     
        for p in data.get("constant_patterns", []): 
            register(p.get("constant"), p.get("source_import"), "const", [])
            
        for p in data.get("component_definitions", []): 
            register(p.get("component"), p.get("file"), "def", p.get("props"),
                     prop_types=p.get('prop_types'), ret_type=p.get('return_type'))
                     
        for p in data.get("reference_patterns", []): 
            register(p.get("name"), p.get("source_import"), "ref", [])
        self.registry = registry

        # Load element analysis
        self.element_analysis = {}
        if os.path.exists(self.element_analysis_path):
            with open(self.element_analysis_path, "r", encoding="utf-8") as f:
                self.element_analysis = json.load(f)
        
        self.context = self._initialize_context()
    
    def _discover_tile_images(self) -> List[str]:
        """Find all tile images in the directory."""
        # Check for single tile
        single_tile = os.path.join(self.tiles_dir, "tiles.png")
        if os.path.exists(single_tile):
            return [single_tile]
        
        # Check for numbered tiles
        pattern = os.path.join(self.tiles_dir, "tiles_*.png")
        all_matches = glob.glob(pattern)
        
        # STRICTLY exclude legend files
        tiles = [p for p in all_matches if "_legend" not in os.path.basename(p)]
        
        if not tiles:
            # Fallback: maybe it's just tiles.png but glob missed it? (Covered above)
            raise FileNotFoundError(f"No tile images found in {self.tiles_dir}")
        
        # Natural sort or index-based map for indexed tiles
        def get_tile_idx(path):
            name = os.path.basename(path)
            # Expecting tiles_N.png
            try:
                # Remove 'tiles_' and '.png' to get N
                num_part = name.replace("tiles_", "").split(".")[0]
                return int(num_part)
            except:
                return 999999
        
        indexed_tiles = sorted(tiles, key=get_tile_idx)
        return indexed_tiles
    
    def get_legend_paths(self) -> List[str]:
        """Return paths to all legend images (split or single)."""
        pattern = os.path.join(self.tiles_dir, "tiles*legend*.png")
        legends = sorted(glob.glob(pattern))
        if not legends:
            # Fallback path if not found (though glob handles list)
            fallback = os.path.join(self.tiles_dir, "tiles_legend.png")
            if os.path.exists(fallback): return [fallback]
            return []
        return legends
        
    def _initialize_context(self) -> VisualContext:
        print("👁️ VisualDecoder: Loading Atlas and calibrating palette...")
        
        # --- Load Manifest (if available) for tile-to-family mapping ---
        manifest_path = os.path.join(self.tiles_dir, "tiles.manifest.json")
        self.manifest = None
        self.family_to_tile = {}  # family -> tile_index
        
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r') as f:
                self.manifest = json.load(f)
            print(f"   Manifest: {self.manifest.get('total_tiles', 1)} tiles")
            
            # Build reverse index: family -> tile_index
            for tile_idx_str, tile_info in self.manifest.get("tiles", {}).items():
                tile_idx = int(tile_idx_str)
                for fam in tile_info.get("families", []):
                    if fam not in self.family_to_tile:
                        self.family_to_tile[fam] = tile_idx
        
        # --- Lazy Tile Image Cache ---
        # Store tile paths and load on demand
        self.tile_images_cache: Dict[int, Image.Image] = {}
        self.tile_paths = {i: path for i, path in enumerate(self.atlas_paths)}
        
        # We NO LONGER stitch tiles vertically to avoid memory bombs.
        # Instead, we use lazy loading and per-tile cropping.
        img = None # No stitched image by default
        print(f"   Using lazy loading for {len(self.atlas_paths)} tiles")
        
        with open(self.coords_path, 'r') as f:
            coords_list = json.load(f)
            # Handle coords that may have tile_index (for split images)
            # Build coords_map with tile_index preserved
            coords_map = {}
            for item in coords_list:
                family = item["family"]
                if family in coords_map:
                    continue  # Skip duplicates from split tiles
                
                # Determine tile index (prefer coords, fallback to manifest)
                tile_idx = item.get("tile_index")
                if tile_idx is None:
                    tile_idx = self.family_to_tile.get(family, 0)
                
                # Store tile_index in the item for later use
                item["_tile_index"] = tile_idx
                
                # IMPORTANT: Store the tile-local y BEFORE overwriting with stitched y
                item["_tile_local_bbox"] = item["bbox"].copy()  # Keep tile-local coords
                
                # Overwrite bbox with stitched coords for backward compatibility
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
    
    def _get_tile_image(self, tile_index: int) -> Optional[Image.Image]:
        """Get a specific tile image (lazy loading). Indices are 0-based relative to atlas_paths."""
        if tile_index in self.tile_images_cache:
            return self.tile_images_cache[tile_index]
        
        # Map 0-based index to tile path
        # Note: if manifest says tile 0 is tiles_1.png, and atlas_paths is sorted by N, 
        # then atlas_paths[0] should be tiles_1.png.
        if 0 <= tile_index < len(self.atlas_paths):
            path = self.atlas_paths[tile_index]
            img = Image.open(path).convert("RGB")
            self.tile_images_cache[tile_index] = img
            return img
        
        return None

    def _normalize_family(self, family: str) -> str:
        """Standardize family names for robust lookup with fuzzy matching."""
        if not family: 
            return family
        
        # 0. Try exact match first (most common case)
        if family in self.context.coords:
            return family
        
        # 1. Build candidate variations
        candidates = []
        
        # Original with stripped whitespace
        stripped = family.strip()
        candidates.append(stripped)
        
        # Try with/without outer quotes
        if stripped.startswith('"') and stripped.endswith('"'):
            candidates.append(stripped[1:-1])  # Remove quotes
        else:
            candidates.append(f'"{stripped}"')  # Add quotes
        
        # Try swapping path separators (both directions)
        for c in list(candidates):
            candidates.append(c.replace('\\', '/'))
            candidates.append(c.replace('/', '\\'))
        
        # Handle :: splitting for source::name patterns
        if '::' in family:
            parts = family.split('::', 1)
            source, name = parts[0].strip(), parts[1].strip()
            
            # Source variations: with/without quotes and path separators
            source_vars = [source]
            if source.startswith('"'):
                source_vars.append(source[1:])  # Remove leading quote
            else:
                source_vars.append(f'"{source}')  # Add leading quote
            if source.endswith('"'):
                source_vars.append(source[:-1])  # Remove trailing quote
            else:
                source_vars.append(f'{source}"')  # Add trailing quote
            
            # Path separator variants for source
            for sv in list(source_vars):
                source_vars.append(sv.replace('\\', '/'))
                source_vars.append(sv.replace('/', '\\'))
            
            # Combine source variations with name
            for sv in source_vars:
                candidates.append(f'{sv}::{name}')
        
        # 2. Try each candidate
        for candidate in candidates:
            if candidate in self.context.coords:
                return candidate
        
        # 3. Last resort: substring match on family key
        search_key = family.replace('\\', '/').replace('"', '').strip()
        for key in self.context.coords:
            key_clean = key.replace('\\', '/').replace('"', '').strip()
            if search_key in key_clean or key_clean in search_key:
                return key
        
        # 4. Give up, return original
        return family

    def crop_and_decode(self, family: str) -> Optional[Image.Image]:
        """
        Inspect a single family's bbox, return the image crop and list of found sub-families.
        Uses per-tile coordinates when manifest is available for efficient memory usage.
        """
        family = self._normalize_family(family)
        if family not in self.context.coords: 
            return None
        meta = self.context.coords[family]
        x, y, w, h = meta["bbox"]
        
        if w <= 0 or h <= 0: 
            return None
        
        # Determine which tile to use
        tile_index = meta.get("_tile_index", 0)
        
        # Strictly use per-tile image and tile-local coordinates
        source_image = self._get_tile_image(tile_index)
        
        if source_image:
            # Use tile-local coordinates if available (robustness)
            if "_tile_local_bbox" in meta:
                 lx, ly, lw, lh = meta["_tile_local_bbox"]
                 crop = source_image.crop((lx, ly, lx + lw, ly + lh))
            else:
                 # Fallback: assume bbox is already local (from tiles.py)
                 crop = source_image.crop((x, y, x + w, y + h))
            return crop

    def inspect(self, family: str) -> Optional[Tuple[bytes,InspectionResult]]:
        """
        Full inspection of a component - returns structured data.
        """
        crop = self.crop_and_decode(family)
        if not crop:
            return None
            
        # Lookup pre-computed analysis
        children_counts = {}
        parent_counts = {}
        density = "unknown" # Default density

        norm_family = self._normalize_family(family) # Normalize early for analysis lookup
        
        if norm_family in self.element_analysis:
            data = self.element_analysis[norm_family]
            children_counts = data.get("children", {})
            parent_counts = data.get("parents", {})
            
            # Simple heuristic for density based on child count
            total_children = sum(children_counts.values())
            if total_children < 5: density = "sparse"
            elif total_children < 20: density = "medium"
            else: density = "dense"
        
        # Convert crop to bytes
        buf = io.BytesIO()
        crop.save(buf, format='PNG')
        image_bytes = buf.getvalue()
        
        # Normalize family for registry lookup (already done, but keep for clarity)
        reg_entry = self.registry.get(norm_family) or {}
        
        # If this is a sub-item, link to parent metadata for richer analysis
        if not reg_entry.get('props') and norm_family in self.sub_to_parents:
            # Take first parent as primary context
            parent_key = self.sub_to_parents[norm_family][0]
            parent_entry = self.registry.get(parent_key, {})
            # Merge or surface parent info
            reg_entry = parent_entry.copy()
            reg_entry['is_sub_item'] = True
            reg_entry['parent_key'] = parent_key
        
        # Extract metadata from registry
        props = reg_entry.get("props", [])
        prop_types = reg_entry.get("prop_types")
        return_type = reg_entry.get("return_type")
        variations = reg_entry.get("variations")
        signature = reg_entry.get("signature")
        shapes = reg_entry.get("shapes")
        subs = reg_entry.get("subs")

        return image_bytes, InspectionResult(
            family=family,
            density=density,
            color_analysis=children_counts,
            most_frequent_parents=parent_counts,
            props=props,
            prop_types=prop_types,
            return_type=return_type,
            variations=variations,
            signature=signature,
            shapes=shapes,
            subs=subs
        )

    def bulk_inspect(self, families: List[str]) -> Tuple[List[bytes], List[InspectionResult]]:
        """
        Bulk inspection - inspect multiple families and return a list of stitched grid images.
        Returns (list_of_stitched_image_bytes, list of individual results).
        """
        results: List[InspectionResult] = []
        crops: List[Tuple[Image.Image, str]] = []
        
        for family in families:
            res = self.inspect(family)

            if res:
                _,result  = res
                results.append(result)
                # Re-get crop for stitching
                crop = self.crop_and_decode(family)
                if crop:
                    crops.append((crop, family))
        
        if not crops:
            return [], results
        
        # Stitch into grid chunks
        stitched_images = self._stitch_grid(crops)
        
        byte_chunks = []
        for img in stitched_images:
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            byte_chunks.append(buf.getvalue())
        
        return byte_chunks, results

    def _stitch_grid(self, crops: List[Tuple[Image.Image, str]], max_width: int = 10000, max_dimension: int = 10000) -> List[Image.Image]:
        """
        Create grids of component crops using PAGE-SAFE BOOKSHELF packing.
        Ported from tiles.py: items are NEVER split across pages.
        If an item would cross a page boundary, it's moved to the next page.
        """
        if not crops:
            return [Image.new("RGB", (100, 100), (30, 30, 30))]
        
        PAD = 10
        
        # --- Phase 1: Page-safe placement (tiles.py logic, lines 356-411) ---
        current_shelf_x = PAD
        current_shelf_h = 0
        current_shelf_items = []  # Items on the current shelf row
        
        placed_items = []  # Final list of (img, x, y, label)
        
        current_y = PAD
        page_limit = max_dimension
        total_w = 0
        
        for crop, label in crops:
            w, h = crop.size
            
            # Check if item fits on current shelf horizontally
            if current_shelf_x + w + PAD <= max_width:
                item_bottom = current_y + h
                
                if item_bottom > page_limit:
                    # PAGE BREAK: flush current shelf, jump to next page
                    for item in current_shelf_items:
                        placed_items.append(item)
                    
                    current_y = page_limit + PAD
                    page_limit += max_dimension
                    
                    current_shelf_x = PAD
                    current_shelf_h = 0
                    current_shelf_items = []
                    
                    # Place item on the new page
                    current_shelf_items.append((crop, current_shelf_x, current_y, label))
                    current_shelf_x += w + PAD
                    current_shelf_h = h
                else:
                    # Safe to place on current shelf
                    current_shelf_items.append((crop, current_shelf_x, current_y, label))
                    current_shelf_x += w + PAD
                    current_shelf_h = max(current_shelf_h, h)
            else:
                # NEW LINE: flush current shelf, move down
                for item in current_shelf_items:
                    placed_items.append(item)
                
                current_y += current_shelf_h + PAD
                current_shelf_x = PAD
                current_shelf_h = 0
                current_shelf_items = []
                
                # Check page boundary for new line
                if current_y + h > page_limit:
                    current_y = page_limit + PAD
                    page_limit += max_dimension
                
                current_shelf_items.append((crop, current_shelf_x, current_y, label))
                current_shelf_x += w + PAD
                current_shelf_h = h
            
            total_w = max(total_w, current_shelf_x)
        
        # Flush remaining shelf items
        for item in current_shelf_items:
            placed_items.append(item)
        current_y += current_shelf_h + PAD
        
        # --- Phase 2: Render into page-safe tile images ---
        final_w = max(total_w, 100)
        final_h = current_y
        
        num_tiles = math.ceil(final_h / max_dimension)
        tiles = []
        
        for tile_idx in range(num_tiles):
            y_start = tile_idx * max_dimension
            y_end = min((tile_idx + 1) * max_dimension, final_h)
            tile_h = y_end - y_start
            
            tile_canvas = Image.new("RGB", (final_w, tile_h), (30, 30, 30))
            
            for img, x, y, label in placed_items:
                item_h = img.height
                item_y_end = y + item_h
                
                # Only paste items that belong to this tile
                if item_y_end > y_start and y < y_end:
                    paste_y = y - y_start
                    tile_canvas.paste(img, (x, paste_y))
            
            tiles.append(tile_canvas)
            
        return tiles


# --- Tool 2: Composer (The Artist) ---

class Composer:
    """Collects and composes visual thoughts into a trace."""
    
    def __init__(self):
        self.crops: List[Tuple[Image.Image, str]] = []

    def add_thought(self, image: Image.Image, label: str):
        self.crops.append((image, label))

    def compose(self, output_path: str, max_dimension: int = 10000):
        print(f"🎨 Composer: Stitching {len(self.crops)} visual thoughts...")
        if not self.crops: 
            return

        # Shelf Algorithm
        MAX_WIDTH = max_dimension 
        positions = []
        current_x, current_y = 0, 0
        row_h = 0
        total_w = 0
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
            
        final_h = current_y + row_h + PAD
        final_w = max(total_w + 200, 1024)

        need_split = final_h > max_dimension
        base_name = output_path.replace(".png", "")
        
        if not need_split:
            canvas = Image.new("RGB", (final_w, final_h), 0)
            for img, x, y, label in positions:
                canvas.paste(img, (x, y))
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            canvas.save(output_path)
            print(f"✅ Final Composition saved: {output_path}")
        else:
            num_tiles = math.ceil(final_h / max_dimension)
            print(f"Splitting trace into {num_tiles} tiles...")
            for tile_idx in range(num_tiles):
                y_start = tile_idx * max_dimension
                y_end = min((tile_idx + 1) * max_dimension, final_h)
                tile_h = y_end - y_start
                
                tile_canvas = Image.new("RGB", (final_w, tile_h), 0)
                
                for img, x, y, label in positions:
                    item_h = img.height
                    item_y_end = y + item_h
                    
                    if item_y_end > y_start and y < y_end:
                        paste_y = max(0, y - y_start)
                        crop_top = max(0, y_start - y)
                        crop_bottom = min(item_h, y_end - y)
                        
                        if crop_bottom > crop_top:
                            cropped_img = img.crop((0, crop_top, img.width, crop_bottom))
                            tile_canvas.paste(cropped_img, (x, paste_y))
                
                tile_path = f"{base_name}_{tile_idx + 1}.png"
                tile_canvas.save(tile_path)
                print(f"  Saved trace tile: {tile_path}")


# --- Tool 3: Vocabulary Index ---

class VocabularyIndex:
    """Searchable vocabulary from the codebase."""
    
    def __init__(self, tiles_dir: str):
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
        
        # Also load the flat vocab list for fallback/completeness
        vocab_path = os.path.join(tiles_dir, "tiles.vocab.json")
        if os.path.exists(vocab_path):
            with open(vocab_path, 'r') as f:
                raw = json.load(f)
                self.flat_vocab = list(raw.keys()) if isinstance(raw, dict) else raw
        else:
            self.flat_vocab = []

        self.sub_to_parents = {}

        def register(name, src, kind, props, prop_types=None, ret_type=None, variations=None, sig=None, shapes=None, subs=None):
            if not name: return None
            if not src: src = "unknown"
            
            # Disambiguate name with kind (Matches tiles.py logic)
            distinct_name = name
            if kind == "jsx": distinct_name = f"{name}::JSX"
            elif kind == "call": distinct_name = f"{name}::CALL"
            elif kind == "const": distinct_name = f"{name}::CONST"
            elif kind == "def": distinct_name = f"{name}::DEF"
            
            key = f"{src}::{distinct_name}"
            
            new_data = {
                "name": distinct_name, 
                "source": src, 
                "type": kind, 
                "props": props or [],
                "prop_types": prop_types or {},
                "return_type": ret_type or "",
                "variations": variations or [],
                "signature": sig or {},
                "shapes": shapes or [],
                "subs": subs or []
            }

            if key in registry:
                # Merge logic: Prioritize non-empty/richer data
                old = registry[key]
                for k, v in new_data.items():
                    if v and not old.get(k):
                        old[k] = v
                    elif isinstance(v, list) and isinstance(old.get(k), list):
                        for item in v:
                            if item not in old[k]: old[k].append(item)
                    elif isinstance(v, dict) and isinstance(old.get(k), dict):
                        old[k].update({mk: mv for mk, mv in v.items() if mv})
                return key

            registry[key] = new_data
            return key
            
        for p in data.get("call_patterns", []): 
            sig = p.get('signature') or {}
            subs = p.get("sub_patterns", [])
            hkey = register(p.get("chain"), p.get("source_import"), "call", [], 
                     variations=p.get('call_variations'), 
                     sig=sig,
                     subs=subs)
            
            # Track sub-patterns
            if hkey:
                for sub in subs:
                    skey = register(sub, p.get("source_import"), "call", [])
                    if skey and skey != hkey:
                        if skey not in self.sub_to_parents: self.sub_to_parents[skey] = []
                        if hkey not in self.sub_to_parents[skey]:
                            self.sub_to_parents[skey].append(hkey)
                     
        for p in data.get("jsx_patterns", []): 
            subs = p.get("sub_components", [])
            hkey = register(p.get("component"), p.get("source_import"), "jsx", p.get("common_props"),shapes=p.get('shapes'), subs=subs)
            
            # Track sub-components
            if hkey:
                for sub in subs:
                    skey = register(sub, p.get("source_import"), "jsx", [])
                    if skey and skey != hkey:
                        if skey not in self.sub_to_parents: self.sub_to_parents[skey] = []
                        if hkey not in self.sub_to_parents[skey]:
                            self.sub_to_parents[skey].append(hkey)
                     
        for p in data.get("constant_patterns", []): 
            register(p.get("constant"), p.get("source_import"), "const", [])
            
        for p in data.get("component_definitions", []): 
            register(p.get("component"), p.get("file"), "def", p.get("props"),
                     prop_types=p.get('prop_types'), ret_type=p.get('return_type'))
                     
        for p in data.get("reference_patterns", []): 
            register(p.get("name"), p.get("source_import"), "ref", [])
        
        self.registry = registry
        
        # Build inverse map: parent -> [children]
        self.parent_to_children = {}
        for child_key, parent_keys in self.sub_to_parents.items():
            for pkey in parent_keys:
                if pkey not in self.parent_to_children:
                    self.parent_to_children[pkey] = []
                if child_key not in self.parent_to_children[pkey]:
                    self.parent_to_children[pkey].append(child_key)
        
        self.vocab = list(self.flat_vocab)
        print(f"📚 Vocabulary loaded: {len(self.vocab)} | {len(self.parent_to_children)} families")
        
    def get_all(self) -> List[str]:
        """Return full vocabulary."""
        return self.vocab.copy()
        
    def get_entry(self, family: str) -> Dict:
        """Get rich metadata for a family."""
        return self.registry.get(family, {})

    def search(self, query: str, limit: int = 5, cutoff: float = 0.4) -> List[str]:
        """Fuzzy search for families matching the query. Prioritizes component name matches."""
        import difflib
        
        query_lower = query.lower()
        
        # 0. exact match in full vocab (fastest)
        matches = [v for v in self.vocab if query_lower in v.lower()]
        
        # 1. Check against component names (suffix after ::)
        # Create a mapping of {name: full_family} for candidates
        name_map = {}
        for v in self.vocab:
            parts = v.split('::')
            if len(parts) > 1:
                name = parts[1].strip()
                if name not in name_map:
                    name_map[name] = []
                name_map[name].append(v)
        
        # Fuzzy match on pure names first (high priority)
        fuzzy_names = difflib.get_close_matches(query, list(name_map.keys()), n=limit, cutoff=cutoff)
        
        for name in fuzzy_names:
            for full_v in name_map[name]:
                if full_v not in matches:
                    matches.append(full_v)
        
        # 2. Fuzzy match against full strings (fallback)
        if len(matches) < limit:
            remaining = limit - len(matches)
            # Filter out already found to avoid duplicates
            candidates = [v for v in self.vocab if v not in matches]
            fuzzy_full = difflib.get_close_matches(query, candidates, n=remaining, cutoff=cutoff)
            matches.extend(fuzzy_full)
        
        # 3. Deep family expansion (bidirectional)
        #    - If match is a parent: include parent + all children
        #    - If match is a child: include parent + all siblings
        #    - Limit applies to number of *families*, not individual items
        final_results = []
        seen = set()
        families_added = 0
        
        for m in matches:
            if m in seen:
                continue
            
            # Determine the root parent(s) for this match
            root_keys = []
            if m in self.sub_to_parents:
                # This is a child — its parents are the roots
                root_keys = self.sub_to_parents[m]
            elif m in self.parent_to_children:
                # This is itself a parent/root
                root_keys = [m]
            else:
                # Standalone item (no family)
                if m not in seen:
                    final_results.append(m)
                    seen.add(m)
                    families_added += 1
                if families_added >= limit:
                    break
                continue
            
            # Expand each root with its full family
            for root in root_keys:
                if root in seen:
                    continue
                    
                # Add the parent first
                final_results.append(root)
                seen.add(root)
                
                # Add all children of this parent
                for child in self.parent_to_children.get(root, []):
                    if child not in seen:
                        final_results.append(child)
                        seen.add(child)
                
                families_added += 1
                if families_added >= limit:
                    break
            
            if families_added >= limit:
                break
        
        return final_results

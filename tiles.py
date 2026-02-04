"""
tiles_fixed.py

- Dynamic Width: max(Text_Width, Data_Width) snapped to Tile Grid.
- RIGHT-ALIGNED SEPARATOR: The black end-of-row tile is pushed to the far right.
- Visuals: Full alignment between header width and token row width.
"""
from __future__ import annotations
import os
import sys
import json
import math
import hashlib
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional, Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Disable Image Size Limit for massive datasets
Image.MAX_IMAGE_PIXELS = None

# ----------------------------
# 1) Configuration
# ----------------------------

@dataclass(frozen=True)
class TileConfig:
    tile_size: int = 16               
    pad_family: str = "PAD"           
    sep_family: str = "SEP"           
    background: Tuple[int, int, int] = (30, 30, 30) 
    use_checksum_corner: bool = True
    max_dimension: int = 10000  # Max width/height before splitting

# ----------------------------
# 2) Deterministic glyph generator
# ----------------------------

def _hash_bytes(s: str) -> bytes:
    return hashlib.sha256(s.encode("utf-8")).digest()

def glyph_for_family(family: str, cfg: TileConfig) -> np.ndarray:
    if family == cfg.pad_family:
        tile = np.zeros((cfg.tile_size, cfg.tile_size, 3), dtype=np.uint8)
        tile[:] = 255
        return tile
    
    if family == cfg.sep_family:
        return np.zeros((cfg.tile_size, cfg.tile_size, 3), dtype=np.uint8)

    size = cfg.tile_size
    h = _hash_bytes(family)

    r, g, b = h[0], h[1], h[2]
    r = int(40 + (r / 255) * 175)
    g = int(40 + (g / 255) * 175)
    b = int(40 + (b / 255) * 175)

    tile = np.zeros((size, size, 3), dtype=np.uint8)
    tile[:, :, 0] = r
    tile[:, :, 1] = g
    tile[:, :, 2] = b

    mode = h[3] % 6
    strength = 40 + (h[4] % 80)

    r2 = np.clip(r + (strength if (h[5] & 1) else -strength), 0, 255)
    g2 = np.clip(g + (strength if (h[6] & 1) else -strength), 0, 255)
    b2 = np.clip(b + (strength if (h[7] & 1) else -strength), 0, 255)
    c2 = np.array([r2, g2, b2], dtype=np.uint8)

    yy, xx = np.mgrid[0:size, 0:size]
    mask = None

    if mode == 0: mask = (xx % 4) < 2
    elif mode == 1: mask = (yy % 4) < 2
    elif mode == 2: mask = ((xx // 2 + yy // 2) % 2) == 0
    elif mode == 3: mask = ((xx + yy) % 6) < 3
    elif mode == 4: mask = (xx == yy) | (xx == (size - 1 - yy))
    else: 
        tile[0:2,:,:] = c2
        tile[-2:,:,:] = c2
        tile[:,0:2,:] = c2
        tile[:,-2:,:] = c2
        
    if mask is not None: tile[mask] = c2

    if cfg.use_checksum_corner:
        corner = np.array([[h[8]&1, h[9]&1], [h[10]&1, h[11]&1]], dtype=np.uint8)
        cc = np.array([240, 240, 240], dtype=np.uint8) if (h[12] & 1) else np.array([15, 15, 15], dtype=np.uint8)
        for cy in range(2):
            for cx in range(2):
                if corner[cy, cx]: tile[cy, cx] = cc

    return tile

def generate_legend(unique_families: List[str], filename: str, cfg: TileConfig):
    families = sorted(list(unique_families))
    if not families: return

    try: font = ImageFont.truetype("arial.ttf", 14)
    except IOError: font = ImageFont.load_default()

    dummy_img = Image.new("RGB", (1, 1))
    dummy_draw = ImageDraw.Draw(dummy_img)
    
    max_text_w = 0
    for fam in families:
        fam_draw  = re.sub(r"[\n\t\r]+", " ", fam).strip()
        
        bbox = dummy_draw.textbbox((0, 0), fam_draw, font=font)
        w = bbox[2] - bbox[0]
        max_text_w = max(max_text_w, w)
            
    col_w = 10 + cfg.tile_size + 10 + max_text_w + 50
    row_h = max(cfg.tile_size, 20) + 4
    
    n_fams = len(families)
    total_area = n_fams * row_h * col_w
    side = math.sqrt(total_area)
    
    num_cols = max(1, int(side // col_w) + 1)
    items_per_col = math.ceil(n_fams / num_cols)
    
    img_w = num_cols * col_w
    img_h = items_per_col * row_h
    
    img = Image.new("RGB", (img_w, img_h), (30, 30, 30))
    draw = ImageDraw.Draw(img)

    for i, fam in enumerate(families):
        col = i // items_per_col
        row = i % items_per_col
        x = col * col_w
        y = row * row_h + 2
        
        glyph = glyph_for_family(fam, cfg)
        img.paste(Image.fromarray(glyph), (x + 10, y))
        fam_draw  = re.sub(r"[\n\t\r]+", " ", fam).strip()
        draw.text((x + 10 + cfg.tile_size + 10, y), fam_draw, fill=(220, 220, 220), font=font)

    img.save(filename)
    print(f"Saved legend to {filename}")


# ----------------------------
# 3) Main Encoding Logic
# ----------------------------

def encode_rows_to_image(
    rows: List[List[str]],
    out_png_path: str,
    out_meta_json_path: Optional[str],
    cfg: TileConfig,
    explicit_family_mapper=None
) -> Dict:
    
    # 1. Prepare Data
    fam_rows = []
    for ex in rows:
        if explicit_family_mapper:
            fam_rows.append([explicit_family_mapper(tok) for tok in ex])
        else:
            fam_rows.append(ex)

    unique_families = set(f for r in fam_rows for f in r)
    unique_families.add(cfg.pad_family)
    unique_families.add(cfg.sep_family)
    
    glyph_cache = {f: glyph_for_family(f, cfg) for f in unique_families}

    # 2. Group by Family
    from collections import defaultdict
    family_groups = defaultdict(list)
    for r in fam_rows:
        if not r: continue
        family_groups[r[0]].append(r)
        
    sorted_fams = sorted(family_groups.keys())
    
    # 3. Create Blocks
    blocks = [] # (Image, Meta)
    
    try: font = ImageFont.truetype("arial.ttf", 14)
    except: font = ImageFont.load_default()
    
    dummy_img = Image.new("RGB", (1,1))
    dummy_draw = ImageDraw.Draw(dummy_img)
    
    header_h = 24
    sep_h = cfg.tile_size 
    
    global_max_width = 0

    for fam in sorted_fams:
        group_rows = family_groups[fam]
        
        # A. Calculate Raw Token Width (just data)
        max_data_tokens = 0
        for r in group_rows:
            max_data_tokens = max(max_data_tokens, len(r))
        
        # B. Calculate Text Width
        fam_draw  = re.sub(r"[\n\t\r]+", " ", fam).strip()
        bbox = dummy_draw.textbbox((0, 0), fam_draw, font=font)
        text_w_px = bbox[2] - bbox[0] + 16 # padding
        
        # C. Calculate Required Width in TILES
        # Max tiles allowed (10000px - border / 16)
        MAX_TILES_PER_ROW = (cfg.max_dimension - (cfg.tile_size * 2)) // cfg.tile_size
        
        width_needed_px = max(text_w_px, (max_data_tokens + 1) * cfg.tile_size)
        total_tiles_wide = math.ceil(width_needed_px / cfg.tile_size)
        
        # Cap at Max Width
        if total_tiles_wide > MAX_TILES_PER_ROW:
            total_tiles_wide = MAX_TILES_PER_ROW
            
        width_px = total_tiles_wide * cfg.tile_size
        global_max_width = max(global_max_width, width_px)
        
        # Normalize rows with Wrapping
        # Logic: 
        # 1. Wrap individual examples if they exceed width.
        # 2. Separate DIFFERENT examples with a 'Stripe' row (tile_size height).
        # 3. No stripes between wrapped lines of the same example.
        
        processed_rows = []
        for i, r in enumerate(group_rows):
            # Add SEP to the end of the logic sequence
            full_seq = r + [cfg.sep_family]
            
            # Wrap
            idx = 0
            while idx < len(full_seq):
                chunk = full_seq[idx : idx + total_tiles_wide]
                
                # Pad chunk to full width if needed
                if len(chunk) < total_tiles_wide:
                    chunk = chunk + [cfg.pad_family] * (total_tiles_wide - len(chunk))
                    
                processed_rows.append( (chunk, 1.0) ) # Normal height row
                idx += total_tiles_wide
            
            # Add Stripe after example (if not the last one, or maybe always?)
            # User said "before and after". Let's put a separator after each example.
            # "make it tile size" -> 1.0 factor
            if i < len(group_rows) - 1:
                 processed_rows.append( ([], 1.0) )
            
        # Recalculate Content Height based on variable row heights
        content_h = header_h + sep_h
        for _, factor in processed_rows:
            content_h += int(cfg.tile_size * factor)

        # Recalculate Content Height based on variable row heights
        content_w = width_px
        content_h = header_h + sep_h
        for _, factor in processed_rows:
            content_h += int(cfg.tile_size * factor)

        # Add Border Tiles (16px on all sides)
        BORDER_SIZE = cfg.tile_size
        full_w = content_w + (BORDER_SIZE * 2)
        full_h = content_h + (BORDER_SIZE * 2)
        
        block_img = Image.new("RGB", (full_w, full_h), (255,255,255))
        draw = ImageDraw.Draw(block_img)
        
        # Draw Border Tiles
        # Generate a border glyph for this family
        border_glyph = glyph_for_family(fam + "::BORDER", cfg)
        b_tile = Image.fromarray(border_glyph)
        
        # Top & Bottom Border
        for bx in range(0, full_w, BORDER_SIZE):
            block_img.paste(b_tile, (bx, 0))
            block_img.paste(b_tile, (bx, full_h - BORDER_SIZE))
            
        # Left & Right Border
        for by in range(BORDER_SIZE, full_h - BORDER_SIZE, BORDER_SIZE):
            block_img.paste(b_tile, (0, by))
            block_img.paste(b_tile, (full_w - BORDER_SIZE, by))
            
        # Draw Content inside Border
        # Header Background
        draw.rectangle([(BORDER_SIZE, BORDER_SIZE), (BORDER_SIZE + content_w, BORDER_SIZE + header_h)], fill=(220,220,220))
        
        fam_draw  = re.sub(r"[\n\t\r]+", " ", fam).strip()
        
        draw.text((BORDER_SIZE + 4, BORDER_SIZE + 4), fam_draw, fill=(0,0,0), font=font)
        
        # Tiles & Stripes
        y = BORDER_SIZE + header_h
        
        # We don't generate a stripe glyph anymore, just use black pixels.
        
        for row_data, factor in processed_rows:
            h_px = int(cfg.tile_size * factor)
            
            if not row_data:
                # Stripe Row (Empty Data) - Draw BLACK separator
                # Draw a black rectangle across the content width
                # (Inside standard borders)
                draw.rectangle([(BORDER_SIZE, y), (BORDER_SIZE + width_px, y + h_px)], fill=(0,0,0))
            else:
                # Normal Row
                for i, tok in enumerate(row_data):
                    block_img.paste(Image.fromarray(glyph_cache[tok]), (BORDER_SIZE + i*cfg.tile_size, y))
                    
            y += h_px
            
        # Bottom Separator Bar (inside border)
        draw.rectangle([(BORDER_SIZE, BORDER_SIZE + content_h - sep_h), (BORDER_SIZE + content_w, BORDER_SIZE + content_h)], fill=(0,0,0))
        
        # 1px Outline invalid inside border? User asked for 16x16 tiles.
        # But maybe we keep a thin line around content?
        draw.rectangle([(BORDER_SIZE, BORDER_SIZE), (full_w - BORDER_SIZE - 1, full_h - BORDER_SIZE - 1)], outline=(0,0,0), width=1)
        
        meta = {
            "family": fam,
            "w": full_w,
            "h": full_h,
            "rows": len(processed_rows),
            "limit": total_tiles_wide
        }
        blocks.append((block_img, meta))
        
    if not blocks: return {}

    # 4. Shelf Packing - Cap width at max_dimension
    target_width = min(max(global_max_width + (cfg.tile_size*2), 4096), cfg.max_dimension)
    
    current_shelf_x = 0
    current_shelf_h = 0
    current_shelf_items = []
    
    placed_items = [] 
    
    current_y = 0
    page_limit = cfg.max_dimension
    
    for b_img, b_meta in blocks:
        w, h = b_meta['w'], b_meta['h']
        
        # Check if item fits on current shelf horizontally
        if current_shelf_x + w <= target_width:
            # Fits horizontally. 
            # Now Check Vertical Page Constraints for this item
            item_bottom = current_y + h
            
            if item_bottom > page_limit:
                # This item crosses the page boundary!
                # We cannot place it on this shelf (or this shelf is invalid here).
                
                # Strategy:
                # 1. Flush current shelf to placed_items (it's done).
                for item in current_shelf_items: placed_items.append(item)
                
                # 2. Advance current_y to start of NEXT PAGE
                current_y = page_limit
                page_limit += cfg.max_dimension
                
                # 3. Reset Shelf
                current_shelf_x = 0
                current_shelf_h = 0
                current_shelf_items = []
                
                # 4. Now place item on new page shelf
                current_shelf_items.append((b_img, current_shelf_x, current_y, b_meta))
                current_shelf_x += w
                current_shelf_h = h
            else:
                # Safe to place
                current_shelf_items.append((b_img, current_shelf_x, current_y, b_meta))
                current_shelf_x += w
                current_shelf_h = max(current_shelf_h, h)
                
        else:
            # Does not fit horizontally. Start NEW SHELF (New Line).
            for item in current_shelf_items: placed_items.append(item)
            
            current_y += current_shelf_h
            
            # Check if this NEW shelf start overlaps boundary? 
            # Usually strict packing prevents this if we check item-by-item below.
            # But let's check if the *start* y is valid?
            # Actually, `current_y` is just the top.
            
            current_shelf_x = 0
            current_shelf_h = 0
            current_shelf_items = []
            
            # Now we try to place the item on this NEW shelf.
            # Again, check vertical fit.
            if current_y + h > page_limit:
                # New line still crosses boundary!
                # Force Page Break
                current_y = page_limit
                page_limit += cfg.max_dimension
            
            current_shelf_items.append((b_img, current_shelf_x, current_y, b_meta))
            current_shelf_x += w
            current_shelf_h = h
            
    for item in current_shelf_items:
        placed_items.append(item)
    current_y += current_shelf_h
    
    # 5. Render Final Canvas (with possible splitting)
    final_w = target_width
    final_h = current_y
    
    print(f"Canvas Size: {final_w}x{final_h} pixels")
    
    # Determine if we need to split
    max_dim = cfg.max_dimension
    need_split = final_w > max_dim or final_h > max_dim
    
    all_coords = []
    saved_images = []
    
    if not need_split:
        # Single image output
        canvas = Image.new("RGB", (final_w, final_h), cfg.background)
        for img, x, y, meta in placed_items:
            canvas.paste(img, (x, y))
            bbox = [x, y, meta['w'], meta['h']]
            all_coords.append({
                "family": meta['family'],
                "bbox": bbox,
                "rows": meta['rows'],
                "limit": meta['limit'],
                "tile_index": 0
            })
        canvas.save(out_png_path, optimize=True)
        saved_images.append(out_png_path)
    else:
        # Split into multiple tiles based on height
        tile_height = max_dim
        num_tiles = math.ceil(final_h / tile_height)
        print(f"Splitting into {num_tiles} tiles (max dimension: {max_dim}px)")
        
        base_name = out_png_path.replace(".png", "")
        
        for tile_idx in range(num_tiles):
            y_start = tile_idx * tile_height
            y_end = min((tile_idx + 1) * tile_height, final_h)
            tile_h = y_end - y_start
            
            tile_canvas = Image.new("RGB", (final_w, tile_h), cfg.background)
            
            for img, x, y, meta in placed_items:
                item_y_end = y + meta['h']
                
                # Check if this item overlaps with current tile
                if item_y_end > y_start and y < y_end:
                    # Calculate overlap region
                    paste_y = max(0, y - y_start)
                    crop_top = max(0, y_start - y)
                    crop_bottom = min(meta['h'], y_end - y)
                    
                    if crop_bottom > crop_top:
                        cropped_img = img.crop((0, crop_top, meta['w'], crop_bottom))
                        tile_canvas.paste(cropped_img, (x, paste_y))
                        
                        # Add coords for this tile (relative to tile)
                        all_coords.append({
                            "family": meta['family'],
                            "bbox": [x, paste_y, meta['w'], crop_bottom - crop_top],
                            "rows": meta['rows'],
                            "limit": meta['limit'],
                            "tile_index": tile_idx,
                            "original_y": y
                        })
            
            tile_path = f"{base_name}_{tile_idx + 1}.png"
            tile_canvas.save(tile_path, optimize=True)
            saved_images.append(tile_path)
            print(f"  Saved: {tile_path} ({final_w}x{tile_h})")
    
    # Generate legend
    legend_path = out_png_path.replace(".png", "_legend.png")
    
    # Filter families for Legend to avoid bloating
    # 1. Syntax ((){})
    # 2. Key Markers (TYPE_INFO)
    # 3. Explicit Headers (Modules) - optional, maybe only show checking '::'
    # 4. Do NOT show distinct vocabulary tokens if there are thousands.
    
    legend_fams = []
    syntax_chars = {"(", ")", "{", "}", "[", "]", "=>", ".", ",", ":", "TYPE_INFO"}
    
    for f in unique_families:
        if f in syntax_chars:
            legend_fams.append(f)
        elif "::" in f:
             # It's a header/module key?
             # User might want to see module colors.
             # Limit to top 200 modules?
             legend_fams.append(f)
             
    # Sort: Syntax first, then Modules
    legend_fams.sort(key=lambda x: (0 if x in syntax_chars else 1, x))
    
    generate_legend(legend_fams, legend_path, cfg)
    
    # Save vocab
    with open(out_png_path.replace(".png", ".vocab.json"), "w", encoding="utf-8") as f:
        json.dump(list(set(c['family'] for c in all_coords)), f, indent=2)

    # Save coords
    with open(out_png_path.replace(".png", ".coords.json"), "w", encoding="utf-8") as f:
        json.dump(all_coords, f, indent=2)
        
    return {"dimensions": [final_w, final_h], "tiles": len(saved_images), "images": saved_images}

# ----------------------------
# 4) Main Driver
# ----------------------------

if __name__ == "__main__":
    import re
    if len(sys.argv) < 2:
        print("Usage: python tiles.py <input.json>")
        sys.exit(1)
        
    input_path = sys.argv[1]
    if not os.path.exists(input_path): sys.exit(1)
    
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    # A. Registry
    registry = {}
    name_map = {}
    
    def register(name, src, kind):
        if not name: return
        if not src: src = "unknown"
        key = f"{src}::{name}"
        registry[key] = {"name": name, "source": src, "type": kind}
        if name not in name_map: name_map[name] = key
    for p in data.get("call_patterns", []): register(p.get("chain"), p.get("source_import"), "call")
    for p in data.get("jsx_patterns", []): register(p.get("component"), p.get("source_import"), "jsx")
    for p in data.get("constant_patterns", []): register(p.get("constant"), p.get("source_import"), "const")
    for p in data.get("component_definitions", []): register(p.get("component"), p.get("file"), "def")
    for p in data.get("reference_patterns", []): register(p.get("name"), p.get("source_import"), "ref")
    
    # B. Examples
    examples = []
    token_re = re.compile(r"[\w]+(?:\.[\w]+)*|[(){}]")
    
    def resolve(t): return name_map.get(t)
    
    def proc(plist, nkey, fkey):
        for p in plist:
            hname:str = p.get(nkey)
            if not hname: continue
            
            # Remove newlines to prevent overlap
            src = p.get("source_import") or p.get("file") or "unknown"
            hkey = f"{src}::{hname}"
            if hkey not in registry: register(hname, src, "auto")
            
            # Type Encoding Enhancement
            # If pattern has return type or signature, we add a generic marker or specific type token
            # User asked for "types the return". 
            # We can look for 'return_type' or check signature.
            has_type = False
            if p.get("return_type") and p.get("return_type") != "unknown":
                has_type = True
            elif p.get("signature"):
                has_type = True
                
            for f in p.get(fkey, []):
                tokens = token_re.findall(f)
                row = [hkey]
                
                # Injection: If typed, add a visual indicator (Type Glyph) right after header
                # We use a special family "TYPE::marker" which will have a consistent color
                if has_type:
                    row.append("TYPE_INFO") 
                
                for t in tokens:
                    if t in "(){}":
                        # Syntax Encoding Enhancement
                        # Pass brackets directly. They become their own family "{" etc.
                        row.append(t)
                    else:
                        tok = resolve(t)
                        if tok:
                            if t != hname: row.append(tok)
                            
                if len(row) > 0: examples.append(row)
                
    proc(data.get("call_patterns", []), "chain", "abstract_forms")
    proc(data.get("jsx_patterns", []), "component", "abstract_forms")
    proc(data.get("constant_patterns", []), "constant", "examples")
    proc(data.get("component_definitions", []), "component", "abstract_forms")
    
    heads = {e[0] for e in examples}
    for k, v in registry.items():
        if v['type'] == 'vocab' and k not in heads:
            examples.append([k, "PAD"])
            
    # C. Output - Create directory named after the repo
    base = os.path.splitext(os.path.basename(input_path))[0]
    # Remove _patterns suffix if present
    if base.endswith("_patterns"):
        repo_name = base[:-9]
    else:
        repo_name = base
    
    output_dir = os.path.join(os.path.dirname(input_path) or ".", f"{repo_name}_tiles")
    os.makedirs(output_dir, exist_ok=True)
    
    out_png = os.path.join(output_dir, "tiles.png")
    out_map = os.path.join(output_dir, "map.json")
    
    cfg = TileConfig(tile_size=16)
    result = encode_rows_to_image(examples, out_png, None, cfg)
    
    with open(out_map, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)
    
    print(f"\nOutput directory: {output_dir}")
    print(f"Done. Map: {out_map}")
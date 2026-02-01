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
        bbox = dummy_draw.textbbox((0, 0), fam, font=font)
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
        draw.text((x + 10 + cfg.tile_size + 10, y), fam, fill=(220, 220, 220), font=font)

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
        bbox = dummy_draw.textbbox((0, 0), fam, font=font)
        text_w_px = bbox[2] - bbox[0] + 16 # padding
        
        # C. Calculate Required Width in TILES
        # We need enough tiles to cover the text, OR the data, whichever is wider.
        # width in pixels must be multiple of tile_size
        
        width_needed_px = max(text_w_px, (max_data_tokens + 1) * cfg.tile_size)
        
        # Snap up to nearest tile count
        total_tiles_wide = math.ceil(width_needed_px / cfg.tile_size)
        
        width_px = total_tiles_wide * cfg.tile_size
        global_max_width = max(global_max_width, width_px)
        
        # Normalize rows:
        # PUSH THE 'SEP' TO THE FAR RIGHT (last tile index)
        norm_rows = []
        for r in group_rows:
            current_len = len(r)
            # We need to fill from current_len up to (total_tiles_wide - 1) with PAD
            # The very last slot (total_tiles_wide - 1) is SEP
            
            pads_needed = (total_tiles_wide - 1) - current_len
            if pads_needed < 0: pads_needed = 0 # sanity check
            
            padded = r + [cfg.pad_family] * pads_needed
            padded.append(cfg.sep_family) # SEP is now at the right edge
            norm_rows.append(padded)
            
        n_rows = len(norm_rows)
        height_px = header_h + (n_rows * cfg.tile_size) + sep_h
        
        block_img = Image.new("RGB", (width_px, height_px), (255,255,255))
        draw = ImageDraw.Draw(block_img)
        
        # Header
        draw.rectangle([(0,0), (width_px, header_h)], fill=(220,220,220))
        draw.text((4, 4), fam, fill=(0,0,0), font=font)
        
        # Tiles
        y = header_h
        for row in norm_rows:
            for i, tok in enumerate(row):
                block_img.paste(Image.fromarray(glyph_cache[tok]), (i*cfg.tile_size, y))
            y += cfg.tile_size
            
        # Bottom Separator Bar
        draw.rectangle([(0, height_px - sep_h), (width_px, height_px)], fill=(0,0,0))
        
        # FULL BORDER
        draw.rectangle([(0, 0), (width_px - 1, height_px - 1)], outline=(0,0,0), width=1)
        
        meta = {
            "family": fam,
            "w": width_px,
            "h": height_px,
            "rows": n_rows,
            "limit": total_tiles_wide
        }
        blocks.append((block_img, meta))

    if not blocks: return {}

    # 4. Shelf Packing
    target_width = max(global_max_width, 4096) 
    
    current_shelf_x = 0
    current_shelf_h = 0
    current_shelf_items = []
    
    placed_items = [] 
    
    current_y = 0
    
    for b_img, b_meta in blocks:
        w, h = b_meta['w'], b_meta['h']
        
        if current_shelf_x + w <= target_width:
            current_shelf_items.append((b_img, current_shelf_x, current_y, b_meta))
            current_shelf_x += w
            current_shelf_h = max(current_shelf_h, h)
        else:
            for item in current_shelf_items:
                placed_items.append(item)
            
            current_y += current_shelf_h
            current_shelf_x = 0
            current_shelf_h = 0
            current_shelf_items = []
            
            current_shelf_items.append((b_img, current_shelf_x, current_y, b_meta))
            current_shelf_x += w
            current_shelf_h = h
            
    for item in current_shelf_items:
        placed_items.append(item)
    current_y += current_shelf_h
    
    # 5. Render Final Canvas
    final_w = target_width
    final_h = current_y
    
    print(f"Canvas Size: {final_w}x{final_h} pixels")
    canvas = Image.new("RGB", (final_w, final_h), cfg.background)
    
    coords = []
    
    for img, x, y, meta in placed_items:
        canvas.paste(img, (x, y))
        
        bbox = [x, y, meta['w'], meta['h']]
        coords.append({
            "family": meta['family'],
            "bbox": bbox,
            "rows": meta['rows'],
            "limit": meta['limit']
        })
        
    canvas.save(out_png_path, optimize=True)
    generate_legend(list(unique_families), out_png_path.replace(".png", "_legend.png"), cfg)
    
    with open(out_png_path.replace(".png", ".vocab.json"), "w", encoding="utf-8") as f:
        json.dump([c['family'] for c in coords], f, indent=2)

    with open(out_png_path.replace(".png", ".coords.json"), "w", encoding="utf-8") as f:
        json.dump(coords, f, indent=2)
        
    return {"dimensions": [final_w, final_h]}

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
    token_re = re.compile(r"[\w]+(?:\.[\w]+)*")
    
    def resolve(t): return name_map.get(t, f"unknown::{t}")
    
    def proc(plist, nkey, fkey):
        for p in plist:
            hname = p.get(nkey)
            if not hname: continue
            src = p.get("source_import") or p.get("file") or "unknown"
            hkey = f"{src}::{hname}"
            if hkey not in registry: register(hname, src, "auto")
            
            for f in p.get(fkey, []):
                tokens = token_re.findall(f)
                row = [hkey]
                for t in tokens:
                    if t != hname: row.append(resolve(t))
                if len(row) > 0: examples.append(row)
                
    proc(data.get("call_patterns", []), "chain", "abstract_forms")
    proc(data.get("jsx_patterns", []), "component", "abstract_forms")
    proc(data.get("constant_patterns", []), "constant", "examples")
    proc(data.get("component_definitions", []), "component", "abstract_forms")
    
    heads = {e[0] for e in examples}
    for k, v in registry.items():
        if v['type'] == 'vocab' and k not in heads:
            examples.append([k, "PAD"])
            
    # C. Output
    base = os.path.splitext(input_path)[0]
    out_png = f"{base}_tiles.png"
    out_map = f"{base}_tiles.map.json"
    out_vocab = f"{base}_vocab.json"
    
    cfg = TileConfig(tile_size=16)
    encode_rows_to_image(examples, out_png, None, cfg)
    
    with open(out_map, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)
        
    print(f"Done. Map: {out_map}")
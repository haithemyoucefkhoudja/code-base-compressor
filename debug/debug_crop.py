import sys
import os
sys.path.insert(0, 'ai')
import ai.workflow as workflow

os.makedirs('./debug', exist_ok=True)

decoder = workflow.VisualDecoder('./repo_blimpt_tiles')
family = "\"@/providers/chat-provider\"::ChatProvider"
print(f'Testing family: {family}')

# Check if family exists
norm = decoder._normalize_family(family)
print(f'Normalized: {norm}')
print(f'In coords: {norm in decoder.context.coords}')

if norm in decoder.context.coords:
    meta = decoder.context.coords[norm]
    print(f'Tile index: {meta.get("_tile_index", 0)}')
    print(f'Bbox (stitched): {meta["bbox"]}')
    print(f'Tile-local bbox: {meta.get("_tile_local_bbox", "N/A")}')
    
    crop, neighbors = decoder.crop_and_decode(family)
    if crop:
        crop.save('./debug/test_crop.png')
        print(f'Saved to ./debug/test_crop.png')
        print(f'Crop size: {crop.size}')
        print(f'Neighbors found: {len(neighbors)}')
    else:
        print('Crop failed!')
else:
    print('Family not found in coords!')

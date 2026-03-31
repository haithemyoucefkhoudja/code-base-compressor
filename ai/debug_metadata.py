import sys
import os
import json

# Add project root to path
sys.path.append(os.getcwd())

from ai.utils.tools import VisualDecoder

def main():
    tiles_dir = "./repo_tiles"
    print(f"🔍 DEBUGGING METADATA FOR: {tiles_dir}")
    
    if not os.path.exists(tiles_dir):
        print(f"❌ Error: Tiles directory {tiles_dir} not found.")
        return

    # 1. Test VisualDecoder
    print("\n--- VisualDecoder Registry ---")
    decoder = VisualDecoder(tiles_dir)
    target = '\"@/utils/with-rate-limit\"::withRateLimit::CALL'
    
    reg_entry = decoder.registry.get(target)
    if reg_entry:
        print(f"✅ Found {target}")
        print(json.dumps(reg_entry, indent=2))
    else:
        print(f"❌ Could not find {target} in Decoder registry.")
        # Print some keys to see what we have
        print("First 5 keys in registry:")
        for k in list(decoder.registry.keys())[:5]:
            print(f"  {k}")

if __name__ == "__main__":
    main()

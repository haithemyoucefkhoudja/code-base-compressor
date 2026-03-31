import sys
import os
import json

# Add project root to path
sys.path.append(os.getcwd())

from ai.utils.tools import VisualDecoder

def main():
    tiles_dir = "./repo_tiles"
    if not os.path.exists(tiles_dir):
        print(f"❌ Error: {tiles_dir} not found.")
        return

    decoder = VisualDecoder(tiles_dir)
    # Testing a known family
    target = '\"@/utils/with-rate-limit\"::withRateLimit::CALL'
    
    print(f"🔍 INSPECTING: {target}")
    result = decoder.inspect(target)
    
    if result:
        image_bytes, inspection = result
        print(f"✅ Inspection Successful")
        print(f"Family: {inspection.family}")
        print(f"Density: {inspection.density}")
        print(f"Total Identified Children: {sum(inspection.color_analysis.values())}")
        print(f"Children Elements (Top 10):")
        sorted_counts = sorted(inspection.color_analysis.items(), key=lambda x: x[1], reverse=True)
        for fam, count in sorted_counts[:10]:
            print(f"  - {count}: {fam}")
            
        print(f"\nMost Frequent Parents (Top 5):")
        sorted_parents = sorted(inspection.most_frequent_parents.items(), key=lambda x: x[1], reverse=True)
        for fam, count in sorted_parents[:5]:
            print(f"  - {count}: {fam}")
    else:
        print(f"❌ Failed to inspect {target}")

if __name__ == "__main__":
    main()

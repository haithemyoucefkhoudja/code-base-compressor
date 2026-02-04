import sys
import os
sys.path.insert(0, 'ai')
import ai.workflow as workflow

os.makedirs('./debug', exist_ok=True)

decoder = workflow.VisualDecoder('./repo_blimpt_tiles')

# Test multiple families for bulk stitching
families = [
    '"../HistoryIndicator"::History',
    "\"@/providers/chat-provider\"::ChatProvider",
    "\"@/providers/chat-provider\"::useConversations",
    "\"@/providers/gamification-provider\"::GamificationProvider",
    "\"@/skill-tree-assets/task-io\"::parseTaskFile"
]

print(f'Testing bulk_inspect with {len(families)} families...')

stitched_bytes, results = decoder.bulk_inspect(families)

if stitched_bytes:
    with open('./debug/bulk_stitch.png', 'wb') as f:
        f.write(stitched_bytes)
    print(f'Saved to ./debug/bulk_stitch.png')
    print(f'Results: {len(results)} families inspected')
    for r in results:
        print(f'  - {r.family}: {len(r.neighbors)} neighbors')
else:
    print('Bulk inspect failed!')

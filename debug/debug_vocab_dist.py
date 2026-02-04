import sys
import json
sys.path.insert(0, 'ai')
import workflow

vocab = workflow.VocabularyIndex('./repo_blimpt_tiles')
all_v = vocab.get_all()

with open('search_results.txt', 'w') as f:
    f.write("--- SEARCH RESULTS ---\n")
    matches = [v for v in all_v if 'Message' in v or 'Messenger' in v or 'Messanger' in v or 'Container' in v]
    for m in matches:
        f.write(f"{m}\n")
print("Done.")

import sys
import json
sys.path.insert(0, 'ai')
import workflow

vocab = workflow.VocabularyIndex('./repo_blimpt_tiles')
all_v = vocab.get_all()

print("--- SEARCH RESULTS ---")
print("Query: Message | Messenger | Container")
matches = [v for v in all_v if 'Message' in v or 'Messenger' in v or 'Container' in v]
for m in matches:
    print(m)
print("----------------------")

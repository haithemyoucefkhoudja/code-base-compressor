import sys
import difflib
sys.path.insert(0, 'ai')
import workflow

vocab = workflow.VocabularyIndex('./repo_blimpt_tiles')
query = 'MessageContainer'

with open('verify_output.txt', 'w') as f:
    f.write(f"Query: {query}\n")
    matches = vocab.search(query, limit=5)
    f.write("Top Matches:\n")
    for m in matches:
        f.write(f"{m}\n")
print("Done.")

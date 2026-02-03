from analyzer.core.dts_provider import parse_dts_definitions
import json

path = "repo_blimpt/dist-types/providers/chat-provider.d.ts"
defs = parse_dts_definitions(path)

print(json.dumps(defs.get("useChat"), indent=2))
print("ChatContextValue expansion check:")
use_chat = defs.get("useChat")
if use_chat:
    print("Return Type:", use_chat.get("return_type"))
    print("Expanded:", json.dumps(use_chat.get("return_type_expanded"), indent=2))

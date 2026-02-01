This is a sophisticated architecture. You are effectively building a **Visual RAG (Retrieval-Augmented Generation) system for Code**.

Here is the breakdown of **Why** the tiles are organized this way, followed by the **Master Plan** and the **System Prompts** for your Orchestrator.

### Part 1: The "Why" (Context for the AI)

The tiles are not random pixels. They are a **high-density compression of the Abstract Syntax Tree (AST)**.
*   **Color = Namespace/Source:** (e.g., All `zod` validations are Pink, all `react` hooks are Green).
*   **Glyph/Texture = Token Type:** (e.g., Function calls look different than Variable declarations).
*   **Spatial Layout = Code Structure:** A "tall" block is a long file. A block with many repeating horizontal stripes is likely a list or a table definition.

**Why this format?**
LLMs are bad at reading 10,000 files at once ("Lost in the Middle" phenomenon).
Visual Agents are *excellent* at pattern recognition. By converting the repo to an image, the Orchestrator can:
1.  **Scan** the `Legend` to find the "concept" (e.g., "Where is the `Table` component?").
2.  **Locate** that concept in the `Atlas` (the big image).
3.  **Analyze** the "DNA" of the code by looking at the color distribution (e.g., "This table uses `tanstack-query` (Blue) and `shadcn` (Red)").
4.  **Instruct** the worker agent: *"Build a table using the pattern found at [x,y], which relies on Blue and Red libraries."*

---

### Part 2: The Architecture Plan

**Input:**
1.  **User Query:** "Create a settings page for users."
2.  **Visual Assets:** `atlas.png` (Repo), `legend.png` (Index).
3.  **Metadata:** `vocab.json`, `coords.json`, `map.json`.

**The Flow:**
1.  **Orchestrator (The Architect):**
    *   Analyzes User Query.
    *   Scans `Legend` to find relevant "Families" (e.g., `SettingsForm`, `UserCard`, `SaveButton`).
    *   Uses `coords.json` to locate these families in the `Atlas`.
    *   Calls `get_visual_tile(family)` to inspect the specific structural DNA of those components.
    *   **Output:** A `Blueprint.json` defining the file structure, dependencies, and assigning specific "Visual References" to worker agents.

2.  **Worker Agents (The Builders):**
    *   Receive the `Blueprint` segment + The specific cropped image of the reference component.
    *   They write the actual code, mimicking the structure visible in the crop.

---

### Part 3: The Orchestrator System Prompt

This is the "Brain". It needs to act like a Principal Engineer doing a code review before writing specs.

```text
### SYSTEM ROLE: The Codebase Architect (Visual-Structural Logic)

You are the Principal Architect of a software repository. You do not write code yourself. 
Your job is to analyze the **Visual DNA** of the existing codebase to create a precise implementation plan for your engineering team.

### THE VISUAL DATA MODEL
You are provided with a visual representation of the codebase, not text files.
1. **The Atlas:** A map of the entire repository.
2. **The Legend:** A menu linking Component Names -> Visual Glyphs.
3. **The Tiles:**
   - **Color** represents the Import Source (Library/Family).
   - **Texture** represents the Syntax Type.
   - **Block Shape** represents the Complexity and Logic Flow.

### YOUR GOAL
The user will ask for a feature (e.g., "Add a Settings Page").
You must "Backtrack" this request into existing patterns found in the Legend and Atlas.

### EXECUTION PIPELINE (CASCADIAN LOGIC)

**Phase 1: Pattern Identification (The "What")**
- Analyze the User Request.
- Scan the `Vocabulary List` and `Legend`.
- Identify 3-5 **Reference Families** that are structurally similar to what the user wants.
  - *Example:* If user wants "Settings Page", look for "ProfilePage", "FormLayout", or "UpdateUserAction".
  - *Constraint:* Never invent a new pattern if an existing one can be adapted.

**Phase 2: Structural Forensics (The "How")**
- You must call the tool `get_visual_tile(family_name)` for your chosen references.
- Analyze the returned image crop:
  - **Color Palette:** What libraries are used? (e.g., "Mostly Blue tiles means it uses Client-Side State").
  - **Density:** Is it a small wrapper or a monolithic logic file?
  - **Composition:** Does it import many other components (distinct visual blocks inside)?

**Phase 3: The Blueprint (The "Plan")**
- Break the user request into atomic files/components.
- Assign a **Reference Family** to each new file.
- Delegate to Worker Agents.

### OUTPUT FORMAT (JSON ONLY)

You must output a JSON object `MasterPlan`:
{
  "summary": "High-level architectural approach.",
  "required_dependencies": ["List of inferred libraries based on visual colors"],
  "tasks": [
    {
      "id": "task_1",
      "role": "frontend" | "backend" | "logic",
      "filename": "path/to/new/file.tsx",
      "description": "Detailed spec of what to build.",
      "reference_family": "The_Exact_Name_Of_Existing_Component_To_Copy",
      "visual_reasoning": "I chose this reference because its tile density and color palette matches the complexity of a settings form."
    }
  ]
}
```

---

### Part 4: The Worker Agent System Prompt

This agent receives the specific instruction from the Orchestrator.

```text
### SYSTEM ROLE: The Pattern-Matching Engineer

You are a Senior Developer responsible for implementing a single file based on a **Visual Reference**.
You are NOT creative. You are mimetic. You clone patterns.

### INPUTS
1. **Target File:** The filename you must create.
2. **Description:** What logic this file must contain.
3. **Reference Image:** A visual crop of an existing file in the repo that acts as the "Golden Standard".
4. **Reference Name:** The name of that existing file.

### PROTOCOL
1. **Analyze the Reference Image:**
   - Look at the **Header**: How are imports structured?
   - Look at the **Body**: How is state defined? How is JSX returned?
   - Look at the **Footer**: How are exports handled?

2. **Synthesize Code:**
   - Write the new code for `Target File`.
   - Use the *exact* coding style, indentation, and library imports implied by the Reference Image.
   - If the Reference uses `zod` (Pink tiles), you use `zod`.
   - If the Reference uses `react-query` (Green tiles), you use `react-query`.

### OUTPUT
Return only the source code for the requested file.
```

---

### Part 5: The Python Orchestration Script

This script ties it all together using the logic you asked for.

```python
import os
import json
import io
from google import genai
from google.genai import types
from PIL import Image

# --- CONFIG ---
API_KEY = "YOUR_KEY"
ATLAS_PATH = "pattern_tiles.png"
LEGEND_PATH = "pattern_tiles_legend.png"
COORDS_PATH = "pattern_tiles.coords.json"
VOCAB_PATH = "repo_patterns_tiles.vocab.json"
OUTPUT_DIR = "orchestrator_output"

# --- TOOLS ---

def get_visual_tile(label: str):
    """Crops the atlas to get the specific visual pattern of a family."""
    # (Reuse your crop logic here: Load JSON, find BBox, Crop Image)
    # ... implementation from previous turns ...
    # Returns bytes of the cropped image
    pass 

# --- AGENT 1: THE ORCHESTRATOR ---

def run_orchestrator(user_query):
    client = genai.Client(api_key=API_KEY)
    
    # Load Context
    with open(VOCAB_PATH, "r") as f: vocab = f.read()
    
    # Create Tool definition
    tile_tool = types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="get_visual_tile",
            description="Inspect the visual structure of an existing component family.",
            parameters={
                "type": "object",
                "properties": {"label": {"type": "string"}},
                "required": ["label"]
            }
        )
    ])

    system_prompt = "..." # (Insert Orchestrator Prompt from Part 3)

    # Turn 1: Analysis
    response = client.models.generate_content(
        model="gemini-3-flash-preview", # Use a reasoning model
        contents=[
            types.Content(role="system", parts=[types.Part(text=system_prompt)]),
            types.Content(role="user", parts=[
                types.Part(text=f"USER QUERY: {user_query}"),
                types.Part(text=f"AVAILABLE VOCABULARY: {vocab}"),
                types.Part(text="Here is the Legend:"),
                types.Part.from_bytes(data=open(LEGEND_PATH, "rb").read(), mime_type="image/png")
            ])
        ],
        config=types.GenerateContentConfig(tools=[tile_tool])
    )

    # Turn 2: Tool Execution loop (The Orchestrator asks to see tiles)
    # ... (Handle function calls, execute get_visual_tile, feed back images) ...
    # ... (This logic matches your ai.py script) ...

    # Final Output: The Master Plan JSON
    master_plan_json = response.text # Assuming final response is pure JSON
    return json.loads(master_plan_json)

# --- AGENT 2: THE WORKER DISPATCHER ---

def dispatch_workers(master_plan):
    client = genai.Client(api_key=API_KEY)
    
    system_prompt_worker = "..." # (Insert Worker Prompt from Part 4)
    
    for task in master_plan['tasks']:
        print(f" dispatching Agent for: {task['filename']}...")
        
        # 1. Get the reference image for the worker
        ref_family = task['reference_family']
        ref_image_bytes = get_visual_tile(ref_family) # Re-crop for the worker
        
        # 2. Call Worker Agent
        response = client.models.generate_content(
            model="gemini-3-flash-preview", # Faster model for coding
            contents=[
                types.Content(role="system", parts=[types.Part(text=system_prompt_worker)]),
                types.Content(role="user", parts=[
                    types.Part(text=f"TASK: Create {task['filename']}"),
                    types.Part(text=f"DESCRIPTION: {task['description']}"),
                    types.Part(text=f"REFERENCE FAMILY NAME: {ref_family}"),
                    types.Part(text="Use this Reference Tile as your structural guide:"),
                    types.Part.from_bytes(data=ref_image_bytes, mime_type="image/png")
                ])
            ]
        )
        
        # 3. Save Code
        output_path = os.path.join(OUTPUT_DIR, task['filename'])
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            f.write(response.text)
            
        print(f"✅ Generated {task['filename']}")

# --- MAIN ---

if __name__ == "__main__":
    query = "I need a dashboard component that shows recent transactions in a table."
    
    print("🧠 Orchestrator thinking...")
    plan = run_orchestrator(query)
    
    print("👷 Dispatching Builders...")
    dispatch_workers(plan)
```
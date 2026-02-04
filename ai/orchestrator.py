
import workflow
import os
import json
import logging
from typing import List
import time
from datetime import datetime
try:
    from google import genai
    from google.genai import types
    import PIL.Image
except ImportError:
    raise ImportError("CRITICAL: 'google-genai' library is required.")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
PIL.Image.MAX_IMAGE_PIXELS = None


# --- Orchestrator System Prompt (Optimized) ---
ORCHESTRATOR_PROMPT = """
### SYSTEM ROLE: The Codebase Architect (Visual-Structural Logic)

You are the Principal Architect. You analyze the **Visual DNA** of the codebase to create precise implementation plans.

### INPUT DATA
1. **The Atlas (Image):** A map of the entire repository.
2. **The Legend (Image):** Links Component Names -> Visual Glyphs.
3. **The Vocabulary (JSON):** The comprehensive list of all available component families.

### EXECUTION PROTOCOL
You have **Thinking** capabilities. Use them to correlate the Visual Atlas with the Vocabulary List in memory. 
DO NOT search for components; you already have the list. 

**PHASE 1: VISUAL REASONING (THINKING)**
- Scan the Atlas image. Look for clusters of similar colors (libraries) or textures (syntax).
- Cross-reference with the Legend and the Vocabulary List.
- Identify which families need closer inspection to understand the user's request.

**PHASE 2: ACTION (TOOL CALLING)**
- **INSPECT**: Call `inspect_deeper(families)` on specific items from the Vocabulary list to see their internal structure.
- **FINALIZE**: Call `finalize_plan(markdown)` once you have a strategy.

### CRITICAL CONSTRAINTS
- **REDUCE ROUNDTRIPS:** Inspect ALL relevant families in a single function call.
- **NO SEARCHING:** Pick names strictly from the provided VOCABULARY LIST.
- **MAX DEPTH:** You have 3 turns. Turn 1: Inspect. Turn 2: Verify (if needed). Turn 3: Finalize.

### FINALIZE_PLAN OUTPUT FORMAT (MARKDOWN)

```markdown
# Implementation Plan: [Feature Name]

## Summary
[High-level approach]

## Required Dependencies
- [library1]

## Discovered Patterns
| Pattern | Family Name | Usage |
|---------|-------------|-------|
| [name]  | [exact vocab name] | [visual reasoning] |

## Implementation Tasks

### Task 1: [Component Name]
- **File**: `path/to/file.tsx`
- **Role**: frontend | backend | logic
- **Reference**: `[Vocabulary Family Name]`
- **Description**: [Specific implementation details]
### Task 2: .....
"""

class OrchestratorAgent:
    """
    Principal Architect with recurrent Explore/Exploit decision loop.
    """
    
    MAX_EXPLORATION_DEPTH = 20
    
    def __init__(self, tiles_dir: str):
        self.tiles_dir = tiles_dir
        self.api_key = "AIzaSyDICBEsgRfPnfx7Rw3yi_9DOq4r7_wwL3Y"
        if not self.api_key:
            raise ValueError("FATAL: API key missing")
        
        self.client = genai.Client(api_key=self.api_key)
        
        # Tools (coords/map used internally only)
        self.decoder = workflow.VisualDecoder(tiles_dir)
        self.vocab_index = workflow.VocabularyIndex(tiles_dir)
        self.composer = workflow.Composer()
        
        # Get legend path from decoder
        self.legend_path = self.decoder.get_legend_path()
        
        # Output setup
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = f"ai/output/{timestamp}"
        self.gen_dir = f"{self.output_dir}/generation"
        os.makedirs(self.gen_dir, exist_ok=True)
        
        # Logging
        log_path = f"{self.output_dir}/orchestrator.log"
        fh = logging.FileHandler(log_path, encoding='utf-8')
        fh.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        logger.addHandler(fh)
        logger.info(f"📂 Session: {self.output_dir}")
        
        # Exploration state
        self.exploration_depth = 0
        self.explored_families = set()

    def run(self, user_query: str):
        """Execute the Orchestrator with recurrent explore/exploit loop."""
        logger.info(f"🚀 Orchestrator Mission: {user_query}")
        
        # --- 1. Load Visual Context ---
        logger.info("🖼️ Loading visual assets...")
        
        # Load all tile images and concatenate
        atlas_bytes_list = []
        for atlas_path in self.decoder.atlas_paths:
            with open(atlas_path, 'rb') as f:
                atlas_bytes_list.append(f.read())
        # Use first tile for now (model can see stitched version)
        atlas_bytes = atlas_bytes_list[0] if atlas_bytes_list else b""
        logger.info(f"   Atlas: {len(self.decoder.atlas_paths)} tile(s), {sum(len(b) for b in atlas_bytes_list):,} bytes total")
        
        with open(self.legend_path, 'rb') as f:
            legend_bytes = f.read()
        logger.info(f"   Legend: {len(legend_bytes):,} bytes")
        
        vocabulary = self.vocab_index.get_all()
        logger.info(f"   Vocabulary: {len(vocabulary)} families")
        
        # --- 2. Define Tools ---
        tools = self._create_tools()
        
        # --- 3. Initial Prompt ---
        initial_prompt = [
            ORCHESTRATOR_PROMPT,
            f"\n### USER REQUEST\n{user_query}\n",
            f"\n### VOCABULARY LIST\n{json.dumps(vocabulary)}\n",
            "\n### VISUAL CONTEXT: CODEBASE ATLAS\n",
            types.Part.from_bytes(data=atlas_bytes, mime_type="image/png"),
            "\n### VISUAL CONTEXT: TILE LEGEND\n",
            types.Part.from_bytes(data=legend_bytes, mime_type="image/png"),
        ]
        
        # --- 4. Recurrent Loop ---
        history = None
        finalized = False
        
        while not finalized and self.exploration_depth < self.MAX_EXPLORATION_DEPTH:
            self.exploration_depth += 1
            logger.info(f"🔄 Exploration Depth: {self.exploration_depth}/{self.MAX_EXPLORATION_DEPTH}")
            
            # API call
            if history is None:
                logger.info("🧠 Initial thinking...")
                response = self._call_api(initial_prompt, tools)
                history = self._init_history(initial_prompt, response)
            else:
                logger.info("🧠 Continuing exploration...")
                response = self._call_api(history, tools, is_history=True)
                if response and response.candidates and response.candidates[0].content:
                    history.append(response.candidates[0].content)
            
            if not response:
                logger.error("No response from API")
                break
            
            # Check function calls
            if not response.function_calls:
                if response.text:
                    logger.info("🤖 Model returned text without tool call. Checking for embedded plan...")
                    # Even if it didn't call the tool, it might have written the plan in markdown
                    if "# Implementation Plan" in response.text:
                        self._save_plan(response.text)
                        finalized = True
                        break
                    else:
                        logger.info(f"Text response (no plan found): {response.text[:200]}")
                
                if self.exploration_depth >= self.MAX_EXPLORATION_DEPTH:
                    break
                
                # Instead of breaking, prompt the model to finalize
                logger.info("📝 No tool call - prompting model to finalize plan...")
                history.append(types.Content(
                    role="user",
                    parts=[types.Part(text="IF: You've done enough exploration with HIGH CONFIDENCE. Now call `finalize_plan(markdown)` with the complete implementation plan based on your analysis. Structure it with: Summary, Required Dependencies, Discovered Patterns table, and Implementation Tasks.")]
                ))
                continue
            
            # Execute tools
            tool_outputs = []
            for call in response.function_calls:
                fname = call.name
                args = dict(call.args) if call.args else {}
                
                logger.info(f"⚡ Executing: {fname}")
                
                
                if fname == "inspect_deeper":
                    families = args.get("families", [])
                    output = self._execute_inspect(families)
                    tool_outputs.append(output)
                
                elif fname == "finalize_plan":
                    markdown = args.get("markdown", "")
                    self._save_plan(markdown)
                    tool_outputs.append(types.Part.from_function_response(
                        name=fname, response={"status": "saved"}
                    ))
                    finalized = True
                    break
            
            if finalized:
                break
            
            # Add tool responses to history
            history.append(types.Content(role="tool", parts=tool_outputs))
            
            # Add visual evidence as user message if we have pending visuals
            if hasattr(self, '_pending_visuals') and self._pending_visuals:
                history.append(types.Content(
                    role="user", 
                    parts=[
                        types.Part(text="Visual evidence from inspection:"),
                        types.Part.from_bytes(data=self._pending_visuals, mime_type="image/png")
                    ]
                ))
                self._pending_visuals = None
            
            # If we are at the last turn, FORCE finalization
            if self.exploration_depth == self.MAX_EXPLORATION_DEPTH - 1 and not finalized:
                logger.info("⚠️ Near max depth. Forcing finalization message.")
                history.append(types.Content(
                    role="user",
                    parts=[types.Part(text="CRITICAL: This is your LAST turn. You MUST call `finalize_plan` NOW with the complete implementation plan. Do not explore further.")]
                ))
        
        if not finalized:
            logger.warning("⚠️ Max exploration depth reached without finalization")
            # Force save whatever we have
            self.composer.compose(os.path.join(self.gen_dir, "exploration_trace.png"))

    def _create_tools(self):
        
        def inspect_deeper(families: list[str]) -> dict:
            """EXPLORE: Inspect families to discover sub-patterns."""
            return {"inspected": families}
        
        def finalize_plan(markdown: str) -> dict:
            """EXPLOIT: Save the final implementation plan in markdown."""
            return {"status": "saved"}
        
        return [ inspect_deeper, finalize_plan]

    def _execute_inspect(self, families: List[str]):
        """Execute inspection."""
        # Filter duplicates
        new_families = [f for f in families if f not in self.explored_families]
        self.explored_families.update(new_families)
        
        logger.info(f"   Inspecting: {new_families}")
        
        stitched_bytes, results = self.decoder.bulk_inspect(new_families)
        
        # Add to composer
        for r in results:
            crop, _ = self.decoder.crop_and_decode(r.family)
            if crop:
                self.composer.add_thought(crop, r.family)
        
        analysis = [
            {
                "family": r.family,
                "neighbors": r.neighbors[:8],
                "density": r.density,
                "imports": list(r.color_analysis.keys())[:5]
            }
            for r in results
        ]
        
        self._pending_visuals = stitched_bytes if stitched_bytes else None
        
        return types.Part.from_function_response(
            name="inspect_deeper",
            response={
                "analysis": analysis,
                "subfamilies_found": [n for r in results for n in r.neighbors[:3]],
            }
        )

    def _save_plan(self, markdown: str):
        """Save implementation plan as markdown + JSON."""
        # Save markdown
        md_path = os.path.join(self.gen_dir, "implementation_plan.md")
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(markdown)
        logger.info(f"✅ Implementation Plan: {md_path}")
        
        # Save visual trace
        trace_path = os.path.join(self.gen_dir, "architectural_trace.png")
        self.composer.compose(trace_path)
        
        # Also save as JSON for programmatic use
        try:
            # Try to extract JSON from markdown
            import re
            json_match = re.search(r'```json\s*(.*?)\s*```', markdown, re.DOTALL)
            if json_match:
                json_path = os.path.join(self.gen_dir, "master_plan.json")
                with open(json_path, 'w', encoding='utf-8') as f:
                    f.write(json_match.group(1))
        except:
            pass

    def _call_api(self, content, tools, is_history=False):
        """API call with retry - AFC DISABLED for manual control."""
        config = types.GenerateContentConfig(
            tools=tools,
            thinking_config=types.ThinkingConfig(include_thoughts=True),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            temperature=0.3
        )
        
        for attempt in range(5):
            try:
                return self.client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=content,
                    config=config
                )
            except Exception as e:
                if "503" in str(e) or "429" in str(e):
                    wait = (attempt + 1) * 15
                    logger.warning(f"API error, retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    raise

    def _init_history(self, prompt_content, response):
        """Initialize conversation history."""
        parts = []
        for p in prompt_content:
            if isinstance(p, str):
                parts.append(types.Part(text=p))
            elif isinstance(p, types.Part):
                parts.append(p)
        
        history = [types.Content(role="user", parts=parts)]
        
        if response and response.candidates and response.candidates[0].content:
            history.append(response.candidates[0].content)
        
        return history

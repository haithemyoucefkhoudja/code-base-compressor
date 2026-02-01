"""
Visual RAG Agent - Orchestrator with Recurrent Explore/Exploit Loop
====================================================================
Principal Architect that uses visual codebase analysis with recursive sub-task exploration.
"""

from google.genai.types import Part
import workflow
import os
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import time
from datetime import datetime
import io

try:
    from google import genai
    from google.genai import types
    from PIL import Image
    import PIL.Image
except ImportError:
    raise ImportError("CRITICAL: 'google-genai' library is required.")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
PIL.Image.MAX_IMAGE_PIXELS = None

# --- Configuration ---
ATLAS_PATH = r"c:\Users\haithem-yk\Desktop\Projects\reposoul-python-job\repo_patterns_tiles.png"
LEGEND_PATH = r"c:\Users\haithem-yk\Desktop\Projects\reposoul-python-job\repo_patterns_tiles_legend.png"


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
    
    def __init__(self):
        self.api_key = "AIzaSyDICBEsgRfPnfx7Rw3yi_9DOq4r7_wwL3Y"
        if not self.api_key:
            raise ValueError("FATAL: API key missing")
        
        self.client = genai.Client(api_key=self.api_key)
        
        # Tools (coords/map used internally only)
        self.decoder = workflow.VisualDecoder()
        self.vocab_index = workflow.VocabularyIndex()
        self.composer = workflow.Composer()
        
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
        
        with open(ATLAS_PATH, 'rb') as f:
            atlas_bytes = f.read()
        logger.info(f"   Atlas: {len(atlas_bytes):,} bytes")
        
        with open(LEGEND_PATH, 'rb') as f:
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
                
                # If no tools and no plan, but not at max depth, maybe prompt to continue?
                # For now, we'll just break to be safe.
                break
            
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


# --- Worker Agent System Prompt ---
WORKER_PROMPT = """
### SYSTEM ROLE: The Pattern-Matching Engineer

You are a Senior Developer responsible for implementing a single file based on a **Visual Reference**.
You are NOT creative. You are mimetic. You clone patterns.

### INPUTS
1. **Target File:** The filename you must create.
2. **Description:** What logic this file must contain.
3. **Reference Image:** A visual crop of an existing file in the repo that acts as the "Golden Standard".
4. **Reference Analysis:** Structural data about the reference (neighbors, density, imports).

### EXPLORE vs EXPLOIT

**EXPLORE** - Call `explore_reference(families)` if you need to see sub-components of the reference
**EXPLOIT** - Call `generate_code(code)` when ready to output the final implementation

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
Call `generate_code(code)` with the complete source code for the requested file.
"""


@dataclass
class TaskResult:
    """Result of a worker task execution."""
    task_id: str
    filename: str
    success: bool
    code: Optional[str] = None
    code_path: Optional[str] = None
    error: Optional[str] = None
    explorations: int = 0
    

class WorkerAgent:
    """
    Pattern-Matching Engineer - generates code based on visual references.
    Production-level implementation with proper explore/exploit loop.
    """
    
    MAX_EXPLORATION_DEPTH = 3

    def __init__(self, client, decoder, vocab_index, output_dir: str):
        self.client = client
        self.decoder = decoder
        self.vocab_index = vocab_index
        self.output_dir = output_dir
        self.code_dir = os.path.join(output_dir, "code")
        os.makedirs(self.code_dir, exist_ok=True)
        
        self.worker_logger = logging.getLogger("worker")
        log_path = os.path.join(output_dir, "worker.log")
        fh = logging.FileHandler(log_path, encoding='utf-8')
        fh.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        self.worker_logger.addHandler(fh)
        self.worker_logger.setLevel(logging.INFO)
    
    def execute_task(self, task: Dict) -> TaskResult:
        task_id = task.get("id", f"task_{int(time.time())}")
        filename = task.get("filename", "untitled.tsx")
        reference = task.get("reference_family", "")
        
        logger.info(f"🔧 Worker: {task_id} - {filename}")
        
        # --- Phase 1: Context ---
        ref_bytes, ref_analysis = self._get_reference(reference)
        
        prompt:List[Part] = [
            Part(text=WORKER_PROMPT),
            Part(text=f"\n### TARGET FILE: {filename}\n### DESCRIPTION: {task.get('description', '')}\n"),
        ]
        
        if ref_bytes:
            prompt.append(Part(text="\n### REFERENCE VISUAL (CLONE THIS)\n"))
            prompt.append(types.Part.from_bytes(data=ref_bytes, mime_type="image/png"))
        if ref_analysis:
            prompt.append(Part(text=f"\n### REFERENCE DATA\n{json.dumps(ref_analysis)}\n"))
        
        # --- Phase 2: Execution ---
        history = None
        generated_code = None
        
        for depth in range(self.MAX_EXPLORATION_DEPTH):
            
            # API Call
            try:
                response = self._call_api(prompt if history is None else history)
            except Exception as e:
                return TaskResult(task_id, filename, False, error=str(e))
            if not response:
                logger.warning(f"API error, No Response")
                break    
            if history is None:
                history = self._init_history(prompt, response)
            elif  response.candidates:
                history.append(response.candidates[0].content)
            
            if not response.function_calls:
                # Check for code block in text
                if response.text and "```" in response.text:
                    generated_code = self._extract_code_from_text(response.text)
                    if generated_code: break
                
                # If no tools and no code, and we are deep, break
                if depth > 1: break
                continue

            # Handle Tools
            tool_outputs = []
            should_break = False
            
            for call in response.function_calls:
                fname = call.name
                args = dict(call.args) if call.args else {}
                
                if fname == "generate_code":
                    code = args.get("code", "")
                    if len(code) > 20:
                        generated_code = code
                        tool_outputs.append(types.Part.from_function_response(name=fname, response={"status": "saved"}))
                        should_break = True
                
                elif fname == "explore_reference":
                    families = args.get("families", [])
                    # Safety check: If agent tries to explore but gives no valid families
                    if not families:
                        tool_outputs.append(types.Part.from_function_response(name=fname, response={"error": "No valid families provided. Generate code now."}))
                    else:
                        stitched, results = self.decoder.bulk_inspect(families)
                        logger.info(f"Results: {results}")
                        if not results:
                            # CRITICAL FIX: If exploration yields nothing, force code generation next turn
                            tool_outputs.append(types.Part.from_function_response(name=fname, response={"error": "Families not found in Atlas. Proceed to generate code with best effort."}))
                        else:
                            tool_outputs.append(types.Part.from_function_response(name=fname, response={"found": len(results)}))
                            if stitched:
                                history.append(types.Content(role="user", parts=[types.Part.from_bytes(data=stitched, mime_type="image/png")]))

            if should_break:
                break
                
            history.append(types.Content(role="tool", parts=tool_outputs))

        if generated_code:
            path = self._save_code(filename, generated_code)
            return TaskResult(task_id, filename, True, code=generated_code, code_path=path)
        
        return TaskResult(task_id, filename, False, error="No code generated")

    def _get_reference(self, reference: str):
        if not reference: return None, {}
        # Try exact match
        res = self.decoder.inspect(reference)
        
        if res:
            image_bytes, result = res
            return image_bytes, {"family": result.family, "imports": list(result.color_analysis.keys())[:5], "props":result.props}
        return None, {}

    def _call_api(self, content):
        # Worker tools
        def generate_code(code: str) -> dict: return {}
        def explore_reference(families: list[str]) -> dict: return {}
        
        config = types.GenerateContentConfig(
            tools=[generate_code, explore_reference],
            thinking_config=types.ThinkingConfig(include_thoughts=True),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            temperature=0.2
        )
        # Reduced retries for speed
        for attempt in range(2):
            try:
                return self.client.models.generate_content(model="gemini-2.5-flash", contents=content, config=config)
            except Exception as e:
                if "429" in str(e): time.sleep(5 + (attempt * 5))
                else: raise
        return None

    def _init_history(self, prompt, response):
        parts = []
        for p in prompt:
            if isinstance(p, str): parts.append(types.Part(text=p))
            elif isinstance(p, types.Part): parts.append(p)
        history = [types.Content(role="user", parts=parts)]
        if response and response.candidates: history.append(response.candidates[0].content)
        return history

    def _extract_code_from_text(self, text):
        import re
        match = re.search(r'```(?:tsx?|jsx?|typescript)?\n(.*?)```', text, re.DOTALL)
        return match.group(1) if match else None

    def _save_code(self, filename, code):
        safe_name = filename.replace("/", "_").replace("\\", "_")
        if not safe_name.endswith((".tsx", ".ts")): safe_name += ".tsx"
        path = os.path.join(self.code_dir, safe_name)
        with open(path, 'w', encoding='utf-8') as f: f.write(code)
        return path


class VisualRAGPipeline:
    """
    Full pipeline: Orchestrator -> Worker Agents
    Production-level implementation with result tracking.
    """
    
    def __init__(self):
        self.api_key = "AIzaSyCuge0jQnDpHgrSyDwPaWNBvr5R7bm__CI"
        self.client = genai.Client(api_key=self.api_key)
        self.decoder = workflow.VisualDecoder()
        self.vocab_index = workflow.VocabularyIndex()
        self.orchestrator = OrchestratorAgent()
        self.results: List[TaskResult] = []
    
    def run(self, query: str):
        """Run the full pipeline."""
        logger.info("=" * 60)
        logger.info("🚀 VISUAL RAG PIPELINE")
        logger.info("=" * 60)
        
        # Phase 1: Orchestrator generates plan
        logger.info("\n📐 PHASE 1: ORCHESTRATOR")
        self.orchestrator.run(query)
        
        # Load the generated plan
        plan_path = os.path.join(self.orchestrator.gen_dir, "implementation_plan.md")
        if not os.path.exists(plan_path):
            logger.error("No plan generated!")
            return
        
        # Parse tasks from plan
        tasks = self._extract_tasks_from_plan(plan_path)
        
        if not tasks:
            logger.warning("No tasks found in plan")
            return
        
        logger.info(f"\n🔧 PHASE 2: WORKER AGENTS ({len(tasks)} tasks)")
        
        # Phase 2: Worker agents execute each task
        worker = WorkerAgent(
            client=self.client,
            decoder=self.decoder,
            vocab_index=self.vocab_index,
            output_dir=self.orchestrator.output_dir
        )
        
        for i, task in enumerate(tasks):
            logger.info(f"\n--- Task {i+1}/{len(tasks)} ---")
            result = worker.execute_task(task)
            self.results.append(result)
            
            if result.success:
                logger.info(f"   ✅ SUCCESS: {result.code_path}")
            else:
                logger.warning(f"   ❌ FAILED: {result.error}")
            
            time.sleep(2)  # Rate limiting
        
        # Summary
        successful = sum(1 for r in self.results if r.success)
        logger.info("\n" + "=" * 60)
        logger.info("✅ PIPELINE COMPLETE")
        logger.info(f"   Output: {self.orchestrator.output_dir}")
        logger.info(f"   Success: {successful}/{len(self.results)} tasks")
        logger.info("=" * 60)
        
        # Save summary
        self._save_summary()
    
    def _extract_tasks_from_plan(self, plan_path: str) -> List[Dict]:
        """Extract tasks from the markdown plan."""
        tasks = []
        
        with open(plan_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Simple parsing - look for Task sections
        import re
        task_pattern = r'### Task \d+:.*?\n(.*?)(?=### Task|\Z)'
        matches = re.findall(task_pattern, content, re.DOTALL)
        
        for match in matches:
            task = {}
            
            # Extract fields
            file_match = re.search(r'\*\*File\*\*:\s*`([^`]+)`', match)
            if file_match:
                task['filename'] = file_match.group(1)
            
            ref_match = re.search(r'\*\*Reference\*\*:\s*`([^`]+)`', match)
            if ref_match:
                task['reference_family'] = ref_match.group(1)
            
            desc_match = re.search(r'\*\*Description\*\*:\s*(.+?)(?=\n\n|\Z)', match, re.DOTALL)
            if desc_match:
                task['description'] = desc_match.group(1).strip()
            
            role_match = re.search(r'\*\*Role\*\*:\s*(\w+)', match)
            if role_match:
                task['role'] = role_match.group(1)
            
            if task.get('filename'):
                task['id'] = f"task_{len(tasks)+1}"
                tasks.append(task)
        
        return tasks
    
    def _save_summary(self):
        """Save execution summary as markdown."""
        summary_path = os.path.join(self.orchestrator.gen_dir, "execution_summary.md")
        
        lines = [
            "# Execution Summary\n",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
            f"**Output Directory:** `{self.orchestrator.output_dir}`\n\n",
            "## Results\n\n",
            "| Task | File | Status | Path |\n",
            "|------|------|--------|------|\n",
        ]
        
        for r in self.results:
            status = "✅ Success" if r.success else f"❌ {r.error or 'Failed'}"
            path = f"`{os.path.basename(r.code_path)}`" if r.code_path else "-"
            lines.append(f"| {r.task_id} | `{r.filename}` | {status} | {path} |\n")
        
        lines.append(f"\n## Statistics\n")
        lines.append(f"- **Total Tasks:** {len(self.results)}\n")
        lines.append(f"- **Successful:** {sum(1 for r in self.results if r.success)}\n")
        lines.append(f"- **Failed:** {sum(1 for r in self.results if not r.success)}\n")
        lines.append(f"- **Total Explorations:** {sum(r.explorations for r in self.results)}\n")
        
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        logger.info(f"📊 Summary saved: {summary_path}")


if __name__ == "__main__":
    # Run full pipeline
    pipeline = VisualRAGPipeline()
    pipeline.run("I need a dashboard with a transaction table. Full implementation.")



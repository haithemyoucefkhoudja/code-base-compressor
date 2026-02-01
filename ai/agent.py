"""
Visual RAG Agent - Orchestrator with Recurrent Explore/Exploit Loop
====================================================================
Principal Architect that uses visual codebase analysis with recursive sub-task exploration.
"""

import workflow
import os
import json
import logging
from typing import List, Dict, Any, Optional
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

# --- Orchestrator System Prompt (Explore/Exploit Loop) ---
ORCHESTRATOR_PROMPT = """
### SYSTEM ROLE: The Codebase Architect (Visual-Structural Logic)

You are the Principal Architect of a software repository. You analyze the **Visual DNA** of the existing codebase to create precise implementation plans.

### THE VISUAL DATA MODEL
1. **The Atlas:** A map of the entire repository - each colored block represents a file/component.
2. **The Legend:** A menu linking Component Names -> Visual Glyphs.
3. **The Tiles:** Color = Library, Texture = Syntax Type, Shape = Complexity.

### EXPLORE vs EXPLOIT DECISION LOOP

You operate in a **recurrent loop**. Each turn, you must decide:

**EXPLORE** (Need more information)
- Call `inspect_deeper(families)` to examine specific components
- The returned image shows the internal structure of those families
- Use this when you see interesting patterns you want to understand better
- Each task may reveal sub-families worth exploring

**EXPLOIT** (Ready to finalize)
- Call `finalize_plan(markdown_content)` when you have enough information
- Output a comprehensive implementation plan in MARKDOWN format
- Include all discovered patterns and their relationships

### TOOLS AVAILABLE

| Tool | When to Use |
|------|-------------|
| `bulk_search(concepts: list)` | Find families matching concepts in vocabulary |
| `inspect_deeper(families: list)` | EXPLORE: Drill into families, discover sub-components |
| `finalize_plan(markdown: str)` | EXPLOIT: Save final implementation plan and exit loop |

### EXECUTION FLOW

1. **Initial Search**: Scan vocabulary for relevant patterns
2. **First Inspection**: Inspect top candidates visually
3. **Decision Loop**:
   - If inspection reveals important sub-families → EXPLORE: inspect those too
   - If you have enough structural understanding → EXPLOIT: finalize the plan
4. **Repeat** until you call `finalize_plan`

### CRITICAL CONSTRAINTS
- ONLY use family names from the VOCABULARY LIST
- BATCH tool calls when possible
- Maximum depth: 3 exploration levels
- Always end with `finalize_plan`

### FINALIZE_PLAN OUTPUT FORMAT (MARKDOWN)

```markdown
# Implementation Plan: [Feature Name]

## Summary
[High-level architectural approach]

## Required Dependencies
- [library1]
- [library2]

## Discovered Patterns
| Pattern | Location | Usage |
|---------|----------|-------|
| [name]  | [vocab entry] | [how it's used] |

## Implementation Tasks

### Task 1: [Component Name]
- **File**: `path/to/file.tsx`
- **Role**: frontend | backend | logic
- **Reference**: `[Vocabulary Family Name]`
- **Visual Reasoning**: [Why this pattern was chosen based on color/density]
- **Description**: [What to build]

### Task 2: ...
```
"""


class OrchestratorAgent:
    """
    Principal Architect with recurrent Explore/Exploit decision loop.
    """
    
    MAX_EXPLORATION_DEPTH = 3
    
    def __init__(self):
        self.api_key = "AIzaSyCuge0jQnDpHgrSyDwPaWNBvr5R7bm__CI"
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
                    logger.info(f"Text response (no tools): {response.text[:200]}")
                break
            
            # Execute tools
            tool_outputs = []
            for call in response.function_calls:
                fname = call.name
                args = dict(call.args) if call.args else {}
                
                logger.info(f"⚡ Executing: {fname}")
                
                if fname == "bulk_search":
                    concepts = args.get("concepts", [])
                    result = self.vocab_index.bulk_search(concepts)
                    tool_outputs.append(types.Part.from_function_response(
                        name=fname, response={"matches": result}
                    ))
                
                elif fname == "inspect_deeper":
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
        
        if not finalized:
            logger.warning("⚠️ Max exploration depth reached without finalization")
            # Force save whatever we have
            self.composer.compose(os.path.join(self.gen_dir, "exploration_trace.png"))

    def _create_tools(self):
        """Define tools for function calling."""
        def bulk_search(concepts: list[str]) -> dict:
            """Search multiple concepts in vocabulary."""
            return self.vocab_index.bulk_search(concepts)
        
        def inspect_deeper(families: list[str]) -> dict:
            """EXPLORE: Inspect families to discover sub-patterns."""
            return {"inspected": families}
        
        def finalize_plan(markdown: str) -> dict:
            """EXPLOIT: Save the final implementation plan in markdown."""
            return {"status": "saved"}
        
        return [bulk_search, inspect_deeper, finalize_plan]

    def _execute_inspect(self, families: List[str]):
        """Execute inspection with multimodal response."""
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
                "top_imports": list(r.color_analysis.keys())[:8]
            }
            for r in results
        ]
        
        # Just return analysis data - images will be added separately to history
        # (The $ref multimodal response system is broken in the SDK)
        self._pending_visuals = stitched_bytes if stitched_bytes else None
        
        return types.Part.from_function_response(
            name="inspect_deeper",
            response={
                "analysis": analysis,
                "discovered_subfamilies": [n for r in results for n in r.neighbors[:3]],
                "has_visual": bool(stitched_bytes)
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
                    model="gemini-3-flash-preview",
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
        
        # Worker-specific logging
        log_path = os.path.join(output_dir, "worker.log")
        self.worker_logger = logging.getLogger("worker")
        fh = logging.FileHandler(log_path, encoding='utf-8')
        fh.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        self.worker_logger.addHandler(fh)
        self.worker_logger.setLevel(logging.INFO)
    
    def execute_task(self, task: Dict) -> TaskResult:
        """
        Execute a single task with explore/exploit loop.
        Returns TaskResult with generated code or error.
        """
        task_id = task.get("id", f"task_{int(time.time())}")
        filename = task.get("filename", "untitled.tsx")
        description = task.get("description", "")
        reference = task.get("reference_family", "")
        role = task.get("role", "frontend")
        
        self.worker_logger.info(f"\n{'='*60}")
        self.worker_logger.info(f"🔧 TASK: {task_id}")
        self.worker_logger.info(f"   File: {filename}")
        self.worker_logger.info(f"   Reference: {reference}")
        self.worker_logger.info(f"   Role: {role}")
        
        logger.info(f"🔧 Worker: {task_id} - {filename}")
        
        # --- Phase 1: Gather Reference Visual ---
        ref_bytes, ref_analysis = self._get_reference(reference)
        
        if not ref_bytes:
            self.worker_logger.warning(f"   No visual reference found for: {reference}")
        else:
            self.worker_logger.info(f"   Reference loaded: {len(ref_bytes)} bytes, density={ref_analysis.get('density')}")
        
        # --- Phase 2: Build Prompt ---
        prompt = self._build_prompt(filename, description, role, ref_analysis, ref_bytes)
        
        # --- Phase 3: Explore/Exploit Loop ---
        generated_code = None
        explorations = 0
        history = None
        explored_families = set()
        
        for depth in range(self.MAX_EXPLORATION_DEPTH):
            self.worker_logger.info(f"   Loop iteration {depth + 1}/{self.MAX_EXPLORATION_DEPTH}")
            
            try:
                response = self._call_api(prompt if history is None else history)
                
                if history is None:
                    history = self._init_history(prompt, response)
                elif response and response.candidates and response.candidates[0].content:
                    history.append(response.candidates[0].content)
                
                if not response:
                    self.worker_logger.error("   No API response")
                    break
                
                # Check for function calls
                if not response.function_calls:
                    # No tools called - check if model output text (fallback)
                    if response.text:
                        # Try to extract code from text response
                        extracted = self._extract_code_from_text(response.text)
                        if extracted:
                            generated_code = extracted
                            self.worker_logger.info("   Code extracted from text response")
                    break
                
                # Process function calls
                tool_outputs = []
                should_break = False
                
                for call in response.function_calls:
                    fname = call.name
                    args = dict(call.args) if call.args else {}
                    
                    self.worker_logger.info(f"   Tool: {fname}")
                    
                    if fname == "explore_reference":
                        # EXPLORE - dig deeper into references
                        families = args.get("families", [])
                        families = [f for f in families if f not in explored_families]
                        explored_families.update(families)
                        
                        if families:
                            explorations += 1
                            logger.info(f"   📖 Exploring: {families[:3]}...")
                            
                            stitched, results = self.decoder.bulk_inspect(families)
                            analysis = [
                                {
                                    "family": r.family,
                                    "neighbors": r.neighbors[:5],
                                    "density": r.density,
                                    "imports": list(r.color_analysis.keys())[:5]
                                }
                                for r in results
                            ]
                            
                            tool_outputs.append(types.Part.from_function_response(
                                name=fname,
                                response={"analysis": analysis, "count": len(results)}
                            ))
                            
                            # Add visual as user message
                            if stitched:
                                history.append(types.Content(
                                    role="user",
                                    parts=[
                                        types.Part(text=f"Visual of explored components: {families}"),
                                        types.Part.from_bytes(data=stitched, mime_type="image/png")
                                    ]
                                ))
                        else:
                            tool_outputs.append(types.Part.from_function_response(
                                name=fname,
                                response={"error": "No new families to explore"}
                            ))
                    
                    elif fname == "generate_code":
                        # EXPLOIT - generate final code
                        code = args.get("code", "")
                        
                        if code and len(code) > 10:
                            generated_code = code
                            logger.info(f"   ✅ Code generated: {len(code)} chars")
                            self.worker_logger.info(f"   Code generated: {len(code)} characters")
                            
                            tool_outputs.append(types.Part.from_function_response(
                                name=fname,
                                response={"status": "accepted", "length": len(code)}
                            ))
                            should_break = True
                        else:
                            tool_outputs.append(types.Part.from_function_response(
                                name=fname,
                                response={"status": "rejected", "error": "Code too short or empty"}
                            ))
                
                if should_break:
                    break
                
                # Add tool outputs to history
                if tool_outputs:
                    history.append(types.Content(role="tool", parts=tool_outputs))
                    
            except Exception as e:
                self.worker_logger.error(f"   Error: {e}")
                logger.error(f"   Worker error: {e}")
                return TaskResult(
                    task_id=task_id,
                    filename=filename,
                    success=False,
                    error=str(e),
                    explorations=explorations
                )
        
        # --- Phase 4: Save Generated Code ---
        if generated_code:
            code_path = self._save_code(filename, generated_code)
            self.worker_logger.info(f"   Saved: {code_path}")
            
            return TaskResult(
                task_id=task_id,
                filename=filename,
                success=True,
                code=generated_code,
                code_path=code_path,
                explorations=explorations
            )
        
        self.worker_logger.warning("   No code generated")
        return TaskResult(
            task_id=task_id,
            filename=filename,
            success=False,
            error="No code generated after max iterations",
            explorations=explorations
        )
    
    def _get_reference(self, reference: str) -> tuple:
        """Get visual reference and analysis for a component."""
        if not reference:
            return None, {}
        
        # Clean up reference (may have :: or \\ formatting)
        ref_clean = reference.replace("::", "/").split("/")[-1] if "::" in reference else reference
        
        # Try exact match first
        result = self.decoder.inspect(reference)
        
        if not result:
            # Try searching vocabulary
            matches = self.vocab_index.search(ref_clean)
            if matches:
                result = self.decoder.inspect(matches[0])
        
        if result:
            return result.image_bytes, {
                "family": result.family,
                "neighbors": result.neighbors[:10],
                "density": result.density,
                "imports": list(result.color_analysis.keys())[:10]
            }
        
        return None, {}
    
    def _build_prompt(self, filename: str, description: str, role: str, ref_analysis: dict, ref_bytes: Optional[bytes]) -> list:
        """Build the worker prompt with all context."""
        parts = [
            WORKER_PROMPT,
            f"\n### TARGET FILE\n**Path:** `{filename}`\n**Role:** {role}\n",
            f"\n### TASK DESCRIPTION\n{description}\n",
        ]
        
        if ref_analysis:
            parts.append(f"\n### REFERENCE ANALYSIS\n```json\n{json.dumps(ref_analysis, indent=2)}\n```\n")
        
        if ref_bytes:
            parts.append("\n### REFERENCE VISUAL\nAnalyze this image - it shows the visual DNA of the reference component. Clone its patterns.\n")
            parts.append(types.Part.from_bytes(data=ref_bytes, mime_type="image/png"))
        
        return parts
    
    def _call_api(self, content) -> Any:
        """Call API with retry logic."""
        # Define tools directly - these are just schemas since AFC is disabled
        def explore_reference(families: list[str]) -> dict:
            """Explore sub-components to understand their structure. Call this when you need to see how referenced components work internally."""
            return {}
        
        def generate_code(code: str) -> dict:
            """Generate and save the final implementation code. The 'code' parameter must contain the complete source code for the target file."""
            return {}
        
        config = types.GenerateContentConfig(
            tools=[explore_reference, generate_code],
            thinking_config=types.ThinkingConfig(include_thoughts=True),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            temperature=0.2
        )
        
        for attempt in range(3):
            try:
                return self.client.models.generate_content(
                    model="gemini-3-flash-preview",
                    contents=content,
                    config=config
                )
            except Exception as e:
                if "429" in str(e) or "503" in str(e):
                    wait = (attempt + 1) * 10
                    self.worker_logger.warning(f"   Rate limited, waiting {wait}s...")
                    time.sleep(wait)
                else:
                    raise
        return None
    
    def _init_history(self, prompt, response):
        """Initialize conversation history."""
        parts = []
        for p in prompt:
            if isinstance(p, str):
                parts.append(types.Part(text=p))
            elif isinstance(p, types.Part):
                parts.append(p)
        
        history = [types.Content(role="user", parts=parts)]
        
        if response and response.candidates and response.candidates[0].content:
            history.append(response.candidates[0].content)
        
        return history
    
    def _extract_code_from_text(self, text: str) -> Optional[str]:
        """Extract code from markdown text response (fallback)."""
        import re
        
        # Look for code blocks
        patterns = [
            r'```(?:tsx?|jsx?|typescript|javascript)\n(.*?)```',
            r'```\n(.*?)```',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            if matches:
                # Return the longest code block
                return max(matches, key=len)
        
        return None
    
    def _save_code(self, filename: str, code: str) -> str:
        """Save generated code to file."""
        # Create safe filename
        safe_name = filename.replace("/", "_").replace("\\", "_").replace(":", "_")
        
        # Preserve extension
        if not any(safe_name.endswith(ext) for ext in ['.tsx', '.ts', '.jsx', '.js', '.py', '.css']):
            safe_name += '.tsx'
        
        code_path = os.path.join(self.code_dir, safe_name)
        
        with open(code_path, 'w', encoding='utf-8') as f:
            f.write(code)
        
        return code_path


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



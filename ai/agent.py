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
import argparse
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


# --- Worker Agent System Prompt ---
WORKER_PROMPT = """
### SYSTEM ROLE: The Pattern-Matching Engineer

You are a Senior Developer who implements code by **deeply studying visual references**.
You are NOT creative. You are mimetic. You CLONE patterns with surgical precision.

### CRITICAL RULE: EXPLORE BEFORE YOU EXPLOIT

**YOU MUST EXPLORE AT LEAST ONCE before calling generate_code.**
- If you try to generate code without exploring, your output will be rejected.
- Deep exploration = Precise output. Shallow exploration = Garbage output.

### INPUTS
1. **Target File:** The filename you must create
2. **Description:** What logic this file must contain
3. **Reference Image:** A visual crop of an existing file (the "Golden Standard")
4. **Reference Analysis:** Structural data (neighbors, density, imports)

### TOOL PROTOCOL

**PHASE 1: MANDATORY EXPLORATION** (at least 1 call required)
Call `explore_reference(families)` to:
- Understand how imports are structured in similar files
- See how state management patterns work in this codebase
- Discover the actual APIs and hooks being used
- Learn the JSX/component patterns

**PHASE 2: CODE GENERATION** (only after exploration)
Call `generate_code(code, confidence)` with:
- `code`: Complete source code for the target file
- `confidence`: Your confidence level (1-10) that this code matches the patterns

### EXPLORATION STRATEGY

Look at the Reference Analysis "neighbors" - these are the most relevant families to explore.
If the reference shows:
- React hooks → Explore hook families to see their signatures
- External APIs → Explore those families to understand the interface
- Custom components → Explore those components to clone their props

### QUALITY CHECKLIST (before generate_code)
- [ ] Did I explore at least 1 related family?
- [ ] Do I understand the import patterns?
- [ ] Do I know the exact API signatures?
- [ ] Am I confident this matches the codebase style?

If ANY checkbox is unchecked → EXPLORE MORE.
"""


@dataclass
class TaskResult:
    """Result of a worker task execution."""
    task_id: str
    filename: str
    success: bool
    code: Optional[str] = None
    description: Optional[str] = None
    error: Optional[str] = None
    explorations: int = 0
    prompt_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    

class WorkerAgent:
    """
    Pattern-Matching Engineer - generates code based on visual references.
    Production-level implementation with proper explore/exploit loop.
    """
    
    MAX_EXPLORATION_DEPTH = 3

    def __init__(self, client, decoder, vocab_index, output_dir: str, legend_path: str):
        self.client = client
        self.decoder = decoder
        self.vocab_index = vocab_index
        self.output_dir = output_dir
        with open(legend_path, 'rb') as f:
            self.legend_bytes = f.read()        
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
        
        # Token tracking
        total_prompt_tokens = 0
        total_output_tokens = 0
        
        # --- Phase 1: Context ---
        ref_bytes, ref_analysis = self._get_reference(reference)
        
        # Get vocabulary for grounding
        vocab = self.vocab_index.get_all()
        vocab_sample = vocab  # All
        
        prompt:List[Part] = [
            Part(text=WORKER_PROMPT),
            Part(text=f"\n### TARGET FILE: {filename}\n### DESCRIPTION: {task.get('description', '')}\n"),
            Part(text=f"\n### VOCABULARY (Use ONLY these family names)\n{json.dumps(vocab_sample)}\n"),
            Part(text="\n### THE LEGEND (DECODE KEY)\nUse this to understand what the colors in the reference mean.\n"),
            Part.from_bytes(data=self.legend_bytes, mime_type="image/png")
        ]
        
        if ref_bytes:
            prompt.append(Part(text="\n### REFERENCE VISUAL (CLONE THIS)\n"))

            prompt.append(types.Part.from_bytes(data=ref_bytes, mime_type="image/png"))
        if ref_analysis:
            prompt.append(Part(text=f"\n### REFERENCE DATA\n{json.dumps(ref_analysis)}\n"))
        
        # --- Phase 2: Execution with Exploration Enforcement ---
        history = None
        generated_code = None
        exploration_count = 0
        confidence = 0
        MIN_EXPLORATIONS = 1  # Require at least 1 exploration before generating
        
        for depth in range(self.MAX_EXPLORATION_DEPTH):
            
            # API Call
            try:
                response = self._call_api(prompt if history is None else history)
            except Exception as e:
                return TaskResult(task_id, filename, False, error=str(e))
            if not response:
                logger.warning(f"API error, No Response")
                break
            
            # Track tokens
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                total_prompt_tokens += getattr(response.usage_metadata, 'prompt_token_count', 0)
                total_output_tokens += getattr(response.usage_metadata, 'candidates_token_count', 0)
                
            if history is None:
                history = self._init_history(prompt, response)
            elif response.candidates:
                history.append(response.candidates[0].content)
            
            if not response.function_calls:
                # Check for code block in text (fallback)
                if response.text and "```" in response.text and exploration_count >= MIN_EXPLORATIONS:
                    generated_code = self._extract_code_from_text(response.text)
                    if generated_code: break
                
                # If no tools and no code, and we are deep, break
                if depth > 2: break
                continue

            # Handle Tools
            tool_outputs = []
            should_break = False
            
            for call in response.function_calls:
                fname = call.name
                args = dict(call.args) if call.args else {}
                
                if fname == "generate_code":
                    code = args.get("code", "")
                    confidence = args.get("confidence", 5)
                    
                    # ENFORCE: Reject if no exploration done
                    if exploration_count < MIN_EXPLORATIONS:
                        tool_outputs.append(types.Part.from_function_response(
                            name=fname, 
                            response={
                                "error": "REJECTED: You MUST explore at least one reference family before generating code. Call explore_reference() first with families from the Reference Analysis neighbors.",
                                "exploration_count": exploration_count,
                                "required": MIN_EXPLORATIONS
                            }
                        ))
                        logger.info(f"   ⚠️ Rejected premature generate_code (explorations: {exploration_count})")
                    elif len(code) > 20:
                        generated_code = code
                        tool_outputs.append(types.Part.from_function_response(
                            name=fname, 
                            response={"status": "saved", "confidence": confidence}
                        ))
                        logger.info(f"   ✅ Code generated (confidence: {confidence}/10, explorations: {exploration_count})")
                        should_break = True
                
                elif fname == "explore_reference":
                    families = args.get("families", [])
                    if not families:
                        tool_outputs.append(types.Part.from_function_response(
                            name=fname, 
                            response={"error": "No families provided. Check the Reference Analysis 'neighbors' field for family names to explore."}
                        ))
                    else:
                        stitched, results = self.decoder.bulk_inspect(families)
                        exploration_count += 1
                        logger.info(f"   🔍 Exploration {exploration_count}: {len(families)} families → {len(results)} found")
                        
                        if not results:
                            tool_outputs.append(types.Part.from_function_response(
                                name=fname, 
                                response={
                                    "warning": "Families not found in Atlas. Try different family names from the Reference Analysis.",
                                    "explored": exploration_count
                                }
                            ))
                        else:
                            # Provide rich analysis back
                            analysis = [{"family": r.family, "props": r.props[:5], "neighbors": r.neighbors[:5]} for r in results]
                            tool_outputs.append(types.Part.from_function_response(
                                name=fname, 
                                response={
                                    "found": len(results),
                                    "analysis": analysis,
                                    "explored": exploration_count,
                                    "can_generate": exploration_count >= MIN_EXPLORATIONS
                                }
                            ))
                            if stitched:
                                history.append(types.Content(role="user", parts=[
                                    types.Part(text=f"Visual reference from exploration {exploration_count}:"),
                                    types.Part.from_bytes(data=stitched, mime_type="image/png")
                                ]))

            if should_break:
                break
                
            history.append(types.Content(role="tool", parts=tool_outputs))

        if generated_code:
            logger.info(f"   📊 Tokens: {total_prompt_tokens:,} prompt + {total_output_tokens:,} output = {total_prompt_tokens + total_output_tokens:,} total")
            return TaskResult(
                task_id, filename, True, 
                code=generated_code, 
                description=task.get('description', ''), 
                explorations=exploration_count,
                prompt_tokens=total_prompt_tokens,
                output_tokens=total_output_tokens,
                total_tokens=total_prompt_tokens + total_output_tokens
            )
        
        return TaskResult(
            task_id, filename, False, 
            error=f"No code generated after {exploration_count} explorations",
            prompt_tokens=total_prompt_tokens,
            output_tokens=total_output_tokens,
            total_tokens=total_prompt_tokens + total_output_tokens
        )

    def _get_reference(self, reference: str):
        if not reference: return None, {}
        # Try exact match
        res = self.decoder.inspect(reference)
        
        if res:
            image_bytes, result = res
            return image_bytes, {"family": result.family, "imports": list(result.color_analysis.keys())[:5], "props":result.props}
        return None, {}

    def _call_api(self, content):
        # Worker tools with confidence tracking
        def generate_code(code: str, confidence: int = 5) -> dict: 
            """Generate code for the target file. Confidence is 1-10 where 10 means 100% confident."""
            return {}
        def explore_reference(families: list[str]) -> dict: 
            """Explore reference families to understand patterns before generating code."""
            return {}
        
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



class VisualRAGPipeline:
    """
    Full pipeline: Orchestrator -> Worker Agents
    Production-level implementation with result tracking.
    """
    
    def __init__(self, tiles_dir: str):
        self.tiles_dir = tiles_dir
        self.api_key = "AIzaSyBvvlaZaKCY9RWYwOa_f1jlOJkO0p6mV2Q"
        self.client = genai.Client(api_key=self.api_key)
        self.decoder = workflow.VisualDecoder(tiles_dir)
        self.vocab_index = workflow.VocabularyIndex(tiles_dir)
        self.orchestrator = OrchestratorAgent(tiles_dir)
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
            output_dir=self.orchestrator.output_dir,
            legend_path=self.decoder.get_legend_path()
        )
        
        for i, task in enumerate(tasks):
            logger.info(f"\n--- Task {i+1}/{len(tasks)} ---")
            result = worker.execute_task(task)
            self.results.append(result)
            
            if result.success:
                logger.info(f"   ✅ SUCCESS: {result.filename}")
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
        
        # Save cookbook
        self._save_cookbook()
    
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
    
    def _save_cookbook(self):
        """Save all generated code as a single cookbook markdown file."""
        cookbook_path = os.path.join(self.orchestrator.gen_dir, "cookbook.md")
        
        lines = [
            "# Implementation Cookbook\n\n",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n",
            "---\n\n",
        ]
        
        # Table of contents
        lines.append("## Table of Contents\n\n")
        for i, r in enumerate(self.results):
            if r.success:
                anchor = r.filename.replace("/", "_").replace("\\", "_").replace(".", "_")
                lines.append(f"{i+1}. [{r.filename}](#{anchor})\n")
        lines.append("\n---\n\n")
        
        # Code sections
        for r in self.results:
            if r.success and r.code:
                anchor = r.filename.replace("/", "_").replace("\\", "_").replace(".", "_")
                ext = r.filename.split(".")[-1] if "." in r.filename else "tsx"
                
                lines.append(f"## {r.filename} {{#{anchor}}}\n\n")
                if r.description:
                    lines.append(f"**Description:** {r.description}\n\n")
                lines.append(f"```{ext}\n{r.code}\n```\n\n")
                lines.append("---\n\n")
        
        # Statistics
        total_prompt = sum(r.prompt_tokens for r in self.results)
        total_output = sum(r.output_tokens for r in self.results)
        total_all = sum(r.total_tokens for r in self.results)
        
        lines.append("## Summary\n\n")
        lines.append(f"- **Total Tasks:** {len(self.results)}\n")
        lines.append(f"- **Successful:** {sum(1 for r in self.results if r.success)}\n")
        lines.append(f"- **Failed:** {sum(1 for r in self.results if not r.success)}\n")
        lines.append(f"- **Total Explorations:** {sum(r.explorations for r in self.results)}\n\n")
        
        # Token usage table
        lines.append("### Token Usage (Workers)\n\n")
        lines.append("| Task | File | Prompt | Output | Total |\n")
        lines.append("|------|------|--------|--------|-------|\n")
        for r in self.results:
            lines.append(f"| {r.task_id} | `{r.filename}` | {r.prompt_tokens:,} | {r.output_tokens:,} | {r.total_tokens:,} |\n")
        lines.append(f"| **TOTAL** | | **{total_prompt:,}** | **{total_output:,}** | **{total_all:,}** |\n\n")
        
        if any(not r.success for r in self.results):
            lines.append("### Failed Tasks\n\n")
            for r in self.results:
                if not r.success:
                    lines.append(f"- `{r.filename}`: {r.error}\n")
        
        with open(cookbook_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        logger.info(f"📚 Cookbook saved: {cookbook_path}")
        logger.info(f"📊 Worker Tokens: {total_prompt:,} prompt + {total_output:,} output = {total_all:,} total")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Visual RAG Agent - Analyze codebase and generate implementation plans.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python agent.py --tiles ./repo_blimpt_tiles --query "Add user authentication"
  python agent.py -t ./my_project_tiles -q "Implement MCP integration"
"""
    )
    parser.add_argument(
        "--tiles", "-t",
        required=True,
        help="Path to the tiles directory (e.g., repo_name_tiles/)"
    )
    parser.add_argument(
        "--query", "-q",
        required=True,
        help="The implementation query/request"
    )
    
    args = parser.parse_args()
    
    # Validate tiles directory
    if not os.path.isdir(args.tiles):
        print(f"Error: Tiles directory not found: {args.tiles}")
        exit(1)
    
    # Run pipeline
    pipeline = VisualRAGPipeline(args.tiles)
    pipeline.run(args.query)

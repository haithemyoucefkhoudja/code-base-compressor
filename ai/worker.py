from google.genai.types import Part
import os
import json
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass
import time

try:
    from google.genai import types
    import PIL.Image
except ImportError:
    raise ImportError("CRITICAL: 'google-genai' library is required.")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
PIL.Image.MAX_IMAGE_PIXELS = None

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
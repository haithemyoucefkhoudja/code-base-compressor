import os
import logging
import base64
import io
import tiktoken
import PIL.Image
from datetime import datetime
from typing import Any, Dict, List
import json
logger = logging.getLogger(__name__)

class CostTracker:
    _instance = None
    

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CostTracker, cls).__new__(cls)
            cls._instance.reset()
        return cls._instance

    def reset(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        self.model_name = "default"
        self.log_file_path = None

    def set_model(self, model_name: str):
        self.model_name = model_name
    
    def set_pricing(self, model_pricing:Dict[str,float]):
        self.pricing = model_pricing

    def set_log_path(self, path: str):
        self.log_file_path = path
        # Ensure directory exists
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def track_response(self, response: Any, request_messages: List[Any] | None = None):
        """
        Track usage from a LangChain AIMessage response.
        If usage is missing, estimates using tiktoken and image dimensions.
        """
        try:
            finish_reason = response.response_metadata.get("finish_reason")
            logger.info(f"🏁 [FINISH REASON]: {finish_reason}")

            usage = response.response_metadata.get("token_usage") or getattr(response, "usage_metadata", None) or {}
            
            logger.info(f"📊 [PROMPT USAGE]: {json.dumps(usage, indent=2)}")
            
            input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens", 0)
            output_tokens = usage.get("output_tokens") or usage.get("completion_tokens", 0)
            prompt_details = usage.get("prompt_tokens_details") or {}
            cached_tokens = (
                prompt_details.get("cached_tokens", 0) or 
                usage.get("input_token_details",{}).get("cache_read", 0) or 
                usage.get("cached_prompt_tokens", 0) or 
                usage.get("cached_tokens",0)
            )
            
            logger.info(f"🔢 [TOKEN COUNT]: Input: {input_tokens:,} | Output: {output_tokens:,} | Cached: {cached_tokens:,}")
            
            # Fallback to estimation
            if input_tokens == 0 or output_tokens == 0:
                logger.info("🕒 Estimating tokens (Tiktoken/Image Fallback)...")
                enc = tiktoken.get_encoding("cl100k_base")
                
                # Estimate Output
                if output_tokens == 0 and response.content:
                     output_tokens = len(enc.encode(str(response.content)))
                
                # Estimate Input
                if input_tokens == 0 and request_messages:
                    for msg in request_messages:
                        content = msg.content
                        if isinstance(content, str):
                            input_tokens += len(enc.encode(content))
                        elif isinstance(content, list):
                            for part in content:
                                if part.get("type") == "text":
                                    input_tokens += len(enc.encode(part["text"]))
                                elif part.get("type") == "image_url":
                                    input_tokens += self._estimate_image_tokens(part["image_url"]["url"])
                
            self._add_usage(input_tokens, output_tokens,cached_tokens)
            
        except Exception as e:
            logger.warning(f"Failed to track cost: {e}")

    def _estimate_image_tokens(self, image_url: str) -> int:
        """Formula: T = min(2, max(H // 560, 1)) * min(2, max(W // 560, 1)) * 1601"""
        try:
            if not image_url.startswith("data:image"):
                return 1601 # Fallback for non-base64
                
            header, encoded = image_url.split(",", 1)
            image_data = base64.b64decode(encoded)
            img = PIL.Image.open(io.BytesIO(image_data))
            W, H = img.size
            
            tokens = min(2, max(H // 560, 1)) * min(2, max(W // 560, 1)) * 1601
            return tokens
        except Exception as e:
            logger.warning(f"Image estimation failed: {e}")
            return 1601

    def _add_usage(self, input_tokens: int, output_tokens: int, cached_tokens: int):
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        cost_input = ((input_tokens - cached_tokens) / 1_000_000) * self.pricing.get("input", 0)
        cost_cached = (cached_tokens / 1_000_000) * self.pricing.get("cache", 0)
        cost_input += cost_cached
        cost_output = (output_tokens / 1_000_000) * self.pricing["output"]
        
        current_cost = cost_input + cost_output
        self.total_cost += current_cost
        
        msg = f"📊 [COST] Run: ↓{input_tokens:,} ↑{output_tokens:,} | 💵 Subtotal: ${current_cost:.4f} | 💰 Accrued: ${self.total_cost:.4f}"
        logger.info(msg)
        
        if self.log_file_path:
            with open(self.log_file_path, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {msg}\n")

    def get_summary_string(self) -> str:
        lines = []
        lines.append("="*40)
        lines.append(f"💰 BUDGET REPORT ({self.model_name})")
        lines.append("-"*40)
        lines.append(f"Input Tokens:  {self.total_input_tokens:,}")
        lines.append(f"Output Tokens: {self.total_output_tokens:,}")
        lines.append(f"Total Tokens:  {self.total_input_tokens + self.total_output_tokens:,}")
        lines.append("-"*40)
        lines.append(f"TOTAL ESTIMATED COST: ${self.total_cost:.4f}")
        lines.append("="*40)
        return "\n".join(lines)

    def print_summary(self):
        logger.info("\n" + self.get_summary_string() + "\n")

import logging
import tiktoken
from typing import Any 

logger = logging.getLogger(__name__)

class CostTracker:
    _instance = None
    
    # Approximate pricing (per 1M tokens) - Update as needed
    PRICING = {
        "gpt-4o": {"input": 5.00, "output": 15.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
        # Fallback generic
        "default": {"input": 1.00, "output": 1.00} 
    }

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

    def set_model(self, model_name: str):
        self.model_name = model_name

    def track_response(self, response: Any):
        """
        Track usage from a LangChain AIMessage response.
        """
        try:
            usage = response.response_metadata.get("token_usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            
            # If usage not provided by provider (some don't), estimate
            if input_tokens == 0 and response.content:
                 # Rough estimation
                 enc = tiktoken.get_encoding("cl100k_base")
                 output_tokens = len(enc.encode(str(response.content)))
                 # Cannot easily estimate prompt without input text, assume 1k for now or skip
                 input_tokens = 0 
            
            self._add_usage(input_tokens, output_tokens)
            
        except Exception as e:
            logger.warning(f"Failed to track cost: {e}")

    def _add_usage(self, input_tokens: int, output_tokens: int):
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        
        # Calculate Cost
        price = self.PRICING.get(self.model_name) or self.PRICING.get("default")
        
        cost_input = (input_tokens / 1_000_000) * price["input"]
        cost_output = (output_tokens / 1_000_000) * price["output"]
        
        self.total_cost += (cost_input + cost_output)

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
        print("\n" + self.get_summary_string() + "\n")

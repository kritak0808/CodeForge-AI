import logging
from typing import Dict, Tuple

logger = logging.getLogger("shared-llm.cost_tracker")

# Pricing structure: (input_cost_per_token, output_cost_per_token)
PRICING_MAP: Dict[Tuple[str, str], Tuple[float, float]] = {
    # OpenAI
    ("openai", "gpt-4-turbo"): (0.00001, 0.00003),
    ("openai", "gpt-4-turbo-2024-04-09"): (0.00001, 0.00003),
    ("openai", "gpt-4o"): (0.000005, 0.000015),
    ("openai", "gpt-4o-mini"): (0.00000015, 0.0000006),
    ("openai", "gpt-4"): (0.00003, 0.00006),
    ("openai", "gpt-3.5-turbo"): (0.0000005, 0.0000015),
    
    # Anthropic
    ("anthropic", "claude-3-opus-20240229"): (0.000015, 0.000075),
    ("anthropic", "claude-3-sonnet-20240229"): (0.000003, 0.000015),
    ("anthropic", "claude-3-haiku-20240307"): (0.00000025, 0.00000125),
    ("anthropic", "claude-3-5-sonnet-20240620"): (0.000003, 0.000015),
    
    # Gemini
    ("gemini", "gemini-1.5-pro"): (0.0000035, 0.0000105),
    ("gemini", "gemini-1.5-flash"): (0.000000075, 0.0000003),
    ("gemini", "gemini-1.0-pro"): (0.0000005, 0.0000015),
}

# Fallbacks by provider: (input_cost_per_token, output_cost_per_token)
PROVIDER_FALLBACKS: Dict[str, Tuple[float, float]] = {
    "openai": (0.000005, 0.000015),      # gpt-4o rates
    "anthropic": (0.000003, 0.000015),   # claude-3-sonnet rates
    "gemini": (0.0000035, 0.0000105),    # gemini-1.5-pro rates
}

class CostTracker:
    def calculate_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """Calculate the cost in USD based on provider, model, and token counts."""
        # Clean up provider and model names
        provider = provider.lower()
        model = model.lower()
        
        # Check direct pricing map
        rates = PRICING_MAP.get((provider, model))
        if rates is None:
            # Check model name substring matching
            matched_key = None
            for key in PRICING_MAP.keys():
                if key[0] == provider and key[1] in model:
                    matched_key = key
                    break
            
            if matched_key:
                rates = PRICING_MAP[matched_key]
            else:
                # Use provider fallback
                rates = PROVIDER_FALLBACKS.get(provider, (0.000002, 0.00001)) # absolute fallback
                logger.info(f"Using fallback pricing for {provider}/{model}: {rates}")
                
        input_rate, output_rate = rates
        cost = (input_tokens * input_rate) + (output_tokens * output_rate)
        return round(cost, 6)

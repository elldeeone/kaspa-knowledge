import os
import requests
from typing import Dict, Any, Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_URL = os.getenv(
    "OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions"
)


class OpenRouterLLMError(Exception):
    pass


class LLMInterface:
    def __init__(self, model: str = "openai/gpt-4.1"):
        if not OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY environment variable not set.")
        self.api_key = OPENROUTER_API_KEY
        self.api_url = OPENROUTER_API_URL
        self.model = model
        self.costs = []  # Track cost per request

    def build_prompt(self, template: str, variables: Dict[str, Any]) -> str:
        return template.format(**variables)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(OpenRouterLLMError),
    )
    def call_llm(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
    ) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model or self.model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt or "You are a helpful assistant.",
                },
                {"role": "user", "content": prompt},
            ],
        }
        try:
            response = requests.post(
                self.api_url, json=payload, headers=headers, timeout=60
            )
            response.raise_for_status()
            data = response.json()
            # Cost monitoring (if available)
            if "usage" in data:
                self.costs.append(data["usage"])
            return self.parse_response(data)
        except requests.RequestException as e:
            raise OpenRouterLLMError(f"Request failed: {e}")
        except Exception as e:
            raise OpenRouterLLMError(f"Unexpected error: {e}")

    def parse_response(self, data: Dict[str, Any]) -> str:
        if "choices" in data and data["choices"]:
            return data["choices"][0]["message"]["content"]
        raise OpenRouterLLMError("No valid response from LLM.")

    def get_cost_summary(self) -> Dict[str, Any]:
        # Aggregate cost info if available
        total_tokens = sum(c.get("total_tokens", 0) for c in self.costs)
        total_cost = sum(c.get("total_cost", 0) for c in self.costs)
        return {"total_tokens": total_tokens, "total_cost": total_cost}


# Example usage
if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    llm = LLMInterface()
    prompt = "Summarize the following text: Kaspa is a fast, scalable blockchain."
    try:
        result = llm.call_llm(prompt)
        print("LLM Response:", result)
    except Exception as e:
        print("Error:", e)

#!/usr/bin/env python3
"""
Prompt loader utility for Kaspa Knowledge Hub

This module handles loading LLM prompts from external text files,
making the system more maintainable and flexible.
"""

from pathlib import Path


class PromptLoader:
    def __init__(self, prompts_dir: str = "scripts/prompts"):
        self.prompts_dir = Path(prompts_dir)
        self._prompt_cache = {}

    def load_prompt(self, prompt_name: str) -> str:
        """Load a prompt from a text file."""
        if prompt_name in self._prompt_cache:
            return self._prompt_cache[prompt_name]

        prompt_path = self.prompts_dir / f"{prompt_name}.txt"

        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt_text = f.read().strip()
                self._prompt_cache[prompt_name] = prompt_text
                return prompt_text
        except Exception as e:
            raise Exception(f"Error loading prompt {prompt_name}: {e}")

    def format_prompt(self, prompt_name: str, **kwargs) -> str:
        """Load and format a prompt with provided variables."""
        prompt_template = self.load_prompt(prompt_name)
        try:
            return prompt_template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing required variable for prompt {prompt_name}: {e}")

    def get_system_prompt(self, prompt_name: str) -> str:
        """Load a system prompt (convention: prompt_name + '_system')."""
        system_prompt_name = f"{prompt_name}_system"
        return self.load_prompt(system_prompt_name)

    def clear_cache(self):
        """Clear the prompt cache (useful for development/testing)."""
        self._prompt_cache.clear()


# Global instance for convenience
prompt_loader = PromptLoader()

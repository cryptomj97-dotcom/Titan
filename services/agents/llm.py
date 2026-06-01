import json
import os
import re
from typing import Any, Dict, Optional, Type

import requests
from pydantic import BaseModel, ValidationError


class LLMClient:
    """Simple BYOK-capable LLM router for Gemini, OpenAI, and Anthropic."""

    def __init__(self) -> None:
        self.gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.openai_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-3.5-opus")

    @property
    def is_configured(self) -> bool:
        return bool(self.gemini_key or self.openai_key or self.anthropic_key)

    @property
    def provider_name(self) -> str:
        if self.gemini_key:
            return "Gemini"
        if self.openai_key:
            return "OpenAI"
        if self.anthropic_key:
            return "Anthropic"
        return "None"

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Type[BaseModel],
        temperature: float = 0.0,
        max_tokens: int = 512,
    ) -> BaseModel:
        if self.gemini_key:
            response_text = self._call_gemini(system_prompt, user_prompt, temperature, max_tokens)
        elif self.openai_key:
            response_text = self._call_openai(system_prompt, user_prompt, temperature, max_tokens)
        elif self.anthropic_key:
            response_text = self._call_anthropic(system_prompt, user_prompt, temperature, max_tokens)
        else:
            raise RuntimeError("No configured LLM provider. Set GEMINI_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY.")

        payload = self._extract_json_payload(response_text)
        try:
            return schema.parse_obj(payload)
        except ValidationError as exc:
            raise RuntimeError(f"LLM response validation failed: {exc}") from exc

    def _call_openai(self, system_prompt: str, user_prompt: str, temperature: float, max_tokens: int) -> str:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openai_key}",
            "Content-Type": "application/json",
        }
        body: Dict[str, Any] = {
            "model": self.openai_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        response = requests.post(url, headers=headers, json=body, timeout=30)
        response.raise_for_status()
        data = response.json()
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        text = message.get("content", "")
        if not text:
            raise RuntimeError("OpenAI returned an empty response.")
        return text

    def _call_gemini(self, system_prompt: str, user_prompt: str, temperature: float, max_tokens: int) -> str:
        url = f"https://generativeai.googleapis.com/v1beta2/models/{self.gemini_model}:generate"
        headers = {
            "Authorization": f"Bearer {self.gemini_key}",
            "Content-Type": "application/json",
        }
        body: Dict[str, Any] = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            "prompt": {
                "messages": [
                    {"author": "system", "content": {"type": "text", "text": system_prompt}},
                    {"author": "user", "content": {"type": "text", "text": user_prompt}},
                ]
            },
        }

        response = requests.post(url, headers=headers, json=body, timeout=30)
        response.raise_for_status()
        data = response.json()
        return self._extract_gemini_text(data)

    def _call_anthropic(self, system_prompt: str, user_prompt: str, temperature: float, max_tokens: int) -> str:
        url = "https://api.anthropic.com/v1/complete"
        headers = {
            "x-api-key": self.anthropic_key,
            "Content-Type": "application/json",
        }
        prompt_text = f"{system_prompt}\n\n{user_prompt}"
        body: Dict[str, Any] = {
            "model": self.anthropic_model,
            "prompt": prompt_text,
            "max_tokens_to_sample": max_tokens,
            "temperature": temperature,
        }

        response = requests.post(url, headers=headers, json=body, timeout=30)
        response.raise_for_status()
        data = response.json()
        text = data.get("completion", "")
        if not text:
            raise RuntimeError("Anthropic returned an empty response.")
        return text

    def _extract_gemini_text(self, payload: Dict[str, Any]) -> str:
        if payload.get("candidates"):
            candidate = payload["candidates"][0]
            content = candidate.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return "".join([part.get("text", "") for part in content if isinstance(part, dict)])

        if payload.get("output_text"):
            return payload["output_text"]
        if payload.get("response") and isinstance(payload["response"], dict):
            return payload["response"].get("content", "")

        raise RuntimeError("Could not parse Gemini response payload.")

    def _extract_json_payload(self, text: str) -> Dict[str, Any]:
        if not text:
            raise RuntimeError("LLM response is empty")

        text = text.strip()
        # Try to parse raw JSON first, otherwise extract the first JSON object.
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        start_index = text.find("{")
        if start_index == -1:
            raise RuntimeError("Unable to locate JSON payload in LLM response.")

        depth = 0
        for index in range(start_index, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start_index : index + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        continue

        raise RuntimeError("Unable to extract valid JSON from LLM response.")

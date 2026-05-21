"""MiMo LLM client (shared with research agent — same interface)."""
import json
import httpx
from typing import Optional
from .config import MIMO_BASE_URL, MIMO_API_KEY, MIMO_MODEL


class MiMoClient:
    def __init__(self, base_url: str = MIMO_BASE_URL, api_key: str = MIMO_API_KEY, model: str = MIMO_MODEL):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.client = httpx.AsyncClient(timeout=180.0)

    async def chat(self, prompt: str, system: Optional[str] = None,
                   temperature: float = 0.2, max_tokens: int = 4096,
                   json_mode: bool = False) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model, "messages": messages,
            "temperature": temperature, "max_tokens": max_tokens,
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        r = await self.client.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    async def chat_json(self, prompt: str, system: Optional[str] = None, **kwargs) -> dict:
        for attempt in range(2):
            try:
                content = await self.chat(prompt, system=system, json_mode=True, **kwargs)
                # Strip markdown code fences if model adds them
                content = content.strip()
                if content.startswith("```"):
                    content = content.split("\n", 1)[1] if "\n" in content else content
                    if content.endswith("```"):
                        content = content.rsplit("```", 1)[0]
                return json.loads(content)
            except (json.JSONDecodeError, httpx.HTTPError):
                if attempt == 1:
                    raise
                prompt = f"{prompt}\n\nReturn valid JSON only, no commentary or markdown."

    async def close(self):
        await self.client.aclose()

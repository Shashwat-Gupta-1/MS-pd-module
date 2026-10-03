"""The single place where the LLM API is called (Google Gemini).
Agents only use `get_llm().complete_json`."""
import json
import time
from typing import Protocol
import httpx
from app.core.config import settings


class LLMClient(Protocol):
    def complete_json(self, system: str, user: str) -> dict: ...


class GeminiClient:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or settings.gemini_api_key
        # Strip 'models/' prefix if user included it
        model_name = model or settings.gemini_model or "gemini-3.5-flash"
        self.model = model_name.removeprefix("models/")

    def complete_json(self, system: str, user: str, retries: int = 5) -> dict:
        """Send a system + user prompt to Google Gemini and return parsed JSON."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        prompt_text = f"System Instructions:\n{system}\n\nUser Data:\n{user}"
        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt_text}]
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json"
            }
        }
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key
        }

        for attempt in range(retries):
            try:
                r = httpx.post(url, json=payload, headers=headers, timeout=60.0)
            except (httpx.TimeoutException, httpx.NetworkError) as net_err:
                print(f"\n[Gemini Attempt {attempt + 1}/{retries} - Network/Timeout Error]: {net_err}")
                time.sleep(2 ** attempt)
                continue

            if r.status_code == 200:
                res_content = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                if res_content.startswith("```"):
                    res_content = res_content.strip("`").removeprefix("json").strip()
                return json.loads(res_content)

            print(f"\n[Gemini Attempt {attempt + 1}/{retries} - Status {r.status_code}]: {r.text}")

            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(2 ** attempt)
                continue

            if r.status_code == 404:
                print(f"\n[Gemini Info]: Model '{self.model}' not found on endpoint. Querying available models...")
                try:
                    list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={self.api_key}"
                    list_resp = httpx.get(list_url, timeout=15)
                    if list_resp.status_code == 200:
                        models_data = list_resp.json().get("models", [])
                        valid_models = [
                            m["name"].removeprefix("models/")
                            for m in models_data
                            if "generateContent" in m.get("supportedGenerationMethods", [])
                        ]
                        print(f"Available Gemini Models for your key: {valid_models}")
                        fallback = next((m for m in valid_models if "flash" in m or "pro" in m), None)
                        if fallback and fallback != self.model:
                            print(f"--> Auto-switching to working model: '{fallback}'\n")
                            self.model = fallback
                            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
                            continue
                except Exception as ex:
                    print(f"Failed to query Gemini models: {ex}")

            r.raise_for_status()
        raise RuntimeError("Gemini LLM call failed after retries")


def get_llm() -> LLMClient:
    return GeminiClient()





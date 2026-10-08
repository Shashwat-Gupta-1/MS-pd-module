"""The single place where the LLM API is called (Google Gemini).
Agents use `get_llm().complete_json` for both text-only and multimodal vision tasks.
"""
import base64
import json
import logging
import time
from typing import Optional, Protocol
import httpx
from app.core.config import settings

log = logging.getLogger("msfincap.llm")


class LLMClient(Protocol):
    def complete_json(
        self,
        system: str,
        user: str,
        retries: int = 5,
        image_bytes: Optional[bytes] = None,
        mime_type: str = "image/jpeg",
    ) -> dict: ...


class GeminiClient:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.gemini_api_key
        # Strip 'models/' prefix if user included it
        model_name = model or settings.gemini_model or "gemini-3.6-flash"
        self.model = model_name.removeprefix("models/")

    def complete_json(
        self,
        system: str,
        user: str,
        retries: int = 5,
        image_bytes: Optional[bytes] = None,
        mime_type: str = "image/jpeg",
    ) -> dict:
        """Send a system + user prompt (and optional image) to Google Gemini and return parsed JSON."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        prompt_text = f"System Instructions:\n{system}\n\nUser Data / Prompt:\n{user}"

        parts = [{"text": prompt_text}]

        if image_bytes:
            b64_data = base64.b64encode(image_bytes).decode("utf-8")
            parts.append({
                "inline_data": {
                    "mime_type": mime_type,
                    "data": b64_data,
                }
            })

        payload = {
            "contents": [
                {
                    "parts": parts
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "maxOutputTokens": 4096,
            },
        }
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

        for attempt in range(retries):
            try:
                r = httpx.post(url, json=payload, headers=headers, timeout=90.0)
            except (httpx.TimeoutException, httpx.NetworkError) as net_err:
                log.warning("[Gemini Attempt %d/%d - Network/Timeout Error]: %s", attempt + 1, retries, net_err)
                time.sleep(2 ** attempt)
                continue

            if r.status_code == 200:
                res_content = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                return self._parse_json_response(res_content)

            log.warning("[Gemini Attempt %d/%d - Status %d]: %s", attempt + 1, retries, r.status_code, r.text)

            if r.status_code == 429 or r.status_code >= 500:
                # If current model is overloaded (503/429), sequentially rotate to the next alternate flash model
                fallback_models = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.7-flash", "gemini-3.1-flash-lite"]
                current_idx = fallback_models.index(self.model) if self.model in fallback_models else 0
                next_model = fallback_models[(current_idx + 1) % len(fallback_models)]
                log.info("--> Overload/Quota limit on '%s'. Auto-switching to next fallback: '%s'", self.model, next_model)
                self.model = next_model
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
                time.sleep(1.5)
                continue

            if r.status_code == 404:
                log.info("[Gemini Info]: Model '%s' not found on endpoint. Querying available models...", self.model)
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
                        log.info("Available Gemini Models for your key: %s", valid_models)
                        fallback = next((m for m in valid_models if "flash" in m or "pro" in m), None)
                        if fallback and fallback != self.model:
                            log.info("--> Auto-switching to working model: '%s'", fallback)
                            self.model = fallback
                            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
                            continue
                except Exception as ex:
                    log.error("Failed to query Gemini models: %s", ex)

            r.raise_for_status()
        raise RuntimeError("Gemini LLM call failed after retries")

    @staticmethod
    def _parse_json_response(res_content: str) -> dict:
        """Robustly parses JSON even if Gemini outputs markdown fences, trailing comments, or extra data."""
        res_content = res_content.strip()
        
        # 1. Try direct json.loads
        try:
            return json.loads(res_content)
        except json.JSONDecodeError:
            pass

        # 2. Extract content inside markdown fences
        if "```" in res_content:
            parts = res_content.split("```")
            for part in parts:
                p = part.strip()
                if p.startswith("json"):
                    p = p[4:].strip()
                try:
                    return json.loads(p)
                except json.JSONDecodeError:
                    pass

        # 3. Find outer braces { ... }
        start_brace = res_content.find("{")
        end_brace = res_content.rfind("}")
        if start_brace != -1 and end_brace > start_brace:
            json_substr = res_content[start_brace : end_brace + 1]
            try:
                return json.loads(json_substr)
            except json.JSONDecodeError:
                pass

        # 4. Use raw_decode to parse first valid JSON object and ignore trailing extra characters
        if start_brace != -1:
            try:
                obj, _ = json.JSONDecoder().raw_decode(res_content[start_brace:])
                if isinstance(obj, dict):
                    return obj
            except Exception:
                pass

        # 5. Attempt progressive repair on truncated JSON output
        if start_brace != -1:
            raw = res_content[start_brace:]
            for cutoff_char in ["}", ",", "]"]:
                pos = raw.rfind(cutoff_char)
                if pos > 0:
                    candidate = raw[: pos + (1 if cutoff_char in "}]" else 0)].strip()
                    open_curly = candidate.count("{") - candidate.count("}")
                    open_square = candidate.count("[") - candidate.count("]")
                    if candidate.count('"') % 2 != 0:
                        candidate += '"'
                    candidate += "]" * max(0, open_square)
                    candidate += "}" * max(0, open_curly)
                    try:
                        obj = json.loads(candidate)
                        if isinstance(obj, dict):
                            return obj
                    except Exception:
                        pass

        # 6. Last resort fallback
        return json.loads(res_content)


def get_llm(model: Optional[str] = None) -> LLMClient:
    return GeminiClient(model=model)

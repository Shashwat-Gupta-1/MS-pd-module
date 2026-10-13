import json
import base64
import time
import logging
import threading
from typing import Literal, Dict, Any, Union, Optional, Protocol
import httpx
from groq import Groq, RateLimitError, APIStatusError, APIConnectionError
from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMUnavailableError(Exception):
    """Raised when the LLM service is unavailable (e.g. repeated 429 rate limit or 5xx server error)."""
    pass


class LLMMalformedResponseError(Exception):
    """Raised when the LLM fails to return parseable JSON after retrying."""
    pass


class GroqKeyPool:
    """
    Thread-safe Round-Robin Pool for Groq API keys.
    Distributes requests equally across all configured API keys to maximize throughput
    and automatically rotates to the next key on 429 rate limit errors.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._clients: Dict[str, Groq] = {}
        self._keys: list[str] = []
        self._index: int = 0
        self._refresh_keys()

    def _refresh_keys(self) -> None:
        pool_keys = settings.groq_api_keys_pool
        if not pool_keys and settings.GROQ_API_KEY and settings.GROQ_API_KEY.strip().startswith("gsk_"):
            pool_keys = [settings.GROQ_API_KEY.strip().strip('"\'')]
        self._keys = pool_keys
        for k in self._keys:
            if k not in self._clients:
                self._clients[k] = Groq(api_key=k)

    @property
    def total_keys(self) -> int:
        if not self._keys:
            self._refresh_keys()
        return len(self._keys)

    def get_client_and_key(self) -> tuple[Optional[Groq], str]:
        with self._lock:
            if not self._keys:
                self._refresh_keys()
            if not self._keys:
                fallback_key = settings.GROQ_API_KEY or "demo_key"
                if fallback_key not in self._clients:
                    self._clients[fallback_key] = Groq(api_key=fallback_key)
                return self._clients[fallback_key], fallback_key

            idx = self._index % len(self._keys)
            key = self._keys[idx]
            self._index = (self._index + 1) % len(self._keys)
            return self._clients[key], key

    @staticmethod
    def mask_key(key: str) -> str:
        if not key or len(key) < 10:
            return "..."
        return f"{key[:7]}...{key[-4:]}"


_key_pool = GroqKeyPool()


def get_groq_client() -> Groq:
    """Returns the next round-robin Groq client instance from the key pool."""
    client, _ = _key_pool.get_client_and_key()
    if client is None:
        return Groq(api_key=settings.GROQ_API_KEY or "demo_key")
    return client


def _execute_groq_call(call_builder: Any) -> Any:
    """
    Executes a Groq API call with automatic round-robin key rotation on 429 rate limits.
    If a key hits a 429, it immediately tries the next key in the pool without delay.
    If all keys in the pool are rate-limited, it performs exponential backoff.
    """
    total_keys = max(1, _key_pool.total_keys)
    max_pool_cycles = 2
    total_attempts = max(3, total_keys * max_pool_cycles)

    last_exc = None
    for attempt in range(total_attempts):
        client, key = _key_pool.get_client_and_key()
        masked = _key_pool.mask_key(key)
        try:
            return call_builder(client)
        except (RateLimitError, APIConnectionError) as e:
            last_exc = e
            msg = str(e).lower()
            if isinstance(e, RateLimitError) or "429" in msg or "rate limit" in msg:
                logger.warning(
                    f"Groq API 429 rate limit on key {masked} (attempt {attempt + 1}/{total_attempts}). "
                    f"Failing over to next key in round-robin pool..."
                )
                if (attempt + 1) % total_keys == 0:
                    time.sleep(1.0)
                continue
            else:
                wait_time = min(4.0, (2 ** (attempt % 3)) * 0.5)
                logger.warning(f"Groq API connection error on key {masked}: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
        except APIStatusError as e:
            last_exc = e
            if e.status_code == 429:
                logger.warning(
                    f"Groq API 429 on key {masked} (attempt {attempt + 1}/{total_attempts}). "
                    f"Failing over to next key in round-robin pool..."
                )
                if (attempt + 1) % total_keys == 0:
                    time.sleep(1.0)
                continue
            elif e.status_code >= 500:
                wait_time = min(4.0, (2 ** (attempt % 3)) * 0.5)
                logger.warning(f"Groq API {e.status_code} server error on key {masked}: {e.message}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise LLMUnavailableError(f"Groq API unrecoverable status {e.status_code}: {e.message}") from e
        except Exception as e:
            last_exc = e
            msg = str(e).lower()
            if "429" in msg or "rate" in msg:
                logger.warning(f"Groq rate limit detected on key {masked}. Rotating to next key...")
                continue
            raise

    raise LLMUnavailableError(
        f"Groq LLM service unavailable after {total_attempts} attempts across {total_keys} pool keys: {last_exc}"
    ) from last_exc


def _execute_with_retry(call_fn, max_attempts: int = 3):
    """
    Executes a callable with exponential backoff on 429 rate limits and 5xx transient server errors.
    Max 3 attempts, then raises typed LLMUnavailableError.
    """
    last_exc = None
    for attempt in range(max_attempts):
        try:
            return call_fn()
        except (RateLimitError, APIConnectionError) as e:
            last_exc = e
            wait_time = (2 ** attempt) * 0.5
            logger.warning(f"Groq API transient error on attempt {attempt + 1}/{max_attempts}: {e}. Retrying in {wait_time}s...")
            time.sleep(wait_time)
        except APIStatusError as e:
            last_exc = e
            if e.status_code == 429 or e.status_code >= 500:
                wait_time = (2 ** attempt) * 0.5
                logger.warning(f"Groq API {e.status_code} on attempt {attempt + 1}/{max_attempts}: {e.message}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise LLMUnavailableError(f"Groq API unrecoverable status {e.status_code}: {e.message}") from e
        except Exception as e:
            last_exc = e
            msg = str(e).lower()
            if "429" in msg or "rate" in msg or "timeout" in msg or "500" in msg or "503" in msg:
                wait_time = (2 ** attempt) * 0.5
                logger.warning(f"Groq transient error on attempt {attempt + 1}/{max_attempts}: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise

    raise LLMUnavailableError(f"LLM service unavailable after {max_attempts} attempts: {last_exc}") from last_exc


def _clean_and_parse_json(text: str) -> Dict[str, Any]:
    """Helper to parse JSON from model output, stripping markdown code fences if present."""
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    return json.loads(cleaned)


def complete(
    prompt: str,
    response_format: Literal["json", "text"] = "text",
    max_tokens: Optional[int] = None
) -> Union[Dict[str, Any], str]:
    """
    Standard text completion interface using Groq LLM with round-robin key pool rotation.
    
    In JSON mode, validates that response is parseable JSON before returning.
    Retries once with a stricter formatting prompt on a parse failure, then raises LLMMalformedResponseError.
    Handles round-robin failover and exponential backoff on 429 / 5xx, raising LLMUnavailableError if exhausted.
    """
    # Check if running in mock/demo mode for local development and offline unit tests
    import os
    if os.environ.get("TESTING") == "true" or (
        not settings.groq_api_keys_pool and (
            not settings.GROQ_API_KEY or settings.GROQ_API_KEY.startswith("demo_") or settings.GROQ_API_KEY == "mock"
        )
    ):
        return _simulate_mock_response(prompt, response_format)

    model = settings.GROQ_TEXT_MODEL

    def _call(client: Groq, p: str):
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": p}],
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}
        return client.chat.completions.create(**kwargs)

    completion = _execute_groq_call(lambda c: _call(c, prompt))
    raw_content = completion.choices[0].message.content or ""

    if response_format == "text":
        return raw_content.strip()

    # JSON response mode
    try:
        return _clean_and_parse_json(raw_content)
    except json.JSONDecodeError as err:
        logger.warning(f"JSON parse error on first attempt: {err}. Retrying once with strict instructions...")
        strict_prompt = (
            f"{prompt}\n\n"
            "CRITICAL: Your previous response was not valid JSON. "
            "You MUST respond ONLY with a raw, valid JSON object. "
            "Do not include any explanation, prefix, suffix, or markdown fences."
        )
        try:
            retry_completion = _execute_groq_call(lambda c: _call(c, strict_prompt))
            retry_raw = retry_completion.choices[0].message.content or ""
            return _clean_and_parse_json(retry_raw)
        except Exception as retry_err:
            raise LLMMalformedResponseError(
                f"Failed to obtain valid JSON from LLM after retry. Raw response: {raw_content}"
            ) from retry_err


def complete_vision(prompt: str, image_bytes: bytes) -> Dict[str, Any]:
    """
    Vision completion interface using Groq Vision model with round-robin key pool rotation.
    Validates JSON output format with the same discipline as complete().
    """
    import os
    if os.environ.get("TESTING") == "true" or (
        not settings.groq_api_keys_pool and (
            not settings.GROQ_API_KEY or settings.GROQ_API_KEY.startswith("demo_") or settings.GROQ_API_KEY == "mock"
        )
    ):
        return {
            "asset_name": "Machinery Unit",
            "count": 2,
            "condition": "OPERATIONAL",
            "verification_confidence": 0.92,
            "dHash": "a1b2c3d4e5f67890"
        }

    model = settings.GROQ_VISION_MODEL
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    data_url = f"data:image/jpeg;base64,{base64_image}"

    def _call(client: Groq, p: str):
        return client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": p},
                        {"type": "image_url", "image_url": {"url": data_url}}
                    ]
                }
            ],
            response_format={"type": "json_object"}
        )

    completion = _execute_groq_call(lambda c: _call(c, prompt))
    raw_content = completion.choices[0].message.content or ""

    try:
        return _clean_and_parse_json(raw_content)
    except json.JSONDecodeError as err:
        logger.warning(f"Vision JSON parse error on first attempt: {err}. Retrying once...")
        strict_prompt = (
            f"{prompt}\n\n"
            "CRITICAL: Return ONLY a valid JSON object matching the requested schema."
        )
        try:
            retry_comp = _execute_groq_call(lambda c: _call(c, strict_prompt))
            retry_raw = retry_comp.choices[0].message.content or ""
            return _clean_and_parse_json(retry_raw)
        except Exception as retry_err:
            raise LLMMalformedResponseError(
                f"Failed to obtain valid JSON from vision LLM after retry. Raw: {raw_content}"
            ) from retry_err


def complete_audio_transcription(
    audio_bytes: bytes,
    filename: str = "chunk.wav",
    model: str = "whisper-large-v3-turbo",
    prompt: Optional[str] = None,
    response_format: str = "verbose_json",
    language: Optional[str] = None
) -> Any:
    """
    Transcribes audio bytes using Groq's Whisper model with the key pool's
    automatic round-robin rotation and instant failover across all pool keys on 429 rate limits.
    """
    import io
    import os

    if os.environ.get("TESTING") == "true" or (
        not settings.groq_api_keys_pool and (
            not settings.GROQ_API_KEY or settings.GROQ_API_KEY.startswith("demo_") or settings.GROQ_API_KEY == "mock"
        )
    ):
        return {
            "text": "Namaste, mera business badhiya chal raha hai.",
            "language": "hi",
            "segments": [
                {
                    "start": 0.0,
                    "end": 4.0,
                    "text": "Namaste, mera business badhiya chal raha hai.",
                    "avg_logprob": -0.15,
                    "no_speech_prob": 0.0
                }
            ]
        }

    def _call(client: Groq):
        buf = io.BytesIO(audio_bytes)
        kwargs: Dict[str, Any] = {
            "file": (filename, buf),
            "model": model,
            "response_format": response_format,
        }
        if prompt:
            # Groq Whisper enforces max 896 chars on prompt; clip safely to 880 chars
            kwargs["prompt"] = str(prompt)[:880]
        if language:
            kwargs["language"] = language
        return client.audio.transcriptions.create(**kwargs)

    return _execute_groq_call(_call)


def _simulate_mock_response(prompt: str, response_format: str) -> Union[Dict[str, Any], str]:
    """Simulates realistic structured responses when running in demo/offline test mode."""
    p_lower = prompt.lower()

    if response_format == "text":
        if "business_overview" in p_lower:
            return "Applicant operates a local commercial unit with stable business operations and steady trade cycles."
        elif "financial_overview" in p_lower:
            return "Monthly business cash flow aligns with stated turnover, showing sustainable operating margins."
        return "Assessment verified against physical inspection and verified customer statements."

    if "premises" in p_lower or "asset valuation" in p_lower or "category_matches_photo" in p_lower or "item detection" in p_lower or "valuation range" in p_lower:
        return {
            "category_matches_photo": True,
            "category_mismatch_reason": None,
            "premises_type": "retail_shop",
            "stock_level": "medium",
            "employee_count_visible": 1,
            "customer_activity_visible": "low",
            "overall_condition": "good",
            "items": [
                {
                    "name": "Display Glass Counter",
                    "count": 2,
                    "condition": "good",
                    "unit_value_min_inr": 8000.0,
                    "unit_value_max_inr": 12000.0,
                    "total_value_min_inr": 16000.0,
                    "total_value_max_inr": 24000.0
                }
            ],
            "estimated_total_value_min": 16000.0,
            "estimated_total_value_max": 24000.0,
            "summary": "Retail shop premises with glass display counter and inventory."
        }

    # JSON responses tailored to calling nodes
    if "diligence" in p_lower or "uptake" in p_lower:
        resolved_idx = []
        if "supplier" in p_lower or "credit" in p_lower or "margin" in p_lower:
            resolved_idx = [0]
        has_proactive = ("strike" in p_lower or "lease" in p_lower or "seasonal" in p_lower or "unprompted" in p_lower)
        return {
            "resolved_question_indices": resolved_idx,
            "proactive_bonus_awarded": has_proactive,
            "proactive_bonus_reason": "Officer proactively investigated supply chain or business continuity." if has_proactive else ""
        }

    if "contradiction" in p_lower or "consistency" in p_lower:
        contradictions = []
        if ("20l" in p_lower or "20,00,000" in p_lower or "20 lakh" in p_lower) and ("2,000" in p_lower or "2000" in p_lower):
            contradictions.append({
                "field_name": "monthly_turnover",
                "stated_value_1": "20,00,000 annual",
                "stated_value_2": "2,00,000 daily",
                "severity": "HIGH",
                "explanation": "Claimed 20L annual sales but earlier stated daily sales of Rs. 2,000 implies only ~6L annual."
            })
        elif "discrepancy" in p_lower or "contradict" in p_lower:
            contradictions.append({
                "field_name": "inventory_value",
                "stated_value_1": "10,00,000",
                "stated_value_2": "2,00,000",
                "severity": "MEDIUM",
                "explanation": "Declared inventory value conflicts with stock assessment."
            })
        return {"contradictions": contradictions}

    if "extract" in p_lower:
        fields = {}
        if "turnover" in p_lower or "2,50,000" in p_lower or "250000" in p_lower or "sales" in p_lower:
            fields["monthly_turnover"] = {
                "value": 250000.0,
                "status": "STATED",
                "confidence": 0.95,
                "reasoning": "Declared 2.5L monthly sales"
            }
        if "margin" in p_lower or "12%" in p_lower:
            fields["net_margin_pct"] = {
                "value": 12.0,
                "status": "STATED",
                "confidence": 0.90,
                "reasoning": "Declared 12% net profit margin"
            }
        if "daily" in p_lower and "10k" in p_lower:
            fields["monthly_turnover"] = {
                "value": 250000.0,
                "status": "INFERRED",
                "confidence": 0.85,
                "reasoning": "Rs. 10k daily * 25 days = Rs. 2.5L monthly"
            }
        if not fields:
            fields["general_info"] = {
                "value": "Captured during interview",
                "status": "STATED",
                "confidence": 0.85,
                "reasoning": "Extracted from dialogue"
            }
        return {"extracted_fields": fields}

    if "duplicate" in p_lower or "deduplicate" in p_lower or "semantically" in p_lower:
        return {
            "evaluations": [
                {"index": 0, "is_duplicate": False, "reason": "Unique follow-up question"},
                {"index": 1, "is_duplicate": False, "reason": "Unique follow-up question"},
                {"index": 2, "is_duplicate": False, "reason": "Unique follow-up question"}
            ]
        }

    if "follow" in p_lower or "question" in p_lower or "gap" in p_lower:
        return {
            "questions": [
                {
                    "question_text": "Aapke suppliers se raw material cash pe aata hai ya credit terms pe? Kitne din ka credit milta hai?",
                    "category": "SUPPLIER_TERMS",
                    "priority": 1,
                    "target_field": "supplier_payment_terms"
                }
            ]
        }

    return {"status": "success", "result": "verified"}


# ====================== LLM Protocol & Multi-Provider Clients ======================


class LLMClient(Protocol):
    def complete_json(
        self,
        system: str,
        user: str,
        retries: int = 5,
        image_bytes: Optional[bytes] = None,
        mime_type: str = "image/jpeg"
    ) -> dict: ...


# ====================== Google Gemini Multi-Key & Multi-Model Rotation ======================


class GeminiKeyPool:
    """
    Thread-safe Round-Robin Pool for Google Gemini API keys.
    Distributes requests across all configured API keys to multiply throughput
    and automatically rotates to the next key on 429 rate limit errors or 503 high demand.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._keys: list[str] = []
        self._index: int = 0
        self._refresh_keys()

    def _refresh_keys(self) -> None:
        self._keys = settings.gemini_api_keys_pool

    @property
    def total_keys(self) -> int:
        if not self._keys:
            self._refresh_keys()
        return len(self._keys)

    def get_next_key(self) -> str:
        with self._lock:
            if not self._keys:
                self._refresh_keys()
            if not self._keys:
                return (
                    getattr(settings, "GEMINI_API_KEY", "")
                    or getattr(settings, "gemini_api_key", "")
                    or "demo_key"
                )
            key = self._keys[self._index % len(self._keys)]
            self._index = (self._index + 1) % len(self._keys)
            return key

    @staticmethod
    def mask_key(key: str) -> str:
        if not key or len(key) < 10:
            return "..."
        return f"{key[:7]}...{key[-4:]}"


class GeminiModelPool:
    """
    Thread-safe Multi-Model Round-Robin Pool for Google Gemini Free Tier models.
    Rotates across multiple distinct free models per task to multiply available free tier RPM/TPM limits.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._indices: dict[str, int] = {"extraction": 0, "diarization": 0, "general": 0}

    def get_next_model(self, task: str = "extraction") -> str:
        with self._lock:
            if task == "diarization":
                models = getattr(
                    settings,
                    "GEMINI_DIARIZATION_MODELS",
                    ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3-flash-preview", "gemini-flash-lite-latest", "gemini-3.8-flash"]
                )
            elif task == "extraction":
                models = getattr(
                    settings,
                    "GEMINI_EXTRACTION_MODELS",
                    ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3-flash-preview", "gemini-flash-lite-latest", "gemini-3.8-flash", "gemini-3.1-flash-lite"]
                )
            else:
                models = getattr(settings, "GEMINI_EXTRACTION_MODELS", ["gemini-3.5-flash-lite", "gemini-3.5-flash"])

            if not models:
                return getattr(settings, "GEMINI_MODEL", "gemini-3.5-flash-lite")

            idx = self._indices.get(task, 0)
            chosen = models[idx % len(models)]
            self._indices[task] = (idx + 1) % len(models)
            return chosen.removeprefix("models/")


_gemini_key_pool = GeminiKeyPool()
_gemini_model_pool = GeminiModelPool()


def _execute_gemini_call(call_fn, task: str = "extraction", preferred_model: Optional[str] = None) -> Any:
    """
    Executes a Google Gemini API call with dual round-robin rotation across both API keys and models.
    On 429 rate limits, 503 high load, or 404 model errors, it immediately fails over to the next key
    and next available model in the free pool without blocking.
    """
    total_keys = max(1, _gemini_key_pool.total_keys)
    max_attempts = max(4, total_keys * 3)

    last_exc = None
    for attempt in range(max_attempts):
        key = _gemini_key_pool.get_next_key()
        masked = _gemini_key_pool.mask_key(key)
        model = preferred_model if (preferred_model and attempt == 0) else _gemini_model_pool.get_next_model(task=task)
        print(f">> [Gemini Rotation] Task='{task}' -> Model='{model}' | Key='{masked}' (attempt {attempt + 1})", flush=True)

        try:
            return call_fn(key, model)
        except (httpx.TimeoutException, httpx.NetworkError) as net_err:
            last_exc = net_err
            wait_time = min(2.0, (2 ** (attempt % 3)) * 0.4)
            logger.warning(f"Gemini API network/timeout on {model} (key {masked}): {net_err}. Trying next key/model in {wait_time}s...")
            time.sleep(wait_time)
        except Exception as e:
            last_exc = e
            msg = str(e).lower()
            status_code = getattr(e, "status_code", None)
            if hasattr(e, "response") and hasattr(e.response, "status_code"):
                status_code = e.response.status_code

            if status_code in (429, 503, 404) or "429" in msg or "quota" in msg or "rate limit" in msg or "503" in msg:
                logger.warning(
                    f"Gemini {status_code or 'error'} on {model} (key {masked}, attempt {attempt + 1}/{max_attempts}). "
                    f"Failing over to next Gemini key & model in round-robin pool..."
                )
                time.sleep(0.5 if status_code == 429 else 0.2)
                continue
            raise

    raise LLMUnavailableError(
        f"Gemini LLM service unavailable after {max_attempts} attempts across pool keys and models: {last_exc}"
    ) from last_exc


class GeminiClient:
    def __init__(self, api_key: str | None = None, model: str | None = None, task: str = "extraction"):
        self.api_key = api_key
        # If explicit model provided, pin to it; if None, enables dynamic per-call round-robin across task model pool
        self.model = model.removeprefix("models/") if model else None
        self.task = task

    def complete_json(
        self,
        system: str,
        user: str,
        retries: int = 5,
        image_bytes: Optional[bytes] = None,
        mime_type: str = "image/jpeg"
    ) -> dict:
        """Send a system + user prompt (and optional image) to Google Gemini and return parsed JSON."""
        import os
        if os.environ.get("TESTING") == "true" or not _gemini_key_pool.total_keys:
            return _simulate_mock_response(f"{system}\n{user}", "json")

        prompt_text = f"System Instructions:\n{system}\n\nUser Data:\n{user}"
        parts: list[dict] = [{"text": prompt_text}]
        if image_bytes:
            b64_img = base64.b64encode(image_bytes).decode("utf-8")
            parts.append({
                "inlineData": {
                    "mimeType": mime_type,
                    "data": b64_img
                }
            })

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json"
            }
        }

        def _call(key: str, model_name: str) -> dict:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
            headers = {"Content-Type": "application/json", "x-goog-api-key": key}
            r = httpx.post(url, json=payload, headers=headers, timeout=50.0)
            if r.status_code == 200:
                res_content = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                if res_content.startswith("```"):
                    res_content = res_content.strip("`").removeprefix("json").strip()
                return json.loads(res_content)
            r.raise_for_status()

        return _execute_gemini_call(_call, task=self.task, preferred_model=self.model)

    def complete_text(self, system: str, user: str, retries: int = 5) -> str:
        """Send a system + user prompt to Google Gemini and return response text."""
        import os
        if os.environ.get("TESTING") == "true" or not _gemini_key_pool.total_keys:
            return str(_simulate_mock_response(f"{system}\n{user}", "text"))

        prompt_text = f"System Instructions:\n{system}\n\nUser Data:\n{user}"
        payload = {
            "contents": [{"parts": [{"text": prompt_text}]}],
            "generationConfig": {"temperature": 0.2}
        }

        def _call(key: str, model_name: str) -> str:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
            headers = {"Content-Type": "application/json", "x-goog-api-key": key}
            r = httpx.post(url, json=payload, headers=headers, timeout=50.0)
            if r.status_code == 200:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            r.raise_for_status()

        return _execute_gemini_call(_call, task=self.task, preferred_model=self.model)


class GroqClient:
    """Groq client adapter implementing LLMClient using our round-robin pool."""
    def complete_json(
        self,
        system: str,
        user: str,
        retries: int = 5,
        image_bytes: Optional[bytes] = None,
        mime_type: str = "image/jpeg"
    ) -> dict:
        if image_bytes:
            combined = f"{system}\n\n{user}"
            return complete_vision(combined, image_bytes)
        combined = f"{system}\n\nUser Data:\n{user}"
        res = complete(combined, response_format="json")
        if isinstance(res, dict):
            return res
        return json.loads(str(res))


def get_llm(provider: Optional[str] = None, model: Optional[str] = None, task: str = "extraction") -> LLMClient:
    """
    Returns the active LLM client based on configuration or explicit provider selection.
    If `provider` is explicitly specified ("gemini" or "groq"), that provider is returned.
    If `model` contains 'gemini', automatically routes to GeminiClient.
    Otherwise, defaults to the provider configured in settings.LLM_PROVIDER.
    """
    if provider:
        active = provider.lower()
    elif model and "gemini" in model.lower():
        active = "gemini"
    else:
        active = getattr(settings, "LLM_PROVIDER", "groq").lower()

    if active == "gemini":
        return GeminiClient(model=model, task=task)
    return GroqClient()



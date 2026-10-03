"""App settings loaded from environment variables (DB URL, Redis URL, LLM API keys, JWT secret, etc.) via pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- infrastructure ---
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/msfincap"
    redis_url: str = "redis://localhost:6379/0"

    # --- LLM (Google Gemini) ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"


    # --- Agent 1: speech-to-text ---
    whisper_model: str = "small"               # use "small" to avoid out-of-memory errors on CPU
    whisper_device: str = "cpu"                # "cuda" on GPU
    whisper_compute_type: str = "int8"         # "float16" on GPU
    whisper_initial_prompt: str = ""           # cleared to prevent hallucination on short audio
    long_audio_sec: float = 3600               # split audio longer than this
    piece_target_sec: float = 600              # target length of each piece
    piece_overlap_sec: float = 3               # overlap between pieces
    low_conf_threshold: float = 0.6            # segments below this are flagged low_confidence


settings = Settings()

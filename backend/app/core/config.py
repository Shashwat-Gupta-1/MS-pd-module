from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "MSFincap PD Module"
    API_V1_STR: str = ""
    
    # Database & Redis
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/msfincap"
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Auth
    JWT_SECRET: str = "msfincap-phase1-super-secret-key"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day
    
    # LLM Settings (Defaulting to Groq per decision)
    LLM_PROVIDER: str = "groq"
    LLM_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    GROQ_API_KEYS: str = ""
    GROQ_MODEL_TEXT: str = "openai/gpt-oss-120b"
    GROQ_MODEL_VISION: str = "openai/gpt-oss-20b"
     
    # Gemini Settings
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    GEMINI_API_KEY: str = ""
    GEMINI_API_KEYS: str = ""
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    vision_model: str = "gemini-flash-latest"
    
    # Gemini Multi-Model Free Rotation Pools (Independent Quota per Model)
    GEMINI_EXTRACTION_MODELS: list[str] = [
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash",
        "gemini-flash-lite-latest",
        "gemini-flash-latest",
        "gemini-3-flash-preview",
        "gemini-3.8-flash"
    ]
    GEMINI_DIARIZATION_MODELS: list[str] = [
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash",
        "gemini-flash-lite-latest",
        "gemini-flash-latest",
        "gemini-3-flash-preview",
        "gemini-3.8-flash"
    ]
    
    # Whisper Settings (Agent 1: faster-whisper / Groq LPU)
    STT_ENGINE: str = "groq"
    GROQ_WHISPER_MODEL: str = "whisper-large-v3-turbo"
    whisper_model: str = "small"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    whisper_initial_prompt: str = (
        "MSFincap micro-enterprise loan Personal Discussion (PD) interview in Hindi, Hinglish, and English. "
        "Do NOT translate into English. Transcribe spoken Hindi in Devanagari script or Hinglish verbatim as spoken. "
        "Credit officer inquiries and borrower responses regarding business activity, daily and monthly sales, "
        "annual turnover, gross and net profit margin, operating expenses, existing loan obligations, and proposed EMI. "
        "Examples: 'नमस्ते, मेरी दुकान का टर्नओवर 2.5 लाख है और मार्जिन 12% है।' 'Daily sale lagbhag 8,000 se 10,000 rupaye hoti hai.' "
        "Key terms: ₹50,000, ₹1,00,000, 6 lakh, turnover, munafa, bikri, kharcha, EMI, byaaj, purana loan, "
        "dukaan, dairy, doodh, litre, pashu, gaay, bhains, kirana, customer, vendor, payment, cash, UPI, bank, Jaipur, Rajasthan. "
        "Transcribe spoken numbers as digits with currency where applicable."
    )
    long_audio_sec: float = 300.0
    piece_target_sec: float = 180.0
    piece_overlap_sec: float = 2.0
    low_conf_threshold: float = 0.6
    
    # Geocoding
    MAPS_API_KEY: str = ""
    
    # Storage paths
    UPLOAD_DIR: Path = Path("uploads")
    RECORDINGS_DIR: Path = Path("uploads/recordings")
    PHOTOS_DIR: Path = Path("uploads/photos")
    REPORTS_DIR: Path = Path("uploads/reports")
    CHROMA_PERSIST_DIRECTORY: Path = Path("chroma_db")
    MEDIA_BASE_URL: str = "/media"
    
    # Thresholds (Configurable per open TBD items)
    TRANSCRIPTION_CONFIDENCE_THRESHOLD: float = 0.6
    GPS_CLUSTER_TOLERANCE_METERS: float = 100.0
    gps_max_accuracy_m: float = 50.0
    default_distance_tolerance_m: float = 150.0
    photo_timestamp_drift_sec: int = 1800  # 30 minutes
    photo_hash_threshold: int = 10  # Max Hamming distance for pHash duplicate match
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def sqlalchemy_database_url(self) -> str:
        """Ensure postgresql:// URLs use psycopg2 driver if not explicitly specified."""
        if self.DATABASE_URL.startswith("postgresql://"):
            return self.DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
        return self.DATABASE_URL

    def init_upload_directories(self) -> None:
        """Ensure media upload directories exist on local disk."""
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
        self.PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
        self.REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def BASE_DIR(self) -> Path:
        return Path(__file__).resolve().parent.parent.parent

    @property
    def PHOTO_DIR(self) -> Path:
        return self.PHOTOS_DIR

    @property
    def GROQ_TEXT_MODEL(self) -> str:
        return self.GROQ_MODEL_TEXT

    @property
    def GROQ_VISION_MODEL(self) -> str:
        return self.GROQ_MODEL_VISION

    @property
    def groq_api_keys_pool(self) -> list[str]:
        """
        Gathers all unique valid Groq API keys from:
        1. settings.GROQ_API_KEY
        2. settings.GROQ_API_KEYS (comma separated keys or variable names)
        3. Environment variables matching gsk_key* or GROQ_KEY_*
        4. .env file directly (for extra variables not in Settings schema)
        """
        import os
        keys: list[str] = []

        def _is_valid_groq_key(val: str) -> bool:
            return bool(val and val.startswith("gsk_") and len(val) >= 30 and not val.endswith("_here"))

        # 1. Main key
        if self.GROQ_API_KEY:
            cleaned = self.GROQ_API_KEY.strip().strip('"\'')
            if _is_valid_groq_key(cleaned):
                keys.append(cleaned)

        # 2. Multi-key list or references from environment
        if self.GROQ_API_KEYS:
            for item in self.GROQ_API_KEYS.split(","):
                val = item.strip().strip('"\'')
                if not val:
                    continue
                if _is_valid_groq_key(val):
                    keys.append(val)
                elif val in os.environ:
                    env_val = os.environ[val].strip().strip('"\'')
                    if _is_valid_groq_key(env_val):
                        keys.append(env_val)

        # 3. Environment variables matching gsk_key* or GROQ_KEY_*
        for env_k, env_v in os.environ.items():
            if env_k.startswith("gsk_key") or env_k.startswith("GROQ_KEY_"):
                cleaned = env_v.strip().strip('"\'')
                if _is_valid_groq_key(cleaned):
                    keys.append(cleaned)

        # 4. If python-dotenv is present, check .env directly
        try:
            from dotenv import dotenv_values
            env_file = self.BASE_DIR / ".env"
            if env_file.exists():
                file_vals = dotenv_values(str(env_file))
                for f_k, f_v in file_vals.items():
                    if f_v and (f_k.startswith("gsk_key") or f_k.startswith("GROQ_KEY_")):
                        cleaned = f_v.strip().strip('"\'')
                        if _is_valid_groq_key(cleaned):
                            keys.append(cleaned)
                    elif f_k == "GROQ_API_KEYS" and f_v:
                        for token in f_v.split(","):
                            token_clean = token.strip().strip('"\'')
                            if token_clean in file_vals and file_vals[token_clean]:
                                ref_val = file_vals[token_clean].strip().strip('"\'')
                                if _is_valid_groq_key(ref_val):
                                    keys.append(ref_val)
        except Exception:
            pass

        # Deduplicate preserving order
        deduped: list[str] = []
        for k in keys:
            if k not in deduped:
                deduped.append(k)
        return deduped

    @property
    def gemini_api_keys_pool(self) -> list[str]:
        """
        Gathers all unique valid Gemini API keys from:
        1. settings.GEMINI_API_KEY / settings.gemini_api_key
        2. settings.GEMINI_API_KEYS (comma separated)
        3. Environment variables matching gemini_key* or GEMINI_KEY_*
        4. .env file directly
        """
        import os
        keys: list[str] = []

        def _is_valid_gemini_key(val: str) -> bool:
            return bool(val and val.startswith("AQ.") and len(val) >= 25 and not val.endswith("_here"))

        # 1. Main keys
        for k in [self.GEMINI_API_KEY, self.gemini_api_key]:
            if k:
                cleaned = k.strip().strip('"\'')
                if _is_valid_gemini_key(cleaned) and cleaned not in keys:
                    keys.append(cleaned)

        # 2. Multi-key list or references from environment
        if self.GEMINI_API_KEYS:
            for item in self.GEMINI_API_KEYS.split(","):
                val = item.strip().strip('"\'')
                if not val:
                    continue
                if _is_valid_gemini_key(val) and val not in keys:
                    keys.append(val)
                elif val in os.environ:
                    env_val = os.environ[val].strip().strip('"\'')
                    if _is_valid_gemini_key(env_val) and env_val not in keys:
                        keys.append(env_val)

        # 3. Environment variables matching gemini_key* or GEMINI_KEY_*
        for env_k, env_v in os.environ.items():
            if env_k.lower().startswith("gemini_key") or env_k.startswith("GEMINI_KEY_"):
                cleaned = env_v.strip().strip('"\'')
                if _is_valid_gemini_key(cleaned) and cleaned not in keys:
                    keys.append(cleaned)

        # 4. Direct .env parse to catch variables defined in .env
        try:
            from dotenv import dotenv_values
            env_file = self.BASE_DIR / ".env"
            if not env_file.exists():
                env_file = Path(".env")
            if env_file.exists():
                file_vals = dotenv_values(str(env_file))
                for f_k, f_v in file_vals.items():
                    if f_v and (f_k.lower().startswith("gemini_key") or f_k.startswith("GEMINI_KEY_")):
                        cleaned = f_v.strip().strip('"\'')
                        if _is_valid_gemini_key(cleaned) and cleaned not in keys:
                            keys.append(cleaned)
                    elif f_k in ("GEMINI_API_KEY", "gemini_api_key") and f_v:
                        cleaned = f_v.strip().strip('"\'')
                        if _is_valid_gemini_key(cleaned) and cleaned not in keys:
                            keys.append(cleaned)
                    elif f_k == "GEMINI_API_KEYS" and f_v:
                        for token in f_v.split(","):
                            token_clean = token.strip().strip('"\'')
                            if _is_valid_gemini_key(token_clean) and token_clean not in keys:
                                keys.append(token_clean)
        except Exception:
            pass

        return keys


settings = Settings()

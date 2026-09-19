from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    # Which AI provider to use: "gemini", "anthropic", or "auto" (Gemini if a
    # Gemini key is set, otherwise Anthropic).
    llm_provider: str = "auto"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    # Free keys allow ~5 requests/minute *per model*, so generation (four calls at once)
    # is spread across these extra models. Comma-separated; empty disables.
    gemini_fallback_models: str = "gemini-3.5-flash,gemini-3.1-flash-lite"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    # Optional: cap Gemini's hidden "thinking" tokens (0 = off on Flash models) for speed.
    gemini_thinking_budget: int | None = None
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"
    database_url: str = f"sqlite:///{(BASE_DIR / 'briefly.db').as_posix()}"
    storage_dir: Path = BASE_DIR / "app" / "storage"
    mock_teams_dir: Path = BASE_DIR / "app" / "mock_teams"
    mock_canvas_dir: Path = BASE_DIR / "app" / "mock_canvas"
    # Real Canvas instance; the mock is used unless BOTH are set (https only).
    canvas_base_url: str = ""
    canvas_token: str = ""
    max_source_chars: int = 12_000
    total_context_chars: int = 60_000
    # Chars of retrieved source excerpts given to the tutor per message.
    tutor_context_chars: int = 14_000
    max_upload_bytes: int = 10 * 1024 * 1024
    # Comma-separated list of allowed browser origins (add your Vercel URL here).
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def provider(self) -> str:
        choice = self.llm_provider.strip().lower()
        if choice in ("gemini", "anthropic"):
            return choice
        return "gemini" if self.gemini_api_key else "anthropic"

    @property
    def gemini_fallback_list(self) -> list[str]:
        return [m.strip() for m in self.gemini_fallback_models.split(",") if m.strip()]

    @property
    def model_name(self) -> str:
        return self.gemini_model if self.provider == "gemini" else self.anthropic_model

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()

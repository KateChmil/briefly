from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"
    database_url: str = f"sqlite:///{(BASE_DIR / 'briefly.db').as_posix()}"
    storage_dir: Path = BASE_DIR / "app" / "storage"
    mock_teams_dir: Path = BASE_DIR / "app" / "mock_teams"
    max_source_chars: int = 12_000
    total_context_chars: int = 60_000
    # Chars of retrieved source excerpts given to the tutor per message.
    tutor_context_chars: int = 14_000
    max_upload_bytes: int = 10 * 1024 * 1024
    # Comma-separated list of allowed browser origins (add your Vercel URL here).
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()

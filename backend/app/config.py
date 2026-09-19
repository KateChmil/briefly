from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"
    database_url: str = f"sqlite:///{(BASE_DIR / 'briefly.db').as_posix()}"
    storage_dir: Path = BASE_DIR / "app" / "storage"
    mock_teams_dir: Path = BASE_DIR / "app" / "mock_teams"
    max_source_chars: int = 12_000
    total_context_chars: int = 60_000


settings = Settings()

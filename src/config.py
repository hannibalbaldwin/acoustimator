from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://localhost/acoustimator"
    database_url_direct: str = "postgresql://localhost/acoustimator"
    anthropic_api_key: str = ""
    data_source_path: Path = Path("data/raw")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

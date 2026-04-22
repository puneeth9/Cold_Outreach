from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Stage 1
    database_url: str = "sqlite:///./outreach.db"

    # v1.5 — thread-based follow-up threshold
    follow_up_after_days_default: int = 5

    # Stage 2 — Gmail OAuth
    google_client_secret_file: str = "client_secret.json"
    google_credentials_file: str = "token.json"

    # Stage 2 — Pub/Sub (future)
    pubsub_subscription_name: str | None = None
    pubsub_push_token: str | None = None

    # Stage 3 — Claude
    anthropic_api_key: str | None = None


settings = Settings()

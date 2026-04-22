from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Stage 1
    database_url: str = "sqlite:///./outreach.db"

    # Stage 2 — Gmail OAuth
    google_client_secret_file: str = "client_secret.json"  # downloaded from GCP Console
    google_credentials_file: str = "token.json"            # written by `auth` command

    # Stage 2 — Pub/Sub
    pubsub_subscription_name: str | None = None
    pubsub_push_token: str | None = None

    # Stage 3 — Claude
    anthropic_api_key: str | None = None


settings = Settings()

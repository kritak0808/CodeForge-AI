from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ─────────────────────────────────────────────────────────────
    # App Settings
    # ─────────────────────────────────────────────────────────────
    ENV: str = "development"
    PROJECT_NAME: str = "CodeForge AI"
    API_VERSION: str = "v1"

    # ─────────────────────────────────────────────────────────────
    # Database
    # ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./codeforge_dev.db"

    # ─────────────────────────────────────────────────────────────
    # Redis
    # ─────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_DISABLED: bool = True

    # ─────────────────────────────────────────────────────────────
    # Kafka
    # ─────────────────────────────────────────────────────────────
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_DISABLED: bool = True

    # ─────────────────────────────────────────────────────────────
    # Security
    # ─────────────────────────────────────────────────────────────
    SECRET_KEY: str = "dev-super-secret-key-change-in-production-min-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ─────────────────────────────────────────────────────────────
    # CORS
    # ─────────────────────────────────────────────────────────────
    CORS_ORIGINS: str = (
        "http://localhost:3000,"
        "http://127.0.0.1:3000,"
        "https://code-forge-ai-ivory.vercel.app"
    )

    # Regex to allow ALL Vercel preview deployments
    CORS_ORIGIN_REGEX: str = r"https://.*\.vercel\.app"

    # ─────────────────────────────────────────────────────────────
    # Seed Admin
    # ─────────────────────────────────────────────────────────────
    SEED_ADMIN_USERNAME: str = "admin"
    SEED_ADMIN_PASSWORD: str = "admin123"
    SEED_ADMIN_EMAIL: str = "admin@codeforge.ai"

    # ─────────────────────────────────────────────────────────────
    # AI Providers
    # ─────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def get_cors_origins(self) -> List[str]:
        return [
            origin.strip()
            for origin in self.CORS_ORIGINS.split(",")
            if origin.strip()
        ]

    @property
    def is_sqlite(self) -> bool:
        return "sqlite" in self.DATABASE_URL.lower()

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() == "production"


settings = Settings()
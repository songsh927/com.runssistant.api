from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # App
    ENV: str = "local"  # local | prod
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://runcoach:runcoach@localhost:5432/runcoach"
    DATABASE_URL_TEST: str = "postgresql+asyncpg://runcoach:runcoach@localhost:5432/runcoach_test"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # Rate limiting
    RATE_LIMIT_DEFAULT: int = 60  # 분당 기본 요청 수
    RATE_LIMIT_COACH: int = 5  # 분당 /coach/recommend 최대 요청 수

    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 10080  # 7일

    # LLM provider
    LLM_PROVIDER: str = "ollama"

    # Ollama (local)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "gemma3:4b"

    # Bedrock (prod)
    BEDROCK_MODEL_ID: str = "amazon.nova-lite-v1:0"
    BEDROCK_REGION: str = "us-east-1"

    # OpenAI (optional)
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Weather
    OWM_API_KEY: str = ""


settings = Settings()

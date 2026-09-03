from app.config import settings
from app.llm.base import LLMProvider
from app.llm.bedrock import BedrockProvider
from app.llm.ollama import OllamaProvider
from app.llm.openai import OpenAIProvider


def create_llm_provider() -> LLMProvider:
    """LLM_PROVIDER 환경변수로 provider 결정."""
    match settings.LLM_PROVIDER:
        case "ollama":
            return OllamaProvider(
                base_url=settings.OLLAMA_BASE_URL,
                model=settings.OLLAMA_MODEL,
            )
        case "bedrock":
            return BedrockProvider(
                model_id=settings.BEDROCK_MODEL_ID,
                region=settings.BEDROCK_REGION,
            )
        case "openai":
            return OpenAIProvider(
                api_key=settings.OPENAI_API_KEY,
                model=settings.OPENAI_MODEL,
            )
        case _:
            raise ValueError(f"Unknown LLM provider: {settings.LLM_PROVIDER}")

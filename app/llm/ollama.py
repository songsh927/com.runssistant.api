import httpx

from app.llm.base import LLMProvider, LLMResponse


class OllamaProvider(LLMProvider):
    """로컬 Ollama 서버와 통신. JSON 출력을 강제하기 위해 format=json을 사용한다."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5:7b",
    ) -> None:
        self.base_url = base_url
        self.model = model

    async def invoke(
        self,
        system: str,
        user_message: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_message},
                    ],
                    "stream": False,
                    "format": "json",
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    },
                },
            )
            resp.raise_for_status()
            data = resp.json()

        return LLMResponse(
            content=data["message"]["content"],
            model=self.model,
            usage={
                "input_tokens": data.get("prompt_eval_count"),
                "output_tokens": data.get("eval_count"),
            },
        )

    def get_model_name(self) -> str:
        return f"ollama/{self.model}"

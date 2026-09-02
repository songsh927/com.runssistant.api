import asyncio

import boto3

from app.llm.base import LLMProvider, LLMResponse


class BedrockProvider(LLMProvider):
    """AWS Bedrock — Nova, Claude 등 모델 ID만 바꿔서 사용.

    NOTE: Converse API에는 JSON 강제 모드가 없다. system 프롬프트의 "반드시 JSON으로만
    응답하라" 지시와 app.llm.parsing.extract_json에 의존한다.
    """

    def __init__(
        self,
        model_id: str = "amazon.nova-lite-v1:0",
        region: str = "us-east-1",
    ) -> None:
        self.model_id = model_id
        self.client = boto3.client("bedrock-runtime", region_name=region)

    async def invoke(
        self,
        system: str,
        user_message: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        response = await asyncio.to_thread(
            self.client.converse,
            modelId=self.model_id,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": user_message}]}],
            inferenceConfig={"temperature": temperature, "maxTokens": max_tokens},
        )

        output_text = response["output"]["message"]["content"][0]["text"]
        usage = response.get("usage", {})

        return LLMResponse(
            content=output_text,
            model=self.model_id,
            usage={
                "input_tokens": usage.get("inputTokens"),
                "output_tokens": usage.get("outputTokens"),
            },
        )

    def get_model_name(self) -> str:
        return f"bedrock/{self.model_id}"

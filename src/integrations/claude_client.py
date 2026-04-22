import anthropic

from src.config import settings
from src.core.classifier import CLASSIFICATION_TOOL, ClassificationResult, parse_tool_response

MODEL = "claude-sonnet-4-6"


class ClaudeClient:
    def __init__(self) -> None:
        if not settings.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Add it to your .env file."
            )
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def classify(self, prompt: str) -> ClassificationResult:
        response = self._client.messages.create(
            model=MODEL,
            max_tokens=256,
            tools=[CLASSIFICATION_TOOL],
            tool_choice={"type": "tool", "name": "record_classification"},
            messages=[{"role": "user", "content": prompt}],
        )

        # tool_choice forces exactly one tool use block
        tool_block = next(
            (b for b in response.content if b.type == "tool_use"),
            None,
        )
        if not tool_block:
            raise RuntimeError("Claude did not return a tool use block")

        return parse_tool_response(tool_block.input)

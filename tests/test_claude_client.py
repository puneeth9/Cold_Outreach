import pytest
from unittest.mock import MagicMock, patch

from src.core.classifier import ClassificationResult
from src.models.reply import Classification


@pytest.fixture
def mock_settings(monkeypatch):
    monkeypatch.setattr("src.integrations.claude_client.settings", MagicMock(anthropic_api_key="test-key"))


def _make_tool_response(classification="interested", confidence=0.9, reasoning="Clear interest."):
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.input = {
        "classification": classification,
        "confidence": confidence,
        "reasoning": reasoning,
    }
    response = MagicMock()
    response.content = [tool_block]
    return response


def test_classify_returns_classification_result(mock_settings):
    with patch("src.integrations.claude_client.anthropic.Anthropic") as MockAnthropic:
        MockAnthropic.return_value.messages.create.return_value = _make_tool_response()
        from src.integrations.claude_client import ClaudeClient
        client = ClaudeClient()
        result = client.classify("some prompt")

    assert isinstance(result, ClassificationResult)
    assert result.classification == Classification.interested
    assert result.confidence == 0.9
    assert result.reasoning == "Clear interest."


def test_classify_raises_when_no_tool_block(mock_settings):
    with patch("src.integrations.claude_client.anthropic.Anthropic") as MockAnthropic:
        response = MagicMock()
        response.content = []
        MockAnthropic.return_value.messages.create.return_value = response
        from src.integrations.claude_client import ClaudeClient
        client = ClaudeClient()
        with pytest.raises(RuntimeError, match="tool use block"):
            client.classify("some prompt")


def test_classify_raises_without_api_key():
    with patch("src.integrations.claude_client.settings", MagicMock(anthropic_api_key=None)):
        from src.integrations.claude_client import ClaudeClient
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            ClaudeClient()

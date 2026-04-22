import pytest

from src.core.classifier import build_prompt, parse_tool_response, ClassificationResult
from src.models.reply import Classification


def test_build_prompt_includes_key_fields():
    prompt = build_prompt(
        outreach_subject="Engineering role at Acme",
        outreach_body="Hi Jane, I wanted to reach out about...",
        reply_body="Thanks, I'm interested! When can we chat?",
        recipient_name="Jane Smith",
        company="Acme Corp",
    )
    assert "Jane Smith" in prompt
    assert "Acme Corp" in prompt
    assert "Engineering role at Acme" in prompt
    assert "I'm interested" in prompt
    assert "reach out about" in prompt


def test_build_prompt_handles_no_company():
    prompt = build_prompt(
        outreach_subject="Subject",
        outreach_body="Body",
        reply_body="Reply",
        recipient_name="Bob",
        company=None,
    )
    assert "Company:" not in prompt
    assert "Bob" in prompt


def test_parse_tool_response_all_classifications():
    for value in ["interested", "not_interested", "needs_followup", "unclassified"]:
        result = parse_tool_response({
            "classification": value,
            "confidence": 0.9,
            "reasoning": "Test reason.",
        })
        assert result.classification == Classification(value)


def test_parse_tool_response_clamps_confidence():
    result = parse_tool_response({
        "classification": "interested",
        "confidence": 1.5,
        "reasoning": "Very confident.",
    })
    assert result.confidence == 1.0

    result = parse_tool_response({
        "classification": "interested",
        "confidence": -0.1,
        "reasoning": "Not confident.",
    })
    assert result.confidence == 0.0


def test_parse_tool_response_rejects_invalid_classification():
    with pytest.raises(ValueError, match="Invalid classification"):
        parse_tool_response({
            "classification": "maybe",
            "confidence": 0.5,
            "reasoning": "Unsure.",
        })


def test_parse_tool_response_rejects_empty_reasoning():
    with pytest.raises(ValueError, match="empty reasoning"):
        parse_tool_response({
            "classification": "interested",
            "confidence": 0.8,
            "reasoning": "",
        })


def test_parse_tool_response_returns_correct_types():
    result = parse_tool_response({
        "classification": "needs_followup",
        "confidence": 0.75,
        "reasoning": "They asked a clarifying question.",
    })
    assert isinstance(result, ClassificationResult)
    assert isinstance(result.confidence, float)
    assert isinstance(result.reasoning, str)

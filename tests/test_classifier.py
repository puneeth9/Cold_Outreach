from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.core.classifier import build_prompt, parse_tool_response, ClassificationResult
from src.models.message import Classification, Direction


SENT_AT = datetime(2026, 1, 10, tzinfo=timezone.utc)


def _make_message(direction, subject="Subject", body="Body text"):
    m = MagicMock()
    m.direction = direction
    m.subject = subject
    m.body = body
    m.sent_at = SENT_AT
    return m


# --- build_prompt ---

def test_build_prompt_includes_recipient_and_company():
    messages = [_make_message(Direction.outbound, body="Initial reach out.")]
    messages.append(_make_message(Direction.inbound, body="I'm interested!"))
    prompt = build_prompt(messages, recipient_name="Jane Smith", company="Acme Corp")
    assert "Jane Smith" in prompt
    assert "Acme Corp" in prompt


def test_build_prompt_omits_company_when_none():
    messages = [_make_message(Direction.outbound, body="Hi.")]
    messages.append(_make_message(Direction.inbound, body="Sure."))
    prompt = build_prompt(messages, recipient_name="Bob", company=None)
    assert "Company:" not in prompt
    assert "Bob" in prompt


def test_build_prompt_marks_last_message_as_classify_target():
    messages = [
        _make_message(Direction.outbound, body="First outbound."),
        _make_message(Direction.outbound, body="Follow-up."),
        _make_message(Direction.inbound, body="Here is my reply."),
        _make_message(Direction.inbound, body="Actually, let me elaborate."),
    ]
    prompt = build_prompt(messages, recipient_name="X", company=None)
    # Only the final message should carry the marker
    assert prompt.count("CLASSIFY THIS MESSAGE") == 1
    # The marker must appear near the last message body
    last_body_pos = prompt.rfind("Actually, let me elaborate.")
    marker_pos = prompt.rfind("CLASSIFY THIS MESSAGE")
    assert marker_pos < last_body_pos or marker_pos > prompt.find("Here is my reply.")


def test_build_prompt_includes_all_message_bodies():
    messages = [
        _make_message(Direction.outbound, body="Cold outreach body."),
        _make_message(Direction.inbound, body="Reply body here."),
    ]
    prompt = build_prompt(messages, recipient_name=None, company=None)
    assert "Cold outreach body." in prompt
    assert "Reply body here." in prompt


def test_build_prompt_shows_direction_labels():
    messages = [
        _make_message(Direction.outbound, body="Sent by me."),
        _make_message(Direction.inbound, body="Sent by them."),
    ]
    prompt = build_prompt(messages, recipient_name=None, company=None)
    assert "outbound" in prompt.lower()
    assert "inbound" in prompt.lower()


# --- parse_tool_response ---

def test_parse_tool_response_all_classifications():
    for value in ["interested", "not_interested", "needs_followup", "unclassified"]:
        result = parse_tool_response({
            "classification": value,
            "confidence": 0.9,
            "reasoning": "Test reason.",
        })
        assert result.classification == Classification(value)


def test_parse_tool_response_clamps_confidence_high():
    result = parse_tool_response({
        "classification": "interested",
        "confidence": 1.5,
        "reasoning": "Very confident.",
    })
    assert result.confidence == 1.0


def test_parse_tool_response_clamps_confidence_low():
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
        "classification": "not_interested",
        "confidence": 0.75,
        "reasoning": "Recipient explicitly declined.",
    })
    assert isinstance(result, ClassificationResult)
    assert isinstance(result.confidence, float)
    assert isinstance(result.reasoning, str)

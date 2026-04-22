from datetime import datetime, timezone

import pytest

from src.core.message_service import build_message, MessageData
from src.models.message import Direction


SENT_AT = datetime(2026, 1, 10, 9, 0, 0, tzinfo=timezone.utc)


def test_build_message_returns_message_data():
    data = build_message(
        outreach_id=1,
        direction=Direction.outbound,
        subject="Hello",
        body="Reaching out.",
        sent_at=SENT_AT,
    )
    assert isinstance(data, MessageData)
    assert data.outreach_id == 1
    assert data.direction == Direction.outbound
    assert data.subject == "Hello"
    assert data.sent_at == SENT_AT


def test_build_message_strips_subject():
    data = build_message(1, Direction.outbound, "  Hello  ", "Body", SENT_AT)
    assert data.subject == "Hello"


def test_build_message_rejects_empty_subject():
    with pytest.raises(ValueError, match="subject"):
        build_message(1, Direction.outbound, "   ", "Body", SENT_AT)


def test_build_message_rejects_empty_body():
    with pytest.raises(ValueError, match="body"):
        build_message(1, Direction.outbound, "Subject", "   ", SENT_AT)


def test_build_message_gmail_id_optional():
    data = build_message(1, Direction.inbound, "Re: Hello", "Thanks!", SENT_AT)
    assert data.gmail_message_id is None


def test_build_message_gmail_id_stored():
    data = build_message(1, Direction.inbound, "Re: Hello", "Thanks!", SENT_AT, gmail_message_id="abc123")
    assert data.gmail_message_id == "abc123"


def test_build_message_classification_defaults_none():
    data = build_message(1, Direction.inbound, "Re: Hi", "Sure!", SENT_AT)
    assert data.classification is None
    assert data.classification_confidence is None
    assert data.classification_reasoning is None

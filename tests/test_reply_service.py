from datetime import datetime, timezone

import pytest

from src.core.reply_service import build_reply
from src.models.reply import Classification

NOW = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)


def test_build_reply_sets_unclassified():
    reply = build_reply(
        gmail_message_id="msg_abc123",
        outreach_id=1,
        received_at=NOW,
        body="Thanks for reaching out!",
    )
    assert reply.classification == Classification.unclassified
    assert reply.classification_confidence is None
    assert reply.classification_reasoning is None
    assert reply.classified_at is None


def test_build_reply_preserves_fields():
    reply = build_reply(
        gmail_message_id="msg_xyz",
        outreach_id=42,
        received_at=NOW,
        body="Not interested.",
    )
    assert reply.gmail_message_id == "msg_xyz"
    assert reply.outreach_id == 42
    assert reply.received_at == NOW
    assert reply.body == "Not interested."


def test_build_reply_rejects_empty_message_id():
    with pytest.raises(ValueError, match="gmail_message_id"):
        build_reply(gmail_message_id="", outreach_id=1, received_at=NOW, body="Hi")


def test_build_reply_rejects_blank_body():
    with pytest.raises(ValueError, match="body"):
        build_reply(gmail_message_id="msg_1", outreach_id=1, received_at=NOW, body="   ")

from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.models.reply import Classification


@dataclass
class ReplyData:
    gmail_message_id: str
    outreach_id: int
    received_at: datetime
    body: str
    classification: Classification = Classification.unclassified
    classification_confidence: float | None = None
    classification_reasoning: str | None = None
    classified_at: datetime | None = None


def build_reply(
    gmail_message_id: str,
    outreach_id: int,
    received_at: datetime,
    body: str,
) -> ReplyData:
    if not gmail_message_id:
        raise ValueError("gmail_message_id cannot be empty")
    if not body.strip():
        raise ValueError("reply body cannot be empty")

    return ReplyData(
        gmail_message_id=gmail_message_id,
        outreach_id=outreach_id,
        received_at=received_at,
        body=body,
    )

from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.models.message import Classification, Direction


@dataclass
class MessageData:
    outreach_id: int
    direction: Direction
    subject: str
    body: str
    sent_at: datetime
    gmail_message_id: str | None = None
    classification: Classification | None = None
    classification_confidence: float | None = None
    classification_reasoning: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def build_message(
    outreach_id: int,
    direction: Direction,
    subject: str,
    body: str,
    sent_at: datetime,
    gmail_message_id: str | None = None,
) -> MessageData:
    if not subject.strip():
        raise ValueError("subject cannot be empty")
    if not body.strip():
        raise ValueError("body cannot be empty")

    return MessageData(
        outreach_id=outreach_id,
        direction=direction,
        subject=subject.strip(),
        body=body,
        sent_at=sent_at,
        gmail_message_id=gmail_message_id,
    )

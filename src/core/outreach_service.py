from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.models.outreach import OutreachStatus


@dataclass
class OutreachData:
    recipient_email: str
    recipient_name: str
    subject: str
    body: str
    company: str | None = None
    role_context: str | None = None
    sent_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: OutreachStatus = OutreachStatus.awaiting_reply


def build_outreach(
    recipient_email: str,
    recipient_name: str,
    subject: str,
    body: str,
    company: str | None = None,
    role_context: str | None = None,
    sent_at: datetime | None = None,
) -> OutreachData:
    parts = recipient_email.split("@")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"Invalid recipient email: {recipient_email!r}")
    if not recipient_name.strip():
        raise ValueError("recipient_name cannot be empty")
    if not subject.strip():
        raise ValueError("subject cannot be empty")
    if not body.strip():
        raise ValueError("body cannot be empty")

    return OutreachData(
        recipient_email=recipient_email.strip().lower(),
        recipient_name=recipient_name.strip(),
        subject=subject.strip(),
        body=body,
        company=company.strip() if company else None,
        role_context=role_context.strip() if role_context else None,
        sent_at=sent_at or datetime.now(timezone.utc),
    )

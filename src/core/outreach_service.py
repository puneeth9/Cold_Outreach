from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class OutreachData:
    recipient_email: str
    recipient_name: str | None = None
    company: str | None = None
    role: str | None = None
    follow_up_after_days: int | None = None
    archived: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def build_outreach(
    recipient_email: str,
    recipient_name: str | None = None,
    company: str | None = None,
    role: str | None = None,
    follow_up_after_days: int | None = None,
) -> OutreachData:
    parts = recipient_email.split("@")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"Invalid recipient email: {recipient_email!r}")

    return OutreachData(
        recipient_email=recipient_email.strip().lower(),
        recipient_name=recipient_name.strip() if recipient_name else None,
        company=company.strip() if company else None,
        role=role.strip() if role else None,
        follow_up_after_days=follow_up_after_days,
    )

from datetime import datetime, timezone

from src.models.message import Direction, Message
from src.models.outreach import Outreach

# Status values and what they mean:
#   archived        — user explicitly archived this outreach
#   draft           — outreach row exists but has no messages yet (shouldn't normally happen)
#   awaiting_reply  — last message is outbound and within the follow-up threshold
#   follow_up_needed — last message is outbound and threshold days have passed with no reply
#   interested      — last inbound message classified as interested
#   not_interested  — last inbound message classified as not_interested
#   needs_followup  — last inbound message classified as needs_followup (Claude label; distinct
#                     from follow_up_needed which is a thread-level timing status)
#   unclassified    — last inbound message has not been classified yet


def compute_status(
    outreach: Outreach,
    messages: list[Message],
    follow_up_after_days_default: int,
    now: datetime | None = None,
) -> str:
    if outreach.archived:
        return "archived"

    if not messages:
        return "draft"

    # Messages must be sorted by sent_at ascending before calling this function.
    last = messages[-1]

    if last.direction == Direction.inbound:
        # Classification label becomes the thread status for inbound-terminated threads.
        return last.classification.value if last.classification else "unclassified"

    # Last message is outbound — check whether we're past the follow-up threshold.
    threshold_days = outreach.follow_up_after_days or follow_up_after_days_default
    reference = now or datetime.now(timezone.utc)
    sent = last.sent_at
    if sent.tzinfo is None:
        sent = sent.replace(tzinfo=timezone.utc)
    if (reference - sent).days >= threshold_days:
        return "follow_up_needed"

    return "awaiting_reply"

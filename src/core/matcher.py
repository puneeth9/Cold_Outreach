from src.models.outreach import Outreach, OutreachStatus


def find_matching_outreach(from_email: str, outreaches: list[Outreach]) -> Outreach | None:
    """
    Match a reply's from_email against a list of outreach records.
    Returns the most recently sent awaiting_reply match, or None.
    """
    candidates = [
        o for o in outreaches
        if o.recipient_email == from_email.strip().lower()
        and o.status == OutreachStatus.awaiting_reply
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda o: o.sent_at)

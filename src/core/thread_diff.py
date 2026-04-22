def compute_new_message_ids(
    thread_message_ids: list[str],
    local_gmail_ids: set[str],
) -> list[str]:
    """Return thread message IDs not yet stored locally, preserving thread order."""
    return [mid for mid in thread_message_ids if mid not in local_gmail_ids]


def detect_direction(from_email: str, authenticated_email: str) -> str:
    """Return 'outbound' if the message was sent by the authenticated user, else 'inbound'."""
    return "outbound" if from_email.strip().lower() == authenticated_email.strip().lower() else "inbound"

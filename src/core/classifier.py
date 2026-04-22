from dataclasses import dataclass

from src.models.message import Classification, Direction, Message

CLASSIFICATION_TOOL = {
    "name": "record_classification",
    "description": "Record the classification of the final inbound message in a cold outreach thread.",
    "input_schema": {
        "type": "object",
        "properties": {
            "classification": {
                "type": "string",
                "enum": ["interested", "not_interested", "needs_followup", "unclassified"],
                "description": "How the recipient responded in their latest message.",
            },
            "confidence": {
                "type": "number",
                "description": "Confidence score between 0.0 and 1.0.",
            },
            "reasoning": {
                "type": "string",
                "description": "One sentence explaining the classification.",
            },
        },
        "required": ["classification", "confidence", "reasoning"],
    },
}


@dataclass
class ClassificationResult:
    classification: Classification
    confidence: float
    reasoning: str


def build_prompt(
    messages: list[Message],
    recipient_name: str | None,
    company: str | None,
) -> str:
    """Build a classification prompt from the thread up to and including the target message.

    The last message in `messages` is the inbound message being classified.
    All prior messages are context only.
    """
    header_parts = ["Cold outreach thread"]
    if recipient_name:
        header_parts.append(f"Recipient: {recipient_name}")
    if company:
        header_parts.append(f"Company: {company}")

    thread_lines = []
    for i, msg in enumerate(messages):
        label = "→ You (outbound)" if msg.direction == Direction.outbound else "← Recipient (inbound)"
        is_last = i == len(messages) - 1
        marker = " ← CLASSIFY THIS MESSAGE" if is_last else ""
        thread_lines.append(
            f"[{label}]{marker}\n"
            f"Subject: {msg.subject}\n"
            f"{msg.body.strip()}"
        )

    thread_block = "\n\n---\n\n".join(thread_lines)

    return f"""{" | ".join(header_parts)}

{thread_block}

---

Classify the FINAL message in the thread (marked above). The prior messages are context only.
Use the record_classification tool with one of:
- interested: recipient wants to continue the conversation or take action
- not_interested: recipient declined or is not open to further contact
- needs_followup: reply is ambiguous, asks a question, or requires a response before intent is clear
- unclassified: out-of-office, auto-reply, or no actionable signal
""".strip()


def parse_tool_response(tool_input: dict) -> ClassificationResult:
    classification_raw = tool_input.get("classification", "")
    try:
        classification = Classification(classification_raw)
    except ValueError:
        raise ValueError(
            f"Invalid classification value from Claude: {classification_raw!r}. "
            f"Expected one of: {[c.value for c in Classification]}"
        )

    confidence = float(tool_input.get("confidence", 0.0))
    confidence = max(0.0, min(1.0, confidence))

    reasoning = tool_input.get("reasoning", "").strip()
    if not reasoning:
        raise ValueError("Claude returned empty reasoning")

    return ClassificationResult(
        classification=classification,
        confidence=confidence,
        reasoning=reasoning,
    )

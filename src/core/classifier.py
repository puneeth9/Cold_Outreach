from dataclasses import dataclass

from src.models.reply import Classification

# Tool schema passed to Claude — enforces the response shape at the API layer
CLASSIFICATION_TOOL = {
    "name": "record_classification",
    "description": "Record the classification of a cold outreach reply.",
    "input_schema": {
        "type": "object",
        "properties": {
            "classification": {
                "type": "string",
                "enum": ["interested", "not_interested", "needs_followup", "unclassified"],
                "description": "How the recipient responded to the outreach.",
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
    outreach_subject: str,
    outreach_body: str,
    reply_body: str,
    recipient_name: str,
    company: str | None,
) -> str:
    company_line = f"Company: {company}" if company else ""
    return f"""You are evaluating a reply to a cold outreach email.

Recipient: {recipient_name}
{company_line}

--- Original outreach ---
Subject: {outreach_subject}
{outreach_body.strip()}

--- Their reply ---
{reply_body.strip()}

Classify the reply using the record_classification tool:
- interested: recipient wants to continue the conversation or take action
- not_interested: recipient declined or is not open to further contact
- needs_followup: reply is ambiguous, asks a question, or requires a response before intent is clear
- unclassified: reply is out-of-office, auto-reply, or contains no actionable signal
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
    confidence = max(0.0, min(1.0, confidence))  # clamp to [0, 1]

    reasoning = tool_input.get("reasoning", "").strip()
    if not reasoning:
        raise ValueError("Claude returned empty reasoning")

    return ClassificationResult(
        classification=classification,
        confidence=confidence,
        reasoning=reasoning,
    )

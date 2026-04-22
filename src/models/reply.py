import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class Classification(str, enum.Enum):
    interested = "interested"
    not_interested = "not_interested"
    needs_followup = "needs_followup"
    unclassified = "unclassified"


class Reply(Base):
    __tablename__ = "replies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    outreach_id: Mapped[int] = mapped_column(Integer, ForeignKey("outreach.id"), nullable=False)
    gmail_message_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    classification: Mapped[Classification] = mapped_column(
        Enum(Classification, native_enum=False),
        nullable=False,
        default=Classification.unclassified,
    )
    classification_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    classification_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    classified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    outreach: Mapped["Outreach"] = relationship("Outreach", back_populates="replies")  # noqa: F821

    __table_args__ = (Index("ix_replies_gmail_message_id", "gmail_message_id"),)

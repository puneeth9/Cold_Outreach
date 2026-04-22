from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class Outreach(Base):
    __tablename__ = "outreach"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipient_email: Mapped[str] = mapped_column(String, nullable=False)
    recipient_name: Mapped[str | None] = mapped_column(String, nullable=True)
    company: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Populated on first sync by searching Gmail sent mail for this outreach
    gmail_thread_id: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)
    # Per-outreach override; falls back to FOLLOW_UP_AFTER_DAYS_DEFAULT from settings
    follow_up_after_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Archived is the only stored status component; all other status is derived
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    messages: Mapped[list["Message"]] = relationship(  # noqa: F821
        "Message", back_populates="outreach", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_outreach_recipient_email", "recipient_email"),)

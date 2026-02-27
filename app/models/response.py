"""
Master responses to orders.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Response(Base):
    """Response entity with response timestamp."""

    __tablename__ = "responses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"))
    # Stores master Telegram ID (not users.id).
    master_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.telegram_id"))
    response_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

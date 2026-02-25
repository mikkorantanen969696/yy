"""
Order photo model for before/after pictures.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class OrderPhoto(Base):
    """Photo metadata stored in DB (file_id from Telegram)."""

    __tablename__ = "order_photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"))
    file_id: Mapped[str] = mapped_column(String(256))
    type: Mapped[str] = mapped_column(String(16))  # before/after
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

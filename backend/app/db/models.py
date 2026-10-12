from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class WatchItem(Base):
    __tablename__ = "watchlist"

    address: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    address: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    collateral_usd: Mapped[float] = mapped_column(Float)
    debt_usd: Mapped[float] = mapped_column(Float)
    portfolio_health_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    worst_health_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    alert_count: Mapped[int] = mapped_column(Integer)
    note: Mapped[str] = mapped_column(Text, default="")

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import DateTime, Float, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    pass


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)  # BUY/SELL
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    note: Mapped[str] = mapped_column(String(256), nullable=False, default="")


@dataclass(frozen=True)
class SqliteTradeLogger:
    db_path: Path = Path("trades.sqlite")

    def _engine(self):
        return create_engine(f"sqlite:///{self.db_path}")

    def init_db(self) -> None:
        engine = self._engine()
        Base.metadata.create_all(engine)

    def log_trade(
        self,
        *,
        symbol: str,
        side: str,
        qty: float,
        price: float,
        ts: datetime | None = None,
        note: str = "",
    ) -> None:
        engine = self._engine()
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            session.add(
                Trade(
                    ts=ts or datetime.utcnow(),
                    symbol=symbol,
                    side=side,
                    qty=qty,
                    price=price,
                    note=note,
                )
            )
            session.commit()

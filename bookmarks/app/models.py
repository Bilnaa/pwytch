from datetime import datetime

from sqlalchemy import UniqueConstraint, func, DateTime, Enum
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

from app.schemas import TargetType


class Base(DeclarativeBase):
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower()


class Bookmark(Base):
    __table_args__ = (
        UniqueConstraint("user_id", "target_type", "target_id", name="uq_bookmark_user_target"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int]
    target_type: Mapped[TargetType] = mapped_column(
        Enum(TargetType, values_callable=lambda e: [m.value for m in e]),
    )
    target_id: Mapped[int]
    label: Mapped[str]
    note: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
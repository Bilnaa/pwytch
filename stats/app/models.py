from sqlalchemy import BigInteger, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


class Base(DeclarativeBase):
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower()


class Counter(Base):
    __table_args__ = (
        UniqueConstraint("counter_type", "key",  name="uq_counter_countertype_key"),
    )
    
    id: Mapped[int] = mapped_column(primary_key=True)
    counter_type: Mapped[str]
    key: Mapped[str]
    value: Mapped[int] = mapped_column(BigInteger, server_default="0") 
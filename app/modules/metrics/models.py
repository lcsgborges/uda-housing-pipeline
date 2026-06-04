from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Metric(Base):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        index=True,
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
    )
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    metric_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    period_year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    period_quarter: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    company = relationship("Company", back_populates="metrics")
    document = relationship("Document", back_populates="metrics")
    lineage = relationship("DataLineage", back_populates="metric", cascade="all, delete-orphan")

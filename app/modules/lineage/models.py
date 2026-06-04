from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DataLineage(Base):
    __tablename__ = "data_lineage"

    id: Mapped[int] = mapped_column(primary_key=True)
    metric_id: Mapped[int] = mapped_column(ForeignKey("metrics.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
    )
    original_url: Mapped[str] = mapped_column(String(700), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_model: Mapped[str] = mapped_column(String(120), nullable=False)
    extraction_prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    extracted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    metric = relationship("Metric", back_populates="lineage")

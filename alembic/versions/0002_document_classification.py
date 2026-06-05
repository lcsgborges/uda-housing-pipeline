"""document classification metadata

Revision ID: 0002_document_classification
Revises: 0001_initial
Create Date: 2026-06-04
"""

import sqlalchemy as sa

from alembic import op

revision = "0002_document_classification"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Adiciona metadados e status de classificação em documentos."""
    for status in (
        "classifying",
        "classified_useful",
        "ignored_not_relevant",
        "needs_ocr",
    ):
        op.execute(f"ALTER TYPE documentstatus ADD VALUE IF NOT EXISTS '{status}'")

    op.add_column("documents", sa.Column("classification_is_useful", sa.Boolean(), nullable=True))
    op.add_column("documents", sa.Column("classification_confidence", sa.Float(), nullable=True))
    op.add_column("documents", sa.Column("classification_reason", sa.Text(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("classification_model", sa.String(length=120), nullable=True),
    )
    op.add_column("documents", sa.Column("detected_domains", sa.JSON(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("extraction_strategy", sa.String(length=40), nullable=True),
    )
    op.add_column("documents", sa.Column("classified_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Remove os campos de classificação adicionados aos documentos."""
    op.drop_column("documents", "classified_at")
    op.drop_column("documents", "extraction_strategy")
    op.drop_column("documents", "detected_domains")
    op.drop_column("documents", "classification_model")
    op.drop_column("documents", "classification_reason")
    op.drop_column("documents", "classification_confidence")
    op.drop_column("documents", "classification_is_useful")

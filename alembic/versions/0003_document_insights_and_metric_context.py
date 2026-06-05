"""document insights and metric context

Revision ID: 0003_document_insights_and_metric_context
Revises: 0002_document_classification
Create Date: 2026-06-04
"""

import sqlalchemy as sa
from alembic import op


revision = "0003_document_insights_and_metric_context"
down_revision = "0002_document_classification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("metrics", sa.Column("period_label", sa.String(length=80), nullable=True))
    op.add_column("metrics", sa.Column("raw_label", sa.String(length=200), nullable=True))
    op.add_column("metrics", sa.Column("dimension", sa.String(length=200), nullable=True))

    op.create_table(
        "document_insights",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("insight_type", sa.String(length=60), nullable=False),
        sa.Column("topic", sa.String(length=120), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("value_text", sa.String(length=300), nullable=True),
        sa.Column("period_year", sa.Integer(), nullable=True),
        sa.Column("period_quarter", sa.Integer(), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_excerpt", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
    )
    op.create_index("ix_document_insights_company_id", "document_insights", ["company_id"])
    op.create_index("ix_document_insights_document_id", "document_insights", ["document_id"])
    op.create_index("ix_document_insights_insight_type", "document_insights", ["insight_type"])
    op.create_index("ix_document_insights_topic", "document_insights", ["topic"])
    op.create_index("ix_document_insights_period_year", "document_insights", ["period_year"])
    op.create_index(
        "ix_document_insights_period_quarter",
        "document_insights",
        ["period_quarter"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_insights_period_quarter", table_name="document_insights")
    op.drop_index("ix_document_insights_period_year", table_name="document_insights")
    op.drop_index("ix_document_insights_topic", table_name="document_insights")
    op.drop_index("ix_document_insights_insight_type", table_name="document_insights")
    op.drop_index("ix_document_insights_document_id", table_name="document_insights")
    op.drop_index("ix_document_insights_company_id", table_name="document_insights")
    op.drop_table("document_insights")

    op.drop_column("metrics", "dimension")
    op.drop_column("metrics", "raw_label")
    op.drop_column("metrics", "period_label")

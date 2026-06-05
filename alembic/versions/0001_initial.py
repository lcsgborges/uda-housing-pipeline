"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-27
"""

import sqlalchemy as sa

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Cria o schema inicial de empresas, documentos, métricas e linhagem."""
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column("ri_url", sa.String(length=500), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("ticker"),
    )
    op.create_index("ix_companies_name", "companies", ["name"])
    op.create_index("ix_companies_ticker", "companies", ["ticker"])

    status_enum = sa.Enum(
        "discovered",
        "downloaded",
        "processing",
        "processed",
        "failed",
        "ignored_duplicate",
        name="documentstatus",
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=300), nullable=True),
        sa.Column("original_url", sa.String(length=700), nullable=False),
        sa.Column("local_path", sa.String(length=700), nullable=True),
        sa.Column("file_hash", sa.String(length=64), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("quarter", sa.Integer(), nullable=True),
        sa.Column("document_type", sa.String(length=80), nullable=True),
        sa.Column("status", status_enum, nullable=False),
        sa.Column("collected_at", sa.DateTime(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_documents_company_id", "documents", ["company_id"])
    op.create_index("ix_documents_file_hash", "documents", ["file_hash"])

    op.create_table(
        "metrics",
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
        sa.Column("metric_name", sa.String(length=100), nullable=False),
        sa.Column("metric_category", sa.String(length=100), nullable=True),
        sa.Column("period_year", sa.Integer(), nullable=True),
        sa.Column("period_quarter", sa.Integer(), nullable=True),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=30), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_excerpt", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
    )
    op.create_index("ix_metrics_company_id", "metrics", ["company_id"])
    op.create_index("ix_metrics_document_id", "metrics", ["document_id"])
    op.create_index("ix_metrics_metric_name", "metrics", ["metric_name"])
    op.create_index("ix_metrics_period_year", "metrics", ["period_year"])
    op.create_index("ix_metrics_period_quarter", "metrics", ["period_quarter"])

    op.create_table(
        "data_lineage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "metric_id",
            sa.Integer(),
            sa.ForeignKey("metrics.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("original_url", sa.String(length=700), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_excerpt", sa.Text(), nullable=True),
        sa.Column("extraction_model", sa.String(length=120), nullable=False),
        sa.Column("extraction_prompt_version", sa.String(length=40), nullable=False),
        sa.Column("extracted_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_data_lineage_metric_id", "data_lineage", ["metric_id"])
    op.create_index("ix_data_lineage_document_id", "data_lineage", ["document_id"])


def downgrade() -> None:
    """Remove o schema inicial na ordem inversa de dependências."""
    op.drop_index("ix_data_lineage_document_id", table_name="data_lineage")
    op.drop_index("ix_data_lineage_metric_id", table_name="data_lineage")
    op.drop_table("data_lineage")

    op.drop_index("ix_metrics_period_quarter", table_name="metrics")
    op.drop_index("ix_metrics_period_year", table_name="metrics")
    op.drop_index("ix_metrics_metric_name", table_name="metrics")
    op.drop_index("ix_metrics_document_id", table_name="metrics")
    op.drop_index("ix_metrics_company_id", table_name="metrics")
    op.drop_table("metrics")

    op.drop_index("ix_documents_file_hash", table_name="documents")
    op.drop_index("ix_documents_company_id", table_name="documents")
    op.drop_table("documents")

    op.drop_index("ix_companies_ticker", table_name="companies")
    op.drop_index("ix_companies_name", table_name="companies")
    op.drop_table("companies")

    status_enum = sa.Enum(name="documentstatus")
    status_enum.drop(op.get_bind(), checkfirst=True)

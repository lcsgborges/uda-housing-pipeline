"""document insights and metric context

Revision ID: 0003_document_insights
Revises: 0002_document_classification
Create Date: 2026-06-04
"""

import sqlalchemy as sa

from alembic import op

revision = "0003_document_insights"
down_revision = "0002_document_classification"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return table_name in _inspector().get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return column_name in {column["name"] for column in _inspector().get_columns(table_name)}


def _index_exists(table_name: str, index_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return index_name in {index["name"] for index in _inspector().get_indexes(table_name)}


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if not _column_exists(table_name, column.name):
        op.add_column(table_name, column)


def _drop_column_if_exists(table_name: str, column_name: str) -> None:
    if _column_exists(table_name, column_name):
        op.drop_column(table_name, column_name)


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str]) -> None:
    if not _index_exists(table_name, index_name):
        op.create_index(index_name, table_name, columns)


def _drop_index_if_exists(index_name: str, table_name: str) -> None:
    if _index_exists(table_name, index_name):
        op.drop_index(index_name, table_name=table_name)


def upgrade() -> None:
    _add_column_if_missing(
        "metrics",
        sa.Column("period_label", sa.String(length=80), nullable=True),
    )
    _add_column_if_missing(
        "metrics",
        sa.Column("raw_label", sa.String(length=200), nullable=True),
    )
    _add_column_if_missing(
        "metrics",
        sa.Column("dimension", sa.String(length=200), nullable=True),
    )

    if not _table_exists("document_insights"):
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

    _create_index_if_missing(
        "ix_document_insights_company_id",
        "document_insights",
        ["company_id"],
    )
    _create_index_if_missing(
        "ix_document_insights_document_id",
        "document_insights",
        ["document_id"],
    )
    _create_index_if_missing(
        "ix_document_insights_insight_type",
        "document_insights",
        ["insight_type"],
    )
    _create_index_if_missing("ix_document_insights_topic", "document_insights", ["topic"])
    _create_index_if_missing(
        "ix_document_insights_period_year",
        "document_insights",
        ["period_year"],
    )
    _create_index_if_missing(
        "ix_document_insights_period_quarter",
        "document_insights",
        ["period_quarter"],
    )


def downgrade() -> None:
    _drop_index_if_exists("ix_document_insights_period_quarter", "document_insights")
    _drop_index_if_exists("ix_document_insights_period_year", "document_insights")
    _drop_index_if_exists("ix_document_insights_topic", "document_insights")
    _drop_index_if_exists("ix_document_insights_insight_type", "document_insights")
    _drop_index_if_exists("ix_document_insights_document_id", "document_insights")
    _drop_index_if_exists("ix_document_insights_company_id", "document_insights")
    if _table_exists("document_insights"):
        op.drop_table("document_insights")

    _drop_column_if_exists("metrics", "dimension")
    _drop_column_if_exists("metrics", "raw_label")
    _drop_column_if_exists("metrics", "period_label")

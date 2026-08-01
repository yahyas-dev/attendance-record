"""Create initial attendance schema

Revision ID: 0001_create_initial_schema
Revises: 
Create Date: 2026-08-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_create_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "employee",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
    )

    attendance_status = postgresql.ENUM("Present", "Sick", "Leave", "Absent", name="attendance_status")
    attendance_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "attendance",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employee.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_name", sa.String(length=50), nullable=False),
        sa.Column("attendance_date", sa.Date(), nullable=False),
        sa.Column("check_in", sa.Time(), nullable=True),
        sa.Column("check_out", sa.Time(), nullable=True),
        sa.Column("status", postgresql.ENUM("Present", "Sick", "Leave", "Absent", name="attendance_status"), nullable=False),
        sa.Column("notes", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint("check_out IS NULL OR check_out >= check_in", name="chk_check_out_after_check_in"),
        sa.CheckConstraint("status != 'Present' OR check_in IS NOT NULL", name="chk_present_requires_check_in"),
    )

    op.create_unique_index(
        "unique_active_employee_daily_attendance",
        "attendance",
        ["employee_id", "attendance_date"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade():
    op.drop_index("unique_active_employee_daily_attendance", table_name="attendance")
    op.drop_table("attendance")
    op.drop_table("employee")
    attendance_status = postgresql.ENUM("Present", "Sick", "Leave", "Absent", name="attendance_status")
    attendance_status.drop(op.get_bind(), checkfirst=True)

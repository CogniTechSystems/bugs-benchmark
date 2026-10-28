"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-26 21:39:54.035800
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bug_hunts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column(
            "difficulty",
            sa.Enum("easy", "medium", "hard", name="difficulty", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("language", sa.String(length=50), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("bug_count", sa.Integer(), nullable=False),
        sa.Column("max_points", sa.Integer(), nullable=False),
        sa.Column("time_budget_seconds", sa.Integer(), nullable=False),
        sa.Column("is_available", sa.Boolean(), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "language_models",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("repo_id", sa.String(length=200), nullable=False),
        sa.Column("revision", sa.String(length=100), nullable=False),
        sa.Column("allow_patterns", sa.JSON(), nullable=True),
        sa.Column("local_path", sa.String(length=1000), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "downloading",
                "ready",
                "failed",
                name="downloadstatus",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("total_bytes", sa.BigInteger(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repo_id"),
    )
    op.create_table(
        "runtimes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("managed", "external", name="runtimekind", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("command_template", sa.Text(), nullable=True),
        sa.Column("base_url", sa.String(length=500), nullable=True),
        sa.Column("health_path", sa.String(length=200), nullable=False),
        sa.Column("startup_timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "deployments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("model_id", sa.Integer(), nullable=False),
        sa.Column("runtime_id", sa.Integer(), nullable=False),
        sa.Column("model_file", sa.String(length=500), nullable=True),
        sa.Column("served_model_name", sa.String(length=200), nullable=True),
        sa.Column("launch_args", sa.Text(), nullable=False),
        sa.Column("temperature", sa.Double(), nullable=False),
        sa.Column("top_p", sa.Double(), nullable=False),
        sa.Column("max_tokens", sa.Integer(), nullable=False),
        sa.Column("request_timeout_seconds", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "stopped",
                "starting",
                "running",
                "failed",
                name="deploymentstatus",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("port", sa.Integer(), nullable=True),
        sa.Column("pid", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["model_id"], ["language_models.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["runtime_id"], ["runtimes.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("deployment_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("idle", "running", "error", name="sessionstatus", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["deployment_id"], ["deployments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "deployment_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("deployment_id", sa.Integer(), nullable=False),
        sa.Column("line", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["deployment_id"], ["deployments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("deployment_logs", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_deployment_logs_deployment_id"), ["deployment_id"], unique=False
        )

    op.create_table(
        "bug_hunt_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bug_hunt_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("deployment_id", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.Integer(), nullable=False),
        sa.Column("runtime_id", sa.Integer(), nullable=False),
        sa.Column("settings_snapshot", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "scoring",
                "completed",
                "failed",
                "cancelled",
                name="jobstatus",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Double(), nullable=True),
        sa.Column("llm_calls", sa.Integer(), nullable=False),
        sa.Column("tool_calls", sa.Integer(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("agent_summary", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["bug_hunt_id"], ["bug_hunts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["deployment_id"], ["deployments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["model_id"], ["language_models.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["runtime_id"], ["runtimes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("bug_hunt_jobs", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_bug_hunt_jobs_model_id"), ["model_id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_bug_hunt_jobs_session_id"), ["session_id"], unique=False
        )

    op.create_table(
        "bug_findings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("line", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("original", sa.Text(), nullable=False),
        sa.Column("replacement", sa.Text(), nullable=False),
        sa.Column(
            "outcome",
            sa.Enum(
                "matched",
                "superseded",
                "false_positive",
                name="findingoutcome",
                native_enum=False,
                length=20,
            ),
            nullable=True,
        ),
        sa.Column("matched_bug_key", sa.String(length=100), nullable=True),
        sa.Column(
            "fix_status",
            sa.Enum(
                "verified",
                "failed",
                "not_applicable",
                name="fixstatus",
                native_enum=False,
                length=20,
            ),
            nullable=True,
        ),
        sa.Column("fix_details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["bug_hunt_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("bug_findings", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_bug_findings_job_id"), ["job_id"], unique=False)

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column(
            "role",
            sa.Enum("user", "assistant", "tool", name="messagerole", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("tool_calls", sa.JSON(), nullable=True),
        sa.Column("tool_call_id", sa.String(length=200), nullable=True),
        sa.Column("tool_name", sa.String(length=100), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["bug_hunt_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("chat_messages", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_chat_messages_job_id"), ["job_id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_chat_messages_session_id"), ["session_id"], unique=False
        )

    op.create_table(
        "job_scores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("bugs_total", sa.Integer(), nullable=False),
        sa.Column("bugs_found", sa.Integer(), nullable=False),
        sa.Column("fixes_verified", sa.Integer(), nullable=False),
        sa.Column("false_positives", sa.Integer(), nullable=False),
        sa.Column("points_earned", sa.Double(), nullable=False),
        sa.Column("points_possible", sa.Double(), nullable=False),
        sa.Column("precision", sa.Double(), nullable=False),
        sa.Column("recall", sa.Double(), nullable=False),
        sa.Column("accuracy_score", sa.Double(), nullable=False),
        sa.Column("time_factor", sa.Double(), nullable=False),
        sa.Column("final_score", sa.Double(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["bug_hunt_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id"),
    )
    op.create_table(
        "job_bug_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("bug_key", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("found", sa.Boolean(), nullable=False),
        sa.Column("fix_verified", sa.Boolean(), nullable=False),
        sa.Column("finding_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["finding_id"], ["bug_findings.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["job_id"], ["bug_hunt_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "bug_key"),
    )


def downgrade() -> None:
    op.drop_table("job_bug_results")
    op.drop_table("job_scores")
    with op.batch_alter_table("chat_messages", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_chat_messages_session_id"))
        batch_op.drop_index(batch_op.f("ix_chat_messages_job_id"))

    op.drop_table("chat_messages")
    with op.batch_alter_table("bug_findings", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_bug_findings_job_id"))

    op.drop_table("bug_findings")
    with op.batch_alter_table("bug_hunt_jobs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_bug_hunt_jobs_session_id"))
        batch_op.drop_index(batch_op.f("ix_bug_hunt_jobs_model_id"))

    op.drop_table("bug_hunt_jobs")
    with op.batch_alter_table("deployment_logs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_deployment_logs_deployment_id"))

    op.drop_table("deployment_logs")
    op.drop_table("chat_sessions")
    op.drop_table("deployments")
    op.drop_table("runtimes")
    op.drop_table("language_models")
    op.drop_table("bug_hunts")

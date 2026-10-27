"""Начальная схема по 120 — Data Model.

Revision ID: 0001
Revises:
Create Date: 2026-10-27 21:50:17.849641
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "attachment",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("owner_kind", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("checksum", sa.Text(), nullable=False),
        sa.Column("uploaded_by", sa.Text(), nullable=False),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "owner_kind IN ('CASE', 'STEP', 'RUN_RESULT', 'DEFECT')",
            name=op.f("attachment_owner_kind_check"),
        ),
        sa.CheckConstraint("size_bytes > 0", name=op.f("attachment_size_bytes_check")),
        sa.PrimaryKeyConstraint("id", name=op.f("attachment_pkey")),
        sa.UniqueConstraint("object_key", name=op.f("attachment_object_key_key")),
    )
    op.create_index(
        "attachment_owner_idx",
        "attachment",
        ["owner_kind", "owner_id"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "classifier_value",
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.CheckConstraint(
            "kind IN ('SEVERITY', 'PRIORITY', 'CASE_TYPE')",
            name=op.f("classifier_value_kind_check"),
        ),
        sa.PrimaryKeyConstraint("kind", "code", name=op.f("classifier_value_pkey")),
    )
    op.create_table(
        "employee_cache",
        sa.Column("external_name", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("org_unit", sa.Text(), nullable=True),
        sa.Column("account_user_id", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("external_name", name=op.f("employee_cache_pkey")),
        sa.UniqueConstraint("account_user_id", name=op.f("employee_cache_account_user_id_key")),
    )
    op.create_table(
        "environment",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("base_urls", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("environment_pkey")),
        sa.UniqueConstraint("code", name=op.f("environment_code_key")),
    )
    op.create_table(
        "import_job",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("report", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('VALIDATED', 'APPLIED', 'REJECTED')",
            name=op.f("import_job_status_check"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("import_job_pkey")),
    )
    op.create_table(
        "inbox_event",
        sa.Column("event_id", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('APPLIED', 'SKIPPED', 'FAILED')",
            name=op.f("inbox_event_status_check"),
        ),
        sa.PrimaryKeyConstraint("event_id", name=op.f("inbox_event_pkey")),
    )
    op.create_table(
        "key_counter",
        sa.Column("prefix", sa.Text(), nullable=False),
        sa.Column("last_value", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("prefix", name=op.f("key_counter_pkey")),
    )
    op.create_table(
        "outbox_message",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("destination", sa.Text(), nullable=False),
        sa.Column("partition_key", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "kind IN ('KAFKA_EVENT', 'TRACKER_BUG')",
            name=op.f("outbox_message_kind_check"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("outbox_message_pkey")),
    )
    op.create_index(
        "outbox_pending_idx",
        "outbox_message",
        ["created_at"],
        unique=False,
        postgresql_where=sa.text("sent_at IS NULL"),
    )
    op.create_table(
        "planning_item_cache",
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("logical_item_id", sa.Text(), nullable=False),
        sa.Column("item_type", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("finish_date", sa.Date(), nullable=True),
        sa.Column("parent_logical_item_id", sa.Text(), nullable=True),
        sa.Column(
            "tracker_iteration_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("plan_version_id", sa.Text(), nullable=True),
        sa.Column("data_as_of", sa.DateTime(timezone=True), nullable=True),
        sa.Column("quality", sa.Text(), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "item_type IN ('RELEASE', 'MILESTONE', 'EPIC', 'FEATURE')",
            name=op.f("planning_item_cache_item_type_check"),
        ),
        sa.CheckConstraint(
            "quality IN ('FULL', 'PARTIAL')",
            name=op.f("planning_item_cache_quality_check"),
        ),
        sa.PrimaryKeyConstraint(
            "project_id", "logical_item_id", name=op.f("planning_item_cache_pkey")
        ),
    )
    op.create_table(
        "test_case_template",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("test_case_template_pkey")),
        sa.UniqueConstraint("name", name=op.f("test_case_template_name_key")),
    )
    op.create_table(
        "test_plan",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("scope_kind", sa.Text(), nullable=False),
        sa.Column("scope_ref", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("owner", sa.Text(), nullable=False),
        sa.Column("team_ref", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("planning_project_id", sa.Text(), nullable=True),
        sa.Column("planning_release_id", sa.Text(), nullable=True),
        sa.Column("planning_plan_version_id", sa.Text(), nullable=True),
        sa.Column("planning_milestone_id", sa.Text(), nullable=True),
        sa.Column("tracker_iteration_id", sa.Text(), nullable=True),
        sa.Column(
            "refs_verified",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "scope_kind <> 'RELEASE' OR planning_release_id IS NOT NULL",
            name=op.f("test_plan_planning_release_id_check"),
        ),
        sa.CheckConstraint(
            "scope_kind IN ('RELEASE', 'ITERATION', 'PROJECT', 'MODULE')",
            name=op.f("test_plan_scope_kind_check"),
        ),
        sa.CheckConstraint(
            "scope_kind NOT IN ('RELEASE', 'PROJECT') OR planning_project_id IS NOT NULL",
            name=op.f("test_plan_planning_project_id_check"),
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'COMPLETED', 'CANCELLED')",
            name=op.f("test_plan_status_check"),
        ),
        sa.CheckConstraint("start_date <= end_date", name=op.f("test_plan_dates_check")),
        sa.PrimaryKeyConstraint("id", name=op.f("test_plan_pkey")),
        sa.UniqueConstraint("key", name=op.f("test_plan_key_key")),
    )
    op.create_index(
        "test_plan_iteration_idx",
        "test_plan",
        ["tracker_iteration_id"],
        unique=False,
        postgresql_where=sa.text("tracker_iteration_id IS NOT NULL"),
    )
    op.create_index(
        "test_plan_release_idx",
        "test_plan",
        ["planning_project_id", "planning_release_id"],
        unique=False,
        postgresql_where=sa.text("planning_release_id IS NOT NULL"),
    )
    op.create_table(
        "test_suite",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("filter", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("owner", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "kind <> 'FILTER' OR filter IS NOT NULL",
            name=op.f("test_suite_filter_check"),
        ),
        sa.CheckConstraint("kind IN ('MANUAL', 'FILTER')", name=op.f("test_suite_kind_check")),
        sa.CheckConstraint(
            "purpose IN ('GENERAL', 'SMOKE', 'ACCEPTANCE')",
            name=op.f("test_suite_purpose_check"),
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'ARCHIVED')", name=op.f("test_suite_status_check")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("test_suite_pkey")),
        sa.UniqueConstraint("name", name=op.f("test_suite_name_key")),
    )
    op.create_index(
        "test_suite_purpose_uq",
        "test_suite",
        ["purpose"],
        unique=True,
        postgresql_where=sa.text("purpose IN ('SMOKE', 'ACCEPTANCE')"),
    )
    op.create_table(
        "tracker_poll_state",
        sa.Column("stream", sa.Text(), nullable=False),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "stream IN ('work-items', 'comments')",
            name=op.f("tracker_poll_state_stream_check"),
        ),
        sa.PrimaryKeyConstraint("stream", name=op.f("tracker_poll_state_pkey")),
    )
    op.create_table(
        "tracker_status_mapping",
        sa.Column("tracker_status_id", sa.Text(), nullable=False),
        sa.Column("tracker_status_name", sa.Text(), nullable=False),
        sa.Column("qa_status", sa.Text(), nullable=True),
        sa.Column(
            "requires_assignee",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("updated_by", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "qa_status IS NULL OR qa_status IN ('OPEN', 'IN_PROGRESS', 'FIXED')",
            name=op.f("tracker_status_mapping_qa_status_check"),
        ),
        sa.PrimaryKeyConstraint("tracker_status_id", name=op.f("tracker_status_mapping_pkey")),
    )
    op.create_table(
        "run_schedule",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("suite_id", sa.Uuid(), nullable=False),
        sa.Column("environment_id", sa.Uuid(), nullable=False),
        sa.Column("cron", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(
            ["environment_id"],
            ["environment.id"],
            name=op.f("run_schedule_environment_id_fkey"),
        ),
        sa.ForeignKeyConstraint(
            ["suite_id"], ["test_suite.id"], name=op.f("run_schedule_suite_id_fkey")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("run_schedule_pkey")),
    )
    op.create_table(
        "test_case",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("module", sa.Text(), nullable=False),
        sa.Column("feature_ref", sa.Text(), nullable=True),
        sa.Column("epic_ref", sa.Text(), nullable=True),
        sa.Column("requirement_ref", sa.Text(), nullable=True),
        sa.Column("copied_from_id", sa.Uuid(), nullable=True),
        sa.Column("template_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'ACTUAL', 'NEEDS_UPDATE', 'ARCHIVED')",
            name=op.f("test_case_status_check"),
        ),
        sa.CheckConstraint("current_version > 0", name=op.f("test_case_current_version_check")),
        sa.ForeignKeyConstraint(
            ["copied_from_id"],
            ["test_case.id"],
            name=op.f("test_case_copied_from_id_fkey"),
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["test_case_template.id"],
            name=op.f("test_case_template_id_fkey"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("test_case_pkey")),
        sa.UniqueConstraint("key", name=op.f("test_case_key_key")),
    )
    op.create_index(
        "test_case_active_idx",
        "test_case",
        ["module", "status"],
        unique=False,
        postgresql_where=sa.text("status <> 'ARCHIVED'"),
    )
    op.create_table(
        "test_run",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=True),
        sa.Column("suite_id", sa.Uuid(), nullable=True),
        sa.Column("parent_run_id", sa.Uuid(), nullable=True),
        sa.Column("environment_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("started_by", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("verdict", sa.Text(), nullable=True),
        sa.Column("verdict_by", sa.Text(), nullable=True),
        sa.Column("verdict_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verdict_note", sa.Text(), nullable=True),
        sa.Column("autotests_commit_sha", sa.Text(), nullable=True),
        sa.Column("sut_versions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.BigInteger(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('CREATED', 'IN_PROGRESS', 'COMPLETED', 'ABORTED')",
            name=op.f("test_run_status_check"),
        ),
        sa.CheckConstraint(
            "trigger IN ('MANUAL', 'SCHEDULE', 'CI')",
            name=op.f("test_run_trigger_check"),
        ),
        sa.CheckConstraint(
            "verdict IS NULL OR status = 'COMPLETED'",
            name=op.f("test_run_verdict_completed_check"),
        ),
        sa.CheckConstraint(
            "verdict IS NULL OR verdict IN ('ACCEPTED', 'REJECTED')",
            name=op.f("test_run_verdict_check"),
        ),
        sa.CheckConstraint("duration_ms >= 0", name=op.f("test_run_duration_ms_check")),
        sa.CheckConstraint(
            "num_nonnulls(plan_id, suite_id) = 1", name=op.f("test_run_source_check")
        ),
        sa.ForeignKeyConstraint(
            ["environment_id"],
            ["environment.id"],
            name=op.f("test_run_environment_id_fkey"),
        ),
        sa.ForeignKeyConstraint(
            ["parent_run_id"], ["test_run.id"], name=op.f("test_run_parent_run_id_fkey")
        ),
        sa.ForeignKeyConstraint(["plan_id"], ["test_plan.id"], name=op.f("test_run_plan_id_fkey")),
        sa.ForeignKeyConstraint(
            ["suite_id"], ["test_suite.id"], name=op.f("test_run_suite_id_fkey")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("test_run_pkey")),
        sa.UniqueConstraint("key", name=op.f("test_run_key_key")),
    )
    op.create_index(
        "test_run_idempotency_uq",
        "test_run",
        ["started_by", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.create_table(
        "execution_job",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("suite_id", sa.Uuid(), nullable=True),
        sa.Column("environment_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("timeout_s", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("claimed_by", sa.Text(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('QUEUED', 'RUNNING', 'DONE', 'FAILED', 'TIMED_OUT')",
            name=op.f("execution_job_status_check"),
        ),
        sa.CheckConstraint("attempts >= 0", name=op.f("execution_job_attempts_check")),
        sa.CheckConstraint("timeout_s > 0", name=op.f("execution_job_timeout_s_check")),
        sa.ForeignKeyConstraint(
            ["run_id"], ["test_run.id"], name=op.f("execution_job_run_id_fkey")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("execution_job_pkey")),
        sa.UniqueConstraint("run_id", name=op.f("execution_job_run_id_key")),
    )
    op.create_index(
        "execution_job_queue_idx",
        "execution_job",
        ["status", "id"],
        unique=False,
        postgresql_where=sa.text("status = 'QUEUED'"),
    )
    op.create_index(
        "execution_job_suite_env_uq",
        "execution_job",
        ["suite_id", "environment_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('QUEUED', 'RUNNING')"),
    )
    op.create_table(
        "test_case_version",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("test_case_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("preconditions", sa.Text(), nullable=True),
        sa.Column("priority", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("automated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("autotest_key", sa.Text(), nullable=True),
        sa.Column("changed_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("author", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "NOT automated OR coalesce(btrim(autotest_key), '') <> ''",
            name=op.f("test_case_version_autotest_key_check"),
        ),
        sa.CheckConstraint("btrim(title) <> ''", name=op.f("test_case_version_title_check")),
        sa.CheckConstraint("version > 0", name=op.f("test_case_version_version_check")),
        sa.ForeignKeyConstraint(
            ["test_case_id"],
            ["test_case.id"],
            name=op.f("test_case_version_test_case_id_fkey"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("test_case_version_pkey")),
        sa.UniqueConstraint(
            "test_case_id",
            "version",
            name=op.f("test_case_version_test_case_id_version_key"),
        ),
    )
    op.create_index(
        "test_case_version_key_idx",
        "test_case_version",
        ["autotest_key"],
        unique=False,
        postgresql_where=sa.text("automated"),
    )
    op.create_table(
        "test_plan_case",
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("test_case_id", sa.Uuid(), nullable=False),
        sa.Column("added_by", sa.Text(), nullable=False),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["test_plan.id"], name=op.f("test_plan_case_plan_id_fkey")
        ),
        sa.ForeignKeyConstraint(
            ["test_case_id"],
            ["test_case.id"],
            name=op.f("test_plan_case_test_case_id_fkey"),
        ),
        sa.PrimaryKeyConstraint("plan_id", "test_case_id", name=op.f("test_plan_case_pkey")),
    )
    op.create_table(
        "test_suite_case",
        sa.Column("suite_id", sa.Uuid(), nullable=False),
        sa.Column("test_case_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["suite_id"], ["test_suite.id"], name=op.f("test_suite_case_suite_id_fkey")
        ),
        sa.ForeignKeyConstraint(
            ["test_case_id"],
            ["test_case.id"],
            name=op.f("test_suite_case_test_case_id_fkey"),
        ),
        sa.PrimaryKeyConstraint("suite_id", "test_case_id", name=op.f("test_suite_case_pkey")),
    )
    op.create_table(
        "run_result",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("test_case_id", sa.Uuid(), nullable=False),
        sa.Column("case_version_id", sa.Uuid(), nullable=False),
        sa.Column("assignee", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("failed_step_position", sa.Integer(), nullable=True),
        sa.Column("actual_result", sa.Text(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("log_text", sa.Text(), nullable=True),
        sa.Column("executed_by", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.BigInteger(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('NOT_RUN', 'PASSED', 'FAILED', 'BLOCKED', 'SKIPPED')",
            name=op.f("run_result_status_check"),
        ),
        sa.CheckConstraint("duration_ms >= 0", name=op.f("run_result_duration_ms_check")),
        sa.ForeignKeyConstraint(
            ["case_version_id"],
            ["test_case_version.id"],
            name=op.f("run_result_case_version_id_fkey"),
        ),
        sa.ForeignKeyConstraint(["run_id"], ["test_run.id"], name=op.f("run_result_run_id_fkey")),
        sa.ForeignKeyConstraint(
            ["test_case_id"],
            ["test_case.id"],
            name=op.f("run_result_test_case_id_fkey"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("run_result_pkey")),
        sa.UniqueConstraint(
            "run_id", "test_case_id", name=op.f("run_result_run_id_test_case_id_key")
        ),
    )
    op.create_index(
        "run_result_assignee_idx",
        "run_result",
        ["assignee", "status"],
        unique=False,
        postgresql_where=sa.text("status = 'NOT_RUN'"),
    )
    op.create_index(
        "run_result_last_idx",
        "run_result",
        ["test_case_id", sa.literal_column("finished_at DESC")],
        unique=False,
        postgresql_where=sa.text("status <> 'NOT_RUN'"),
    )
    op.create_index("run_result_status_idx", "run_result", ["run_id", "status"], unique=False)
    op.create_index("run_result_updated_idx", "run_result", ["updated_at"], unique=False)
    op.create_table(
        "test_step",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("case_version_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("expected_result", sa.Text(), nullable=False),
        sa.CheckConstraint("position > 0", name=op.f("test_step_position_check")),
        sa.ForeignKeyConstraint(
            ["case_version_id"],
            ["test_case_version.id"],
            name=op.f("test_step_case_version_id_fkey"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("test_step_pkey")),
        sa.UniqueConstraint(
            "case_version_id",
            "position",
            name=op.f("test_step_case_version_id_position_key"),
        ),
    )
    op.create_table(
        "defect",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("repro_steps", sa.Text(), nullable=True),
        sa.Column("expected_result", sa.Text(), nullable=True),
        sa.Column("actual_result", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("proposed_priority", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("environment_id", sa.Uuid(), nullable=True),
        sa.Column("build_version", sa.Text(), nullable=True),
        sa.Column("author", sa.Text(), nullable=False),
        sa.Column("test_case_id", sa.Uuid(), nullable=True),
        sa.Column("case_version_id", sa.Uuid(), nullable=True),
        sa.Column("failed_step_id", sa.Uuid(), nullable=True),
        sa.Column("plan_id", sa.Uuid(), nullable=True),
        sa.Column("requirement_ref", sa.Text(), nullable=True),
        sa.Column("epic_ref", sa.Text(), nullable=True),
        sa.Column("tracker_work_item_id", sa.Text(), nullable=True),
        sa.Column("tracker_work_item_url", sa.Text(), nullable=True),
        sa.Column("tracker_sync_state", sa.Text(), server_default="PENDING", nullable=False),
        sa.Column("tracker_status", sa.Text(), nullable=True),
        sa.Column("tracker_priority", sa.Text(), nullable=True),
        sa.Column("tracker_assignee", sa.Text(), nullable=True),
        sa.Column("tracker_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "tracker_mismatch",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("reopen_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("origin IN ('AUTO', 'MANUAL')", name=op.f("defect_origin_check")),
        sa.CheckConstraint(
            "status IN ('NEW', 'OPEN', 'IN_PROGRESS', 'FIXED', 'READY_FOR_TEST', 'CLOSED', 'REOPENED')",
            name=op.f("defect_status_check"),
        ),
        sa.CheckConstraint(
            "tracker_sync_state IN ('PENDING', 'SYNCED', 'FAILED')",
            name=op.f("defect_tracker_sync_state_check"),
        ),
        sa.CheckConstraint("reopen_count >= 0", name=op.f("defect_reopen_count_check")),
        sa.ForeignKeyConstraint(
            ["case_version_id"],
            ["test_case_version.id"],
            name=op.f("defect_case_version_id_fkey"),
        ),
        sa.ForeignKeyConstraint(
            ["environment_id"],
            ["environment.id"],
            name=op.f("defect_environment_id_fkey"),
        ),
        sa.ForeignKeyConstraint(
            ["failed_step_id"],
            ["test_step.id"],
            name=op.f("defect_failed_step_id_fkey"),
        ),
        sa.ForeignKeyConstraint(["plan_id"], ["test_plan.id"], name=op.f("defect_plan_id_fkey")),
        sa.ForeignKeyConstraint(
            ["test_case_id"], ["test_case.id"], name=op.f("defect_test_case_id_fkey")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("defect_pkey")),
        sa.UniqueConstraint("key", name=op.f("defect_key_key")),
    )
    op.create_index("defect_filter_idx", "defect", ["status", "severity"], unique=False)
    op.create_index(
        "defect_mismatch_idx",
        "defect",
        ["tracker_mismatch"],
        unique=False,
        postgresql_where=sa.text("tracker_mismatch"),
    )
    op.create_index(
        "defect_open_auto_uq",
        "defect",
        ["test_case_id"],
        unique=True,
        postgresql_where=sa.text("origin = 'AUTO' AND status <> 'CLOSED'"),
    )
    op.create_table(
        "step_result",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("run_result_id", sa.Uuid(), nullable=False),
        sa.Column("step_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("actual_result", sa.Text(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('NOT_RUN', 'PASSED', 'FAILED', 'BLOCKED', 'SKIPPED')",
            name=op.f("step_result_status_check"),
        ),
        sa.ForeignKeyConstraint(
            ["run_result_id"],
            ["run_result.id"],
            name=op.f("step_result_run_result_id_fkey"),
        ),
        sa.ForeignKeyConstraint(
            ["step_id"], ["test_step.id"], name=op.f("step_result_step_id_fkey")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("step_result_pkey")),
        sa.UniqueConstraint(
            "run_result_id",
            "step_id",
            name=op.f("step_result_run_result_id_step_id_key"),
        ),
    )
    op.create_table(
        "defect_comment",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("defect_id", sa.Uuid(), nullable=False),
        sa.Column("author", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("external_comment_id", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["defect_id"], ["defect.id"], name=op.f("defect_comment_defect_id_fkey")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("defect_comment_pkey")),
        sa.UniqueConstraint(
            "external_comment_id", name=op.f("defect_comment_external_comment_id_key")
        ),
    )
    op.create_table(
        "defect_history",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("defect_id", sa.Uuid(), nullable=False),
        sa.Column("author", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("field", sa.Text(), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source IN ('QA', 'TRACKER', 'SYSTEM')",
            name=op.f("defect_history_source_check"),
        ),
        sa.ForeignKeyConstraint(
            ["defect_id"], ["defect.id"], name=op.f("defect_history_defect_id_fkey")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("defect_history_pkey")),
    )
    op.create_index(
        "defect_history_idx",
        "defect_history",
        ["defect_id", sa.literal_column("occurred_at DESC")],
        unique=False,
    )
    op.create_table(
        "defect_run_link",
        sa.Column("defect_id", sa.Uuid(), nullable=False),
        sa.Column("run_result_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["defect_id"], ["defect.id"], name=op.f("defect_run_link_defect_id_fkey")
        ),
        sa.ForeignKeyConstraint(
            ["run_result_id"],
            ["run_result.id"],
            name=op.f("defect_run_link_run_result_id_fkey"),
        ),
        sa.PrimaryKeyConstraint("defect_id", "run_result_id", name=op.f("defect_run_link_pkey")),
    )


def downgrade() -> None:
    op.drop_table("defect_run_link")
    op.drop_index("defect_history_idx", table_name="defect_history")
    op.drop_table("defect_history")
    op.drop_table("defect_comment")
    op.drop_table("step_result")
    op.drop_index(
        "defect_open_auto_uq",
        table_name="defect",
        postgresql_where=sa.text("origin = 'AUTO' AND status <> 'CLOSED'"),
    )
    op.drop_index(
        "defect_mismatch_idx",
        table_name="defect",
        postgresql_where=sa.text("tracker_mismatch"),
    )
    op.drop_index("defect_filter_idx", table_name="defect")
    op.drop_table("defect")
    op.drop_table("test_step")
    op.drop_index("run_result_updated_idx", table_name="run_result")
    op.drop_index("run_result_status_idx", table_name="run_result")
    op.drop_index(
        "run_result_last_idx",
        table_name="run_result",
        postgresql_where=sa.text("status <> 'NOT_RUN'"),
    )
    op.drop_index(
        "run_result_assignee_idx",
        table_name="run_result",
        postgresql_where=sa.text("status = 'NOT_RUN'"),
    )
    op.drop_table("run_result")
    op.drop_table("test_suite_case")
    op.drop_table("test_plan_case")
    op.drop_index(
        "test_case_version_key_idx",
        table_name="test_case_version",
        postgresql_where=sa.text("automated"),
    )
    op.drop_table("test_case_version")
    op.drop_index(
        "execution_job_suite_env_uq",
        table_name="execution_job",
        postgresql_where=sa.text("status IN ('QUEUED', 'RUNNING')"),
    )
    op.drop_index(
        "execution_job_queue_idx",
        table_name="execution_job",
        postgresql_where=sa.text("status = 'QUEUED'"),
    )
    op.drop_table("execution_job")
    op.drop_index(
        "test_run_idempotency_uq",
        table_name="test_run",
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.drop_table("test_run")
    op.drop_index(
        "test_case_active_idx",
        table_name="test_case",
        postgresql_where=sa.text("status <> 'ARCHIVED'"),
    )
    op.drop_table("test_case")
    op.drop_table("run_schedule")
    op.drop_table("tracker_status_mapping")
    op.drop_table("tracker_poll_state")
    op.drop_index(
        "test_suite_purpose_uq",
        table_name="test_suite",
        postgresql_where=sa.text("purpose IN ('SMOKE', 'ACCEPTANCE')"),
    )
    op.drop_table("test_suite")
    op.drop_index(
        "test_plan_release_idx",
        table_name="test_plan",
        postgresql_where=sa.text("planning_release_id IS NOT NULL"),
    )
    op.drop_index(
        "test_plan_iteration_idx",
        table_name="test_plan",
        postgresql_where=sa.text("tracker_iteration_id IS NOT NULL"),
    )
    op.drop_table("test_plan")
    op.drop_table("test_case_template")
    op.drop_table("planning_item_cache")
    op.drop_index(
        "outbox_pending_idx",
        table_name="outbox_message",
        postgresql_where=sa.text("sent_at IS NULL"),
    )
    op.drop_table("outbox_message")
    op.drop_table("key_counter")
    op.drop_table("inbox_event")
    op.drop_table("import_job")
    op.drop_table("environment")
    op.drop_table("employee_cache")
    op.drop_table("classifier_value")
    op.drop_index(
        "attachment_owner_idx",
        table_name="attachment",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_table("attachment")

"""Прогоны, задания исполнителя, расписания и окружения: 120, раздел 4."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, UniqueConstraint, text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, created_at_column, one_of, updated_at_column, uuid_pk
from app.models.enums import JobStatus, ResultStatus, RunStatus, RunTrigger, Verdict


class Environment(Base):
    __tablename__ = "environment"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
    base_urls: Mapped[dict]
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())


class TestRun(Base):
    __tablename__ = "test_run"
    __test__ = False
    __table_args__ = (
        one_of("status", RunStatus),
        one_of("trigger", RunTrigger),
        one_of("verdict", Verdict, nullable=True),
        CheckConstraint("num_nonnulls(plan_id, suite_id) = 1", name="source"),
        # Проверка «только для набора ACCEPTANCE» требует чужой таблицы и делается в сервисе.
        CheckConstraint("verdict IS NULL OR status = 'COMPLETED'", name="verdict_completed"),
        CheckConstraint("duration_ms >= 0", name="duration_ms"),
        Index(
            "test_run_idempotency_uq",
            "started_by",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    key: Mapped[str] = mapped_column(unique=True)
    plan_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("test_plan.id"))
    suite_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("test_suite.id"))
    parent_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("test_run.id"))
    environment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("environment.id"))
    status: Mapped[str]
    trigger: Mapped[str]
    started_by: Mapped[str]
    idempotency_key: Mapped[str | None]
    verdict: Mapped[str | None]
    verdict_by: Mapped[str | None]
    verdict_at: Mapped[datetime | None]
    verdict_note: Mapped[str | None]
    autotests_commit_sha: Mapped[str | None]
    sut_versions: Mapped[dict | None]
    created_at: Mapped[datetime] = created_at_column()
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)
    updated_at: Mapped[datetime] = updated_at_column()


class RunResult(Base):
    __tablename__ = "run_result"
    __table_args__ = (
        UniqueConstraint("run_id", "test_case_id"),
        one_of("status", ResultStatus),
        CheckConstraint("duration_ms >= 0", name="duration_ms"),
        Index("run_result_status_idx", "run_id", "status"),
        Index(
            "run_result_assignee_idx",
            "assignee",
            "status",
            postgresql_where=text("status = 'NOT_RUN'"),
        ),
        Index(
            "run_result_last_idx",
            "test_case_id",
            text("finished_at DESC"),
            postgresql_where=text("status <> 'NOT_RUN'"),
        ),
        Index("run_result_updated_idx", "updated_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_run.id"))
    test_case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_case.id"))
    case_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_case_version.id"))
    assignee: Mapped[str | None]
    status: Mapped[str]
    failed_step_position: Mapped[int | None]
    actual_result: Mapped[str | None]
    comment: Mapped[str | None]
    failure_reason: Mapped[str | None]
    log_text: Mapped[str | None]
    executed_by: Mapped[str | None]
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)
    updated_at: Mapped[datetime] = updated_at_column()

    step_results: Mapped[list["StepResult"]] = relationship()


class StepResult(Base):
    __tablename__ = "step_result"
    __table_args__ = (
        UniqueConstraint("run_result_id", "step_id"),
        one_of("status", ResultStatus),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    run_result_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("run_result.id"))
    step_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_step.id"))
    status: Mapped[str]
    actual_result: Mapped[str | None]
    comment: Mapped[str | None]


class ExecutionJob(Base):
    """Очередь исполнителя (ADR-004)."""

    __tablename__ = "execution_job"
    __table_args__ = (
        one_of("status", JobStatus),
        CheckConstraint("timeout_s > 0", name="timeout_s"),
        CheckConstraint("attempts >= 0", name="attempts"),
        Index(
            "execution_job_queue_idx", "status", "id", postgresql_where=text("status = 'QUEUED'")
        ),
        # FR-RUN-10: один набор на окружении одновременно.
        Index(
            "execution_job_suite_env_uq",
            "suite_id",
            "environment_id",
            unique=True,
            postgresql_where=text("status IN ('QUEUED', 'RUNNING')"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_run.id"), unique=True)
    # Копии из прогона для ограничения уникальности; внешних ключей нет.
    suite_id: Mapped[uuid.UUID | None]
    environment_id: Mapped[uuid.UUID]
    status: Mapped[str]
    timeout_s: Mapped[int]
    attempts: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    claimed_by: Mapped[str | None]
    claimed_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    error: Mapped[str | None]


class RunSchedule(Base):
    __tablename__ = "run_schedule"

    id: Mapped[uuid.UUID] = uuid_pk()
    suite_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_suite.id"))
    environment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("environment.id"))
    cron: Mapped[str]
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())

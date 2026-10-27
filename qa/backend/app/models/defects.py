"""Дефекты: 120, раздел 5."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, false, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_column, one_of, updated_at_column, uuid_pk
from app.models.enums import (
    ChangeSource,
    DefectOrigin,
    DefectStatus,
    TrackerSyncState,
)


class Defect(Base):
    __tablename__ = "defect"
    __table_args__ = (
        one_of("origin", DefectOrigin),
        one_of("status", DefectStatus),
        one_of("tracker_sync_state", TrackerSyncState),
        CheckConstraint("reopen_count >= 0", name="reopen_count"),
        Index("defect_mismatch_idx", "tracker_mismatch", postgresql_where=text("tracker_mismatch")),
        # FR-DEF-03, ADR-006: один незакрытый автодефект на кейс.
        Index(
            "defect_open_auto_uq",
            "test_case_id",
            unique=True,
            postgresql_where=text("origin = 'AUTO' AND status <> 'CLOSED'"),
        ),
        Index("defect_filter_idx", "status", "severity"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    key: Mapped[str] = mapped_column(unique=True)
    origin: Mapped[str]
    title: Mapped[str]
    description: Mapped[str | None]
    repro_steps: Mapped[str | None]
    expected_result: Mapped[str | None]
    actual_result: Mapped[str]
    severity: Mapped[str]
    proposed_priority: Mapped[str]
    status: Mapped[str]
    environment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("environment.id"))
    build_version: Mapped[str | None]
    author: Mapped[str]
    test_case_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("test_case.id"))
    case_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("test_case_version.id"))
    failed_step_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("test_step.id"))
    plan_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("test_plan.id"))
    requirement_ref: Mapped[str | None]
    epic_ref: Mapped[str | None]
    tracker_work_item_id: Mapped[str | None]
    tracker_work_item_url: Mapped[str | None]
    tracker_sync_state: Mapped[str] = mapped_column(
        default=TrackerSyncState.PENDING, server_default=TrackerSyncState.PENDING
    )
    tracker_status: Mapped[str | None]
    tracker_priority: Mapped[str | None]
    tracker_assignee: Mapped[str | None]
    tracker_updated_at: Mapped[datetime | None]
    tracker_mismatch: Mapped[bool] = mapped_column(default=False, server_default=false())
    reopen_count: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()
    closed_at: Mapped[datetime | None]


class DefectRunLink(Base):
    __tablename__ = "defect_run_link"

    defect_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("defect.id"), primary_key=True)
    run_result_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("run_result.id"), primary_key=True)
    created_at: Mapped[datetime] = created_at_column()


class DefectHistory(Base):
    """Строки не изменяются после вставки."""

    __tablename__ = "defect_history"
    __table_args__ = (
        one_of("source", ChangeSource),
        Index("defect_history_idx", "defect_id", text("occurred_at DESC")),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    defect_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("defect.id"))
    author: Mapped[str]
    source: Mapped[str]
    field: Mapped[str]
    old_value: Mapped[str | None]
    new_value: Mapped[str | None]
    occurred_at: Mapped[datetime] = created_at_column()


class DefectComment(Base):
    __tablename__ = "defect_comment"

    id: Mapped[uuid.UUID] = uuid_pk()
    defect_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("defect.id"))
    author: Mapped[str]
    source: Mapped[str]
    body: Mapped[str]
    external_comment_id: Mapped[str | None] = mapped_column(unique=True)
    created_at: Mapped[datetime] = created_at_column()

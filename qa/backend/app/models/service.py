"""Служебные таблицы: 120, раздел 6."""

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, Index, PrimaryKeyConstraint, false, text, true
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_column, one_of, updated_at_column, uuid_pk
from app.models.enums import (
    TRACKER_OWNED_STATUSES,
    AttachmentOwner,
    CacheQuality,
    ClassifierKind,
    ImportStatus,
    InboxStatus,
    OutboxKind,
    PlanningItemType,
    PollStream,
)


class Attachment(Base):
    __tablename__ = "attachment"
    __table_args__ = (
        one_of("owner_kind", AttachmentOwner),
        CheckConstraint("size_bytes > 0", name="size_bytes"),
        Index(
            "attachment_owner_idx",
            "owner_kind",
            "owner_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    owner_kind: Mapped[str]
    owner_id: Mapped[uuid.UUID]
    file_name: Mapped[str]
    content_type: Mapped[str]
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    object_key: Mapped[str] = mapped_column(unique=True)
    checksum: Mapped[str]
    uploaded_by: Mapped[str]
    uploaded_at: Mapped[datetime] = created_at_column()
    deleted_at: Mapped[datetime | None]


class ClassifierValue(Base):
    """Серьёзность, приоритет и типы кейсов ведёт QA System (ADR-009)."""

    __tablename__ = "classifier_value"
    __table_args__ = (PrimaryKeyConstraint("kind", "code"), one_of("kind", ClassifierKind))

    kind: Mapped[str]
    code: Mapped[str]
    name: Mapped[str]
    sort_order: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())


class EmployeeCache(Base):
    """Кэш сотрудников Reference Manager (ADR-016)."""

    __tablename__ = "employee_cache"

    external_name: Mapped[str] = mapped_column(primary_key=True)
    display_name: Mapped[str]
    org_unit: Mapped[str | None]
    account_user_id: Mapped[str | None] = mapped_column(unique=True)
    is_active: Mapped[bool]
    synced_at: Mapped[datetime]


class PlanningItemCache(Base):
    """Кэш release-context Planning System (ADR-015)."""

    __tablename__ = "planning_item_cache"
    __table_args__ = (
        PrimaryKeyConstraint("project_id", "logical_item_id"),
        one_of("item_type", PlanningItemType),
        one_of("quality", CacheQuality),
    )

    project_id: Mapped[str]
    logical_item_id: Mapped[str]
    item_type: Mapped[str]
    name: Mapped[str]
    start_date: Mapped[date | None]
    finish_date: Mapped[date | None]
    parent_logical_item_id: Mapped[str | None]
    tracker_iteration_ids: Mapped[list] = mapped_column(
        default=list, server_default=text("'[]'::jsonb")
    )
    plan_version_id: Mapped[str | None]
    data_as_of: Mapped[datetime | None]
    quality: Mapped[str]
    synced_at: Mapped[datetime]


class TrackerStatusMapping(Base):
    """Маппинг статусов «Ошибки» Task Tracker (ADR-008). qa_status NULL — «не менять»."""

    __tablename__ = "tracker_status_mapping"
    __table_args__ = (one_of("qa_status", TRACKER_OWNED_STATUSES, nullable=True),)

    tracker_status_id: Mapped[str] = mapped_column(primary_key=True)
    tracker_status_name: Mapped[str]
    qa_status: Mapped[str | None]
    requires_assignee: Mapped[bool] = mapped_column(default=False, server_default=false())
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())
    updated_by: Mapped[str]
    updated_at: Mapped[datetime] = updated_at_column()


class TrackerPollState(Base):
    __tablename__ = "tracker_poll_state"
    __table_args__ = (one_of("stream", PollStream),)

    stream: Mapped[str] = mapped_column(primary_key=True)
    last_updated_at: Mapped[datetime | None]
    last_success_at: Mapped[datetime | None]
    last_error: Mapped[str | None]


class OutboxMessage(Base):
    """Исходящие события и запросы к Task Tracker (ADR-007); id — он же eventId."""

    __tablename__ = "outbox_message"
    __table_args__ = (
        one_of("kind", OutboxKind),
        Index("outbox_pending_idx", "created_at", postgresql_where=text("sent_at IS NULL")),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    kind: Mapped[str]
    destination: Mapped[str]
    partition_key: Mapped[str | None]
    payload: Mapped[dict]
    attempts: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    created_at: Mapped[datetime] = created_at_column()
    sent_at: Mapped[datetime | None]
    last_error: Mapped[str | None]


class InboxEvent(Base):
    __tablename__ = "inbox_event"
    __table_args__ = (one_of("status", InboxStatus),)

    event_id: Mapped[str] = mapped_column(primary_key=True)
    source: Mapped[str]
    received_at: Mapped[datetime] = created_at_column()
    status: Mapped[str]
    attempts: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    last_error: Mapped[str | None]


class ImportJob(Base):
    __tablename__ = "import_job"
    __table_args__ = (one_of("status", ImportStatus),)

    id: Mapped[uuid.UUID] = uuid_pk()
    file_name: Mapped[str]
    status: Mapped[str]
    report: Mapped[dict]
    created_by: Mapped[str]
    created_at: Mapped[datetime] = created_at_column()


class KeyCounter(Base):
    """Счётчики читаемых ключей; см. app/keys.py."""

    __tablename__ = "key_counter"

    prefix: Mapped[str] = mapped_column(primary_key=True)
    last_value: Mapped[int] = mapped_column(BigInteger)

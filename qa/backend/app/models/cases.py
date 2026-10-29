"""Тест-кейсы: 120, раздел 2."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, UniqueConstraint, false, text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, created_at_column, one_of, updated_at_column, uuid_pk
from app.models.enums import CaseStatus


class TestCaseTemplate(Base):
    __tablename__ = "test_case_template"
    __test__ = False

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(unique=True)
    description: Mapped[str | None]
    body: Mapped[dict]
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())


class TestCase(Base):
    __tablename__ = "test_case"
    __test__ = False
    __table_args__ = (
        one_of("status", CaseStatus),
        CheckConstraint("current_version > 0", name="current_version"),
        Index(
            "test_case_active_idx",
            "module",
            "status",
            postgresql_where=text("status <> 'ARCHIVED'"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    key: Mapped[str] = mapped_column(unique=True)
    status: Mapped[str]
    current_version: Mapped[int]
    module: Mapped[str]
    feature_ref: Mapped[str | None]
    epic_ref: Mapped[str | None]
    requirement_ref: Mapped[str | None]
    copied_from_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("test_case.id"))
    template_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("test_case_template.id"))
    created_by: Mapped[str]
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()

    # Текущая версия — та, чей номер равен current_version (050, раздел 2а).
    current: Mapped["TestCaseVersion"] = relationship(
        primaryjoin="and_(TestCase.id == foreign(TestCaseVersion.test_case_id), "
        "TestCase.current_version == foreign(TestCaseVersion.version))",
        viewonly=True,
    )


class TestCaseVersion(Base):
    """Строки не изменяются и не удаляются после вставки (ADR-003)."""

    __tablename__ = "test_case_version"
    __test__ = False
    __table_args__ = (
        UniqueConstraint("test_case_id", "version"),
        CheckConstraint("version > 0", name="version"),
        CheckConstraint("btrim(title) <> ''", name="title"),
        CheckConstraint(
            "NOT automated OR coalesce(btrim(autotest_key), '') <> ''", name="autotest_key"
        ),
        Index("test_case_version_key_idx", "autotest_key", postgresql_where=text("automated")),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    test_case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_case.id"))
    version: Mapped[int]
    title: Mapped[str]
    description: Mapped[str | None]
    preconditions: Mapped[str | None]
    priority: Mapped[str]
    severity: Mapped[str]
    type: Mapped[str]
    automated: Mapped[bool] = mapped_column(default=False, server_default=false())
    autotest_key: Mapped[str | None]
    changed_fields: Mapped[list]
    author: Mapped[str]
    created_at: Mapped[datetime] = created_at_column()

    steps: Mapped[list["TestStep"]] = relationship(order_by="TestStep.position")


class TestStep(Base):
    __tablename__ = "test_step"
    __test__ = False
    __table_args__ = (
        UniqueConstraint("case_version_id", "position"),
        CheckConstraint("position > 0", name="position"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    case_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_case_version.id"))
    position: Mapped[int]
    action: Mapped[str]
    expected_result: Mapped[str]

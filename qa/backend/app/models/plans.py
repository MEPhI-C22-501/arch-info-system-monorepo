"""Наборы и тест-планы: 120, раздел 3."""

import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, false, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_column, one_of, updated_at_column, uuid_pk
from app.models.enums import PlanScope, PlanStatus, SuiteKind, SuitePurpose, SuiteStatus


class TestSuite(Base):
    __tablename__ = "test_suite"
    __test__ = False
    __table_args__ = (
        one_of("kind", SuiteKind),
        one_of("status", SuiteStatus),
        one_of("purpose", SuitePurpose),
        CheckConstraint("kind <> 'FILTER' OR filter IS NOT NULL", name="filter"),
        # «Smoke» и «Приёмка стенда» существуют в одном экземпляре (ADR-017).
        Index(
            "test_suite_purpose_uq",
            "purpose",
            unique=True,
            postgresql_where=text("purpose IN ('SMOKE', 'ACCEPTANCE')"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(unique=True)
    kind: Mapped[str]
    filter: Mapped[dict | None]
    status: Mapped[str]
    purpose: Mapped[str]
    owner: Mapped[str]


class TestSuiteCase(Base):
    __tablename__ = "test_suite_case"
    __test__ = False

    suite_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_suite.id"), primary_key=True)
    test_case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_case.id"), primary_key=True)


class TestPlan(Base):
    __tablename__ = "test_plan"
    __test__ = False
    __table_args__ = (
        one_of("scope_kind", PlanScope),
        one_of("status", PlanStatus),
        CheckConstraint("start_date <= end_date", name="dates"),
        CheckConstraint(
            "scope_kind NOT IN ('RELEASE', 'PROJECT') OR planning_project_id IS NOT NULL",
            name="planning_project_id",
        ),
        CheckConstraint(
            "scope_kind <> 'RELEASE' OR planning_release_id IS NOT NULL",
            name="planning_release_id",
        ),
        Index(
            "test_plan_iteration_idx",
            "tracker_iteration_id",
            postgresql_where=text("tracker_iteration_id IS NOT NULL"),
        ),
        Index(
            "test_plan_release_idx",
            "planning_project_id",
            "planning_release_id",
            postgresql_where=text("planning_release_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    key: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
    scope_kind: Mapped[str]
    scope_ref: Mapped[str | None]
    status: Mapped[str]
    owner: Mapped[str]
    team_ref: Mapped[str | None]
    start_date: Mapped[date]
    end_date: Mapped[date]
    planning_project_id: Mapped[str | None]
    planning_release_id: Mapped[str | None]
    planning_plan_version_id: Mapped[str | None]
    planning_milestone_id: Mapped[str | None]
    tracker_iteration_id: Mapped[str | None]
    refs_verified: Mapped[bool] = mapped_column(default=False, server_default=false())
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()


class TestPlanCase(Base):
    __tablename__ = "test_plan_case"
    __test__ = False

    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_plan.id"), primary_key=True)
    test_case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_case.id"), primary_key=True)
    added_by: Mapped[str]
    added_at: Mapped[datetime] = created_at_column()

import uuid
from datetime import date, datetime

from pydantic import Field

from app.cases.schemas import CaseFilter, LastResult
from app.models.enums import CaseStatus, DefectStatus, PlanScope, PlanStatus
from app.schemas import ApiModel, NonEmptyStr


class TestPlanInput(ApiModel):
    __test__ = False

    name: NonEmptyStr
    scope_kind: PlanScope
    scope_ref: str | None = None
    owner: NonEmptyStr
    team_ref: str | None = None
    start_date: date
    end_date: date
    tracker_iteration_id: str | None = None
    planning_milestone_id: str | None = None
    planning_project_id: str | None = None
    planning_release_id: str | None = None
    planning_plan_version_id: str | None = None


class TestPlan(ApiModel):
    __test__ = False

    id: uuid.UUID
    key: str
    status: PlanStatus
    name: str
    scope_kind: PlanScope
    scope_ref: str | None
    owner: str
    team_ref: str | None
    start_date: date
    end_date: date
    tracker_iteration_id: str | None
    planning_milestone_id: str | None
    planning_project_id: str | None
    planning_release_id: str | None
    planning_plan_version_id: str | None
    refs_verified: bool
    created_at: datetime
    updated_at: datetime
    case_ids: list[uuid.UUID] = Field([], description="Состав плана, по ключу кейса")
    case_count: int = 0


class PlanCasesInput(ApiModel):
    ids: list[uuid.UUID] | None = None
    filter: CaseFilter | None = None
    save_as_suite: NonEmptyStr | None = Field(
        None, description="Имя набора FILTER, под которым сохраняется filter"
    )


class PlanSummaryCase(ApiModel):
    test_case_id: uuid.UUID
    test_case_key: str
    title: str
    status: CaseStatus
    last_result: LastResult | None


class PlanSummaryCounters(ApiModel):
    total: int = 0
    passed: int = 0
    failed: int = 0
    blocked: int = 0
    skipped: int = 0
    not_run: int = 0


class PlanSummaryDefect(ApiModel):
    id: uuid.UUID
    key: str
    title: str
    status: DefectStatus
    severity: str
    test_case_id: uuid.UUID


class PlanSummary(ApiModel):
    plan_id: uuid.UUID
    counters: PlanSummaryCounters
    cases: list[PlanSummaryCase]
    open_defects: list[PlanSummaryDefect]

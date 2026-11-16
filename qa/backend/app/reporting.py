"""Read-only QA projection for the Reports ETL."""

from collections import defaultdict
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth import Role, require_roles
from app.db import get_session
from app.models import (
    Defect,
    DefectHistory,
    RunResult,
    TestCase,
    TestCaseVersion,
    TestPlan,
    TestRun,
)
from app.schemas import ApiModel, Page, PageParams, paginate_rows

router = APIRouter(
    prefix="/reports", tags=["reports"], dependencies=[Depends(require_roles(Role.REPORTS_READER))]
)

# Expose projections, not the interactive APIs (which can include logs and comments).
PROJECTIONS = {
    "test-cases": (
        TestCase,
        {
            "key": "key",
            "status": "status",
            "module": "module",
            "version": "current_version",
            "authorId": "created_by",
            "createdAt": "created_at",
        },
    ),
    "test-plans": (
        TestPlan,
        {
            "title": "name",
            "status": "status",
            "authorId": "owner",
            "planningProjectId": "planning_project_id",
            "planningReleaseId": "planning_release_id",
            "trackerIterationId": "tracker_iteration_id",
            "createdAt": "created_at",
        },
    ),
    "test-runs": (
        TestRun,
        {
            "planId": "plan_id",
            "suiteId": "suite_id",
            "status": "status",
            "authorId": "started_by",
            "createdAt": "created_at",
            "startedAt": "started_at",
            "finishedAt": "finished_at",
        },
    ),
    "test-results": (
        RunResult,
        {
            "runId": "run_id",
            "testCaseId": "test_case_id",
            "status": "status",
            "assigneeId": "assignee",
            "executedBy": "executed_by",
            "finishedAt": "finished_at",
        },
    ),
    "defects": (
        Defect,
        {
            "title": "title",
            "planId": "plan_id",
            "testCaseId": "test_case_id",
            "status": "status",
            "severity": "severity",
            "authorId": "author",
            "assigneeId": "tracker_assignee",
            "trackerWorkItemId": "tracker_work_item_id",
            "reopenCount": "reopen_count",
            "createdAt": "created_at",
            "closedAt": "closed_at",
        },
    ),
}


class ReportRow(ApiModel):
    id: str
    updated_at: datetime
    model_config = {"extra": "allow"}


def endpoint_for(resource: str):
    model, fields = PROJECTIONS[resource]

    def endpoint(
        updated_since: AwareDatetime | None = Query(None, alias="updatedSince"),
        params: PageParams = Depends(),
        session: Session = Depends(get_session),
    ) -> Page[ReportRow]:
        stmt = select(model).order_by(model.updated_at, model.id)
        if updated_since is not None:
            stmt = stmt.where(model.updated_at >= updated_since)
        if model is TestCase:
            stmt = stmt.options(joinedload(TestCase.current))

        def build(rows: list[Any]) -> list[ReportRow]:
            histories = defaultdict(list)
            versions = {}
            if model is Defect and rows:
                changes = session.scalars(
                    select(DefectHistory)
                    .where(
                        DefectHistory.defect_id.in_([row.id for row in rows]),
                        DefectHistory.field == "status",
                    )
                    .order_by(DefectHistory.occurred_at, DefectHistory.id)
                )
                for change in changes:
                    histories[change.defect_id].append(
                        {
                            "oldValue": change.old_value,
                            "newValue": change.new_value,
                            "occurredAt": change.occurred_at,
                        }
                    )
            if model is RunResult and rows:
                versions = dict(
                    session.execute(
                        select(TestCaseVersion.id, TestCaseVersion.version).where(
                            TestCaseVersion.id.in_([row.case_version_id for row in rows])
                        )
                    ).all()
                )

            result = []
            for row in rows:
                values = {name: getattr(row, column) for name, column in fields.items()}
                if model is TestCase and row.current:
                    values.update(title=row.current.title, automated=row.current.automated)
                elif model is Defect:
                    values["history"] = histories[row.id]
                elif model is RunResult:
                    values["caseVersion"] = versions.get(row.case_version_id)
                result.append(ReportRow(id=str(row.id), updated_at=row.updated_at, **values))
            return result

        return paginate_rows(session, stmt, params, ReportRow, build)

    return endpoint


for resource in PROJECTIONS:
    router.add_api_route("/" + resource, endpoint_for(resource), methods=["GET"], name=resource)

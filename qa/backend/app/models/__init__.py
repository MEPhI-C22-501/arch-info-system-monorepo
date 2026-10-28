"""Все модели; импорт пакета регистрирует таблицы в Base.metadata."""

from app.models.base import Base
from app.models.cases import TestCase, TestCaseTemplate, TestCaseVersion, TestStep
from app.models.defects import Defect, DefectComment, DefectHistory, DefectRunLink
from app.models.plans import TestPlan, TestPlanCase, TestSuite, TestSuiteCase
from app.models.runs import (
    Environment,
    ExecutionJob,
    RunResult,
    RunSchedule,
    StepResult,
    TestRun,
)
from app.models.service import (
    Attachment,
    ClassifierValue,
    EmployeeCache,
    ImportJob,
    InboxEvent,
    KeyCounter,
    OutboxMessage,
    PlanningItemCache,
    TrackerPollState,
    TrackerStatusMapping,
)

__all__ = [
    "Attachment",
    "Base",
    "ClassifierValue",
    "Defect",
    "DefectComment",
    "DefectHistory",
    "DefectRunLink",
    "EmployeeCache",
    "Environment",
    "ExecutionJob",
    "ImportJob",
    "InboxEvent",
    "KeyCounter",
    "OutboxMessage",
    "PlanningItemCache",
    "RunResult",
    "RunSchedule",
    "StepResult",
    "TestCase",
    "TestCaseTemplate",
    "TestCaseVersion",
    "TestPlan",
    "TestPlanCase",
    "TestRun",
    "TestStep",
    "TestSuite",
    "TestSuiteCase",
    "TrackerPollState",
    "TrackerStatusMapping",
]

"""Значения перечислений из 120. Совпадают с CHECK в миграциях и enum в OpenAPI."""

from enum import StrEnum


class CaseStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTUAL = "ACTUAL"
    NEEDS_UPDATE = "NEEDS_UPDATE"
    ARCHIVED = "ARCHIVED"


class SuiteKind(StrEnum):
    MANUAL = "MANUAL"
    FILTER = "FILTER"


class SuiteStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class SuitePurpose(StrEnum):
    GENERAL = "GENERAL"
    SMOKE = "SMOKE"
    ACCEPTANCE = "ACCEPTANCE"


class PlanScope(StrEnum):
    RELEASE = "RELEASE"
    ITERATION = "ITERATION"
    PROJECT = "PROJECT"
    MODULE = "MODULE"


class PlanStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class RunStatus(StrEnum):
    CREATED = "CREATED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"


class RunTrigger(StrEnum):
    MANUAL = "MANUAL"
    SCHEDULE = "SCHEDULE"
    CI = "CI"


class Verdict(StrEnum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class ResultStatus(StrEnum):
    NOT_RUN = "NOT_RUN"
    PASSED = "PASSED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"


class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"


class DefectOrigin(StrEnum):
    AUTO = "AUTO"
    MANUAL = "MANUAL"


class DefectStatus(StrEnum):
    NEW = "NEW"
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    FIXED = "FIXED"
    READY_FOR_TEST = "READY_FOR_TEST"
    CLOSED = "CLOSED"
    REOPENED = "REOPENED"


# Статусы разработки принадлежат Task Tracker (ADR-008).
TRACKER_OWNED_STATUSES = (DefectStatus.OPEN, DefectStatus.IN_PROGRESS, DefectStatus.FIXED)


class TrackerSyncState(StrEnum):
    PENDING = "PENDING"
    SYNCED = "SYNCED"
    FAILED = "FAILED"


class ChangeSource(StrEnum):
    QA = "QA"
    TRACKER = "TRACKER"
    SYSTEM = "SYSTEM"


class Severity(StrEnum):
    BLOCKER = "BLOCKER"
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"
    TRIVIAL = "TRIVIAL"


class AttachmentOwner(StrEnum):
    CASE = "CASE"
    STEP = "STEP"
    RUN_RESULT = "RUN_RESULT"
    DEFECT = "DEFECT"


class ClassifierKind(StrEnum):
    SEVERITY = "SEVERITY"
    PRIORITY = "PRIORITY"
    CASE_TYPE = "CASE_TYPE"


class PlanningItemType(StrEnum):
    RELEASE = "RELEASE"
    MILESTONE = "MILESTONE"
    EPIC = "EPIC"
    FEATURE = "FEATURE"


class CacheQuality(StrEnum):
    FULL = "FULL"
    PARTIAL = "PARTIAL"


class PollStream(StrEnum):
    WORK_ITEMS = "work-items"
    COMMENTS = "comments"


class OutboxKind(StrEnum):
    KAFKA_EVENT = "KAFKA_EVENT"
    TRACKER_BUG = "TRACKER_BUG"


class InboxStatus(StrEnum):
    APPLIED = "APPLIED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


class ImportStatus(StrEnum):
    VALIDATED = "VALIDATED"
    APPLIED = "APPLIED"
    REJECTED = "REJECTED"

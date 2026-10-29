import uuid

from pydantic import Field

from app.cases.schemas import CaseFilter
from app.models.enums import SuiteKind, SuitePurpose, SuiteStatus
from app.schemas import ApiModel, NonEmptyStr


class SuiteInput(ApiModel):
    name: NonEmptyStr
    kind: SuiteKind
    purpose: SuitePurpose | None = Field(
        None, description="При создании по умолчанию GENERAL; после создания не меняется"
    )
    filter: CaseFilter | None = Field(None, description="Условие отбора; только для FILTER")
    case_ids: list[uuid.UUID] | None = Field(None, description="Полный состав; только для MANUAL")


class Suite(ApiModel):
    id: uuid.UUID
    name: str
    kind: SuiteKind
    purpose: SuitePurpose
    status: SuiteStatus
    owner: str
    filter: CaseFilter | None
    case_ids: list[uuid.UUID] = Field([], description="Состав ручного набора")
    case_count: int = Field(0, description="Сколько кейсов отбирает набор сейчас, без архивных")

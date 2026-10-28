from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_session

router = APIRouter(tags=["health"])


@router.get("/livez")
def livez() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/readyz")
def readyz(session: Session = Depends(get_session)) -> dict[str, str]:
    # Недоступная БД даёт OperationalError, обработчик отвечает 503 DATABASE_UNAVAILABLE.
    session.execute(text("SELECT 1"))
    return {"status": "ready"}

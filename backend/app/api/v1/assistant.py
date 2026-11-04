from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, DbDep
from app.assistant import engine, llm
from app.core.config import get_settings

router = APIRouter(prefix="/assistant", tags=["assistant"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


@router.get("/status")
def status():
    return llm.status(get_settings())


@router.post("/chat")
def chat(payload: ChatRequest, db: DbDep, user: CurrentUser):
    return engine.respond(db, payload.message.strip(), user.id)

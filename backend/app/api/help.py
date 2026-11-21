"""In-app help: answers "how do I…" questions about Heimdall itself (not about content).

The question is redacted before the AI call (decision 16), wrapped in <content> tags
(decision 26), and goes through `LLMClient.json` like every other model call (decision 22),
using Groq's small help model first. Only the overview, the asker's role and the page they
are on are sent, which keeps each call small.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.ratelimit import limited
from app.help.guide import context_for
from app.llm import LLMClient, get_help_client
from app.llm.errors import LLMUnavailableError
from app.llm.prompts import HELP_SYSTEM, help_prompt
from app.models.llm import HelpAnswer
from app.models.users import CurrentUser
from app.processing.redaction import redact

router = APIRouter(tags=["help"])

MAX_HISTORY = 6  # earlier turns sent with a question


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    text: str = Field(max_length=2000)


class HelpQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=600)
    path: str = Field(default="/", max_length=200)
    history: list[Turn] = Field(default_factory=list, max_length=20)


class HelpReply(BaseModel):
    answer: str


def help_client() -> LLMClient:
    return get_help_client()


HelpLLM = Annotated[LLMClient, Depends(help_client)]
Asker = Annotated[CurrentUser, Depends(limited("help", 30))]


def _clean(text: str) -> str:
    return redact(text).text


@router.post("/help/chat", response_model=HelpReply)
def chat(body: HelpQuestion, user: Asker, client: HelpLLM) -> HelpReply:
    history = [(t.role, _clean(t.text)) for t in body.history[-MAX_HISTORY:]]
    prompt = help_prompt(context_for(user.role, body.path), history, _clean(body.question))
    try:
        out = client.json(HelpAnswer, HELP_SYSTEM, prompt, purpose="help", brand_id=user.brand_id)
    except LLMUnavailableError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The help assistant is busy right now. Please try again in a minute.",
        ) from exc
    return HelpReply(answer=out.answer.strip())

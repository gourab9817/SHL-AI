import asyncio

from fastapi import FastAPI

from app.config import get_settings
from app.schemas import ChatRequest, ChatResponse


app = FastAPI(
    title="SHL Conversational Assessment Recommender",
    version="0.1.0",
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


async def run_chat_shell(request: ChatRequest) -> ChatResponse:
    latest_user_message = next(
        message.content for message in reversed(request.messages) if message.role == "user"
    )
    _ = latest_user_message
    return ChatResponse(
        reply=(
            "I can help recommend SHL assessments. I need one more detail before "
            "shortlisting: what role or job family are you hiring for?"
        ),
        recommendations=[],
        end_of_conversation=False,
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    settings = get_settings()
    try:
        return await asyncio.wait_for(
            run_chat_shell(request),
            timeout=settings.chat_timeout_seconds,
        )
    except TimeoutError:
        return ChatResponse(
            reply=(
                "I could not complete the SHL assessment recommendation within the "
                "time limit. Please try again with the role, seniority, skills, and "
                "language requirements."
            ),
            recommendations=[],
            end_of_conversation=False,
        )

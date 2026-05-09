import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.catalog import load_catalog
from app.config import get_settings
from app.conversation import ConversationContextExtractor
from app.logging_config import configure_logging
from app.retrieval import CatalogRetriever
from app.schemas import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    configure_logging()
    settings = get_settings()
    logger.info("Starting SHL recommender API")
    fastapi_app.state.catalog_index = load_catalog(settings.catalog_path)
    fastapi_app.state.catalog_retriever = CatalogRetriever(fastapi_app.state.catalog_index)
    fastapi_app.state.context_extractor = ConversationContextExtractor(fastapi_app.state.catalog_index)
    logger.info("Catalog is ready with %s products", len(fastapi_app.state.catalog_index.products))

    try:
        yield
    finally:
        logger.info("Stopping SHL recommender API")


app = FastAPI(
    title="SHL Conversational Assessment Recommender",
    version="0.1.0",
    lifespan=lifespan,
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
        logger.warning("Chat request exceeded %s second timeout", settings.chat_timeout_seconds)
        return ChatResponse(
            reply=(
                "I could not complete the SHL assessment recommendation within the "
                "time limit. Please try again with the role, seniority, skills, and "
                "language requirements."
            ),
            recommendations=[],
            end_of_conversation=False,
        )

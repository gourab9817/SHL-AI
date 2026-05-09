import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.catalog import load_catalog
from app.config import get_settings
from app.conversation import ConversationContextExtractor
from app.guardrails import GuardrailService
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
    fastapi_app.state.guardrail_service = GuardrailService()
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


def ensure_runtime_services(fastapi_app: FastAPI) -> None:
    """Lazily initialize services if a test/runtime bypasses the ASGI lifespan."""
    if hasattr(fastapi_app.state, "guardrail_service"):
        return

    logger.warning("Runtime services were not initialized by lifespan; loading lazily")
    settings = get_settings()
    fastapi_app.state.catalog_index = load_catalog(settings.catalog_path)
    fastapi_app.state.catalog_retriever = CatalogRetriever(fastapi_app.state.catalog_index)
    fastapi_app.state.context_extractor = ConversationContextExtractor(fastapi_app.state.catalog_index)
    fastapi_app.state.guardrail_service = GuardrailService()


async def run_chat_shell(request: ChatRequest) -> ChatResponse:
    ensure_runtime_services(app)
    context = app.state.context_extractor.extract(request.messages)
    guardrail_decision = app.state.guardrail_service.evaluate(context)
    if not guardrail_decision.is_allowed:
        return ChatResponse(
            reply=guardrail_decision.reply or "I can only help with SHL assessment selection.",
            recommendations=[],
            end_of_conversation=False,
        )

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

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.agent import AssessmentAgent
from app.agent.responder import DeterministicResponder
from app.catalog import load_catalog
from app.config import get_settings
from app.conversation import ConversationContextExtractor
from app.guardrails import GuardrailService
from app.llm import GroqClient, LLMGenerator
from app.logging_config import configure_logging, RequestLoggingMiddleware
from app.retrieval import CatalogRetriever
from app.schemas import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)


def _build_llm_generator(
    settings,
    catalog_index,
    responder: DeterministicResponder,
) -> LLMGenerator:
    client = GroqClient(settings)
    return LLMGenerator(client=client, catalog=catalog_index, responder=responder)


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    configure_logging()
    settings = get_settings()
    logger.info("Starting SHL recommender API")
    fastapi_app.state.catalog_index = load_catalog(settings.catalog_path)
    fastapi_app.state.catalog_retriever = CatalogRetriever(fastapi_app.state.catalog_index)
    fastapi_app.state.context_extractor = ConversationContextExtractor(fastapi_app.state.catalog_index)
    fastapi_app.state.guardrail_service = GuardrailService()
    responder = DeterministicResponder()
    fastapi_app.state.llm_generator = _build_llm_generator(
        settings, fastapi_app.state.catalog_index, responder
    )
    fastapi_app.state.assessment_agent = AssessmentAgent(
        catalog=fastapi_app.state.catalog_index,
        retriever=fastapi_app.state.catalog_retriever,
        context_extractor=fastapi_app.state.context_extractor,
        guardrail_service=fastapi_app.state.guardrail_service,
        llm_generator=fastapi_app.state.llm_generator,
    )
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

app.add_middleware(RequestLoggingMiddleware)


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
    responder = DeterministicResponder()
    fastapi_app.state.llm_generator = _build_llm_generator(
        settings, fastapi_app.state.catalog_index, responder
    )
    fastapi_app.state.assessment_agent = AssessmentAgent(
        catalog=fastapi_app.state.catalog_index,
        retriever=fastapi_app.state.catalog_retriever,
        context_extractor=fastapi_app.state.context_extractor,
        guardrail_service=fastapi_app.state.guardrail_service,
        llm_generator=fastapi_app.state.llm_generator,
    )


async def run_chat_shell(request: ChatRequest) -> ChatResponse:
    ensure_runtime_services(app)
    return await app.state.assessment_agent.chat(request)


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

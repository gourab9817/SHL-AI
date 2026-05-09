from typing import Literal, NotRequired, TypedDict

from app.catalog import CatalogProduct
from app.conversation import ConversationContext
from app.guardrails import GuardrailDecision
from app.retrieval import RetrievalResult
from app.schemas import ChatResponse, Message


AgentIntent = Literal["clarify", "recommend", "refine", "compare", "finalize", "refuse"]


class AgentState(TypedDict):
    messages: list[Message]
    context: NotRequired[ConversationContext]
    guardrail_decision: NotRequired[GuardrailDecision]
    intent: NotRequired[AgentIntent]
    retrieval_query: NotRequired[str]
    retrieved_results: NotRequired[list[RetrievalResult]]
    shortlist: NotRequired[list[CatalogProduct]]
    shortlist_reply: NotRequired[str]
    response: NotRequired[ChatResponse]

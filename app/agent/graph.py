import logging

from langgraph.graph import END, StateGraph

from app.agent.planner import ShortlistPlanner
from app.agent.responder import DeterministicResponder
from app.agent.state import AgentIntent, AgentState
from app.catalog import CatalogIndex
from app.conversation import ConversationContext, ConversationContextExtractor
from app.guardrails import GuardrailService
from app.llm import LLMGenerator
from app.retrieval import CatalogRetriever
from app.schemas import ChatRequest, ChatResponse
from app.verification import ResponseVerifier

logger = logging.getLogger(__name__)


class AssessmentAgent:
    """LangGraph orchestration for SHL assessment recommendation behavior."""

    def __init__(
        self,
        *,
        catalog: CatalogIndex,
        retriever: CatalogRetriever,
        context_extractor: ConversationContextExtractor,
        guardrail_service: GuardrailService,
        llm_generator: LLMGenerator | None = None,
    ) -> None:
        self.catalog = catalog
        self.retriever = retriever
        self.context_extractor = context_extractor
        self.guardrail_service = guardrail_service
        self.planner = ShortlistPlanner(catalog, retriever)
        self.responder = DeterministicResponder()
        self.llm_generator = llm_generator
        self.verifier = ResponseVerifier(catalog)
        self._graph = self._build_graph()
        logger.info(
            "Assessment agent graph initialized llm=%s",
            "enabled" if llm_generator is not None else "disabled (deterministic fallback)",
        )

    async def chat(self, request: ChatRequest) -> ChatResponse:
        final_state = await self._graph.ainvoke({"messages": request.messages})
        response = final_state.get("response")
        if response is None:
            logger.error("Agent graph completed without a response")
            return ChatResponse(
                reply="I could not complete the SHL assessment workflow. Please try again with the role details.",
                recommendations=[],
                end_of_conversation=False,
            )
        return response

    def _build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("reconstruct_context", self._reconstruct_context)
        graph.add_node("apply_guardrails", self._apply_guardrails)
        graph.add_node("classify_intent", self._classify_intent)
        graph.add_node("retrieve_catalog", self._retrieve_catalog)
        graph.add_node("plan_shortlist", self._plan_shortlist)
        graph.add_node("respond_refusal", self._respond_refusal)
        graph.add_node("respond_clarify", self._respond_clarify)
        graph.add_node("respond_compare", self._respond_compare)
        graph.add_node("respond_finalize", self._respond_finalize)
        graph.add_node("respond_shortlist", self._respond_shortlist)
        graph.add_node("verify_response", self._verify_response)

        graph.set_entry_point("reconstruct_context")
        graph.add_edge("reconstruct_context", "apply_guardrails")
        graph.add_conditional_edges(
            "apply_guardrails",
            self._route_after_guardrails,
            {"refuse": "respond_refusal", "continue": "classify_intent"},
        )
        graph.add_conditional_edges(
            "classify_intent",
            self._route_after_intent,
            {
                "clarify": "respond_clarify",
                "compare": "respond_compare",
                "finalize": "respond_finalize",
                "recommend": "retrieve_catalog",
                "refine": "retrieve_catalog",
            },
        )
        graph.add_edge("retrieve_catalog", "plan_shortlist")
        graph.add_edge("plan_shortlist", "respond_shortlist")
        graph.add_edge("respond_refusal", "verify_response")
        graph.add_edge("respond_clarify", "verify_response")
        graph.add_edge("respond_compare", "verify_response")
        graph.add_edge("respond_finalize", "verify_response")
        graph.add_edge("respond_shortlist", "verify_response")
        graph.add_edge("verify_response", END)
        return graph.compile()

    def _reconstruct_context(self, state: AgentState) -> AgentState:
        return {"context": self.context_extractor.extract(state["messages"])}

    def _apply_guardrails(self, state: AgentState) -> AgentState:
        return {"guardrail_decision": self.guardrail_service.evaluate(state["context"])}

    def _classify_intent(self, state: AgentState) -> AgentState:
        intent = self._determine_intent(state["context"])
        logger.info("Classified agent intent as %s", intent)
        return {"intent": intent}

    def _retrieve_catalog(self, state: AgentState) -> AgentState:
        query = self.planner.build_query(state["context"])
        return {
            "retrieval_query": query,
            "retrieved_results": self.retriever.search(query, limit=15),
        }

    async def _plan_shortlist(self, state: AgentState) -> AgentState:
        intent = state["intent"]
        context = state["context"]
        results = state.get("retrieved_results", [])

        if self.llm_generator is not None:
            candidates = [result.product for result in results]
            llm_shortlist, llm_reply = await self.llm_generator.select_shortlist_with_reply(
                context, candidates, intent  # type: ignore[arg-type]
            )
            if llm_shortlist:
                logger.info("Using LLM shortlist (%d products)", len(llm_shortlist))
                return {"shortlist": llm_shortlist, "shortlist_reply": llm_reply}
            logger.info("LLM shortlist empty; falling back to deterministic planner")

        if intent == "refine":
            shortlist = self.planner.plan_refinement(context, results)
        else:
            shortlist = self.planner.plan_recommendation(context, results)
        return {"shortlist": shortlist, "shortlist_reply": ""}

    def _respond_refusal(self, state: AgentState) -> AgentState:
        decision = state["guardrail_decision"]
        return {
            "intent": "refuse",
            "response": ChatResponse(
                reply=decision.reply or "I can only help with SHL assessment selection.",
                recommendations=[],
                end_of_conversation=False,
            ),
        }

    async def _respond_clarify(self, state: AgentState) -> AgentState:
        context = state["context"]
        if self.llm_generator is not None:
            reply = await self.llm_generator.generate_clarify_reply(context)
        else:
            reply = self.responder.clarify(context)
        return {
            "response": ChatResponse(
                reply=reply,
                recommendations=[],
                end_of_conversation=False,
            )
        }

    async def _respond_compare(self, state: AgentState) -> AgentState:
        context = state["context"]
        products = context.comparison_products
        if self.llm_generator is not None:
            reply = await self.llm_generator.generate_compare_reply(context, products)
        else:
            reply = self.responder.compare(products)
        return {
            "response": ChatResponse(
                reply=reply,
                recommendations=[],
                end_of_conversation=False,
            )
        }

    def _respond_finalize(self, state: AgentState) -> AgentState:
        products = self.planner.plan_finalization(state["context"])
        return {
            "response": self.planner.build_response(
                reply=self.responder.finalize(products),
                products=products,
                end_of_conversation=bool(products),
            )
        }

    def _respond_shortlist(self, state: AgentState) -> AgentState:
        products = state.get("shortlist", [])
        llm_reply = state.get("shortlist_reply", "")
        if llm_reply:
            reply = llm_reply
        elif state["intent"] == "refine":
            reply = self.responder.refine(products)
        else:
            reply = self.responder.recommend(products)
        return {
            "response": self.planner.build_response(
                reply=reply,
                products=products,
                end_of_conversation=False,
            )
        }

    def _verify_response(self, state: AgentState) -> AgentState:
        response = state.get("response")
        if response is None:
            logger.error("verify_response node received state with no response — nothing to verify")
            return {}
        intent = state.get("intent", "recommend")
        verified = self.verifier.verify(response, intent)
        return {"response": verified}

    def _route_after_guardrails(self, state: AgentState) -> str:
        return "continue" if state["guardrail_decision"].is_allowed else "refuse"

    def _route_after_intent(self, state: AgentState) -> str:
        return state["intent"]

    def _determine_intent(self, context: ConversationContext) -> AgentIntent:
        actions = context.actions
        constraints = context.constraints
        if actions.is_vague_request:
            return "clarify"

        has_context = bool(
            constraints.role_text
            or constraints.skills
            or constraints.assessment_types
            or actions.has_job_description
            or context.previous_recommendations
        )

        if actions.confirms_final and context.previous_recommendations:
            return "finalize"
        if actions.asks_comparison:
            return "compare"
        if actions.requested_additions or actions.requested_removals or actions.requested_replacements or actions.wants_shorter:
            return "refine"
        if context.remaining_turn_budget <= 2 and has_context:
            return "recommend"
        if actions.asks_recommendation and not has_context:
            return "clarify"
        if has_context:
            return "recommend"
        return "clarify"

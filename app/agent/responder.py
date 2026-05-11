from app.catalog import CatalogProduct
from app.conversation import ConversationContext
from app.retrieval.tokenizer import normalize_text, tokenize


class DeterministicResponder:
    """Builds safe, catalog-grounded replies before LLM phrasing is introduced."""

    def clarify(self, context: ConversationContext) -> str:
        if context.actions.is_greeting:
            return (
                "Hi! I'm the SHL Assessment Recommender. "
                "Tell me about the role you're hiring for — job title, seniority level, "
                "and key skills — and I'll shortlist the right SHL assessments for you."
            )
        if context.actions.is_identity_question:
            return (
                "I'm an AI consultant that recommends SHL psychometric assessments for hiring. "
                "Share the role, seniority, and core skills you need to evaluate, "
                "and I'll shortlist catalog-backed options tailored to your hiring context."
            )
        if context.actions.is_vague_request:
            return "I can help recommend SHL assessments. What role or job family are you hiring for?"
        if self._needs_skill_clarification(context):
            return "What are the core skills or technologies this role needs, such as Java, AWS, Docker, SQL, or customer-facing capabilities?"
        if context.constraints.role_text and not context.constraints.seniority:
            return "What seniority level or experience range should the assessment battery target?"
        if context.constraints.role_text and not context.constraints.language:
            return "What language or region should the assessment support?"
        return "What role, seniority, core skills, and assessment purpose should I optimize for?"

    def direct_guidance(self, context: ConversationContext) -> str:
        if context.actions.is_greeting:
            return (
                "I recommend SHL assessments for hiring. Share the role, seniority level, and key skills, "
                "and I will return a catalog-backed shortlist."
            )
        if context.actions.is_identity_question:
            return (
                "I recommend SHL psychometric assessments for hiring. "
                "Provide the role, seniority, and core skills for a direct shortlist."
            )
        if context.actions.is_vague_request or not context.constraints.role_text:
            return "Provide the job role, seniority, and core skills, and I will return a direct SHL shortlist."
        if self._needs_skill_clarification(context):
            return (
                "Provide the core skills or technologies for this role, such as Java, AWS, Docker, SQL, "
                "or customer-facing capabilities, and I will return a tighter SHL shortlist."
            )
        if context.constraints.role_text and not context.constraints.seniority:
            return "Provide the target seniority or experience range, and I will return a sharper SHL shortlist."
        return "Provide the missing role details and I will return a direct SHL shortlist."

    def recommend(self, products: list[CatalogProduct]) -> str:
        if not products:
            return (
                "I could not find a strong SHL catalog match from the current details. "
                "Please share the role, seniority, skills, and language requirements."
            )
        return (
            f"Here are {len(products)} SHL catalog assessments that best match the current hiring context. "
            "You can add more skills or refine the job description, and I'll update the shortlist."
        )

    def refine(self, products: list[CatalogProduct]) -> str:
        if not products:
            return "I updated the shortlist, but no catalog-backed recommendations remain after the requested changes."
        return (
            f"Updated the shortlist based on your latest constraints. It now contains {len(products)} SHL item(s). "
            "You can keep refining it by adding skills, removing items, or tightening the job description."
        )

    def compare(self, products: tuple[CatalogProduct, ...]) -> str:
        if len(products) < 2:
            return "Which SHL assessments would you like me to compare?"

        product_lines = []
        for product in products[:4]:
            keys = ", ".join(product.keys) if product.keys else "No catalog category listed"
            duration = product.duration or "duration not listed"
            product_lines.append(f"{product.name}: {keys}; {duration}.")
        return "Catalog comparison: " + " ".join(product_lines)

    def finalize(self, products: list[CatalogProduct]) -> str:
        if not products:
            return "Confirmed. I do not have a prior catalog-backed shortlist to repeat yet."
        return (
            f"Confirmed. Final SHL shortlist contains {len(products)} item(s). "
            "You can still add more skills or adjust the job description if the role changes."
        )

    def needs_skill_clarification(self, context: ConversationContext) -> bool:
        return self._needs_skill_clarification(context)

    def has_actionable_recommendation_context(self, context: ConversationContext) -> bool:
        if context.actions.is_vague_request:
            return False
        if context.previous_recommendations:
            return True
        if context.constraints.skills or context.constraints.assessment_types or context.actions.has_job_description:
            return True

        role_text = context.constraints.role_text
        if not role_text:
            return False

        if context.constraints.seniority:
            return True

        normalized_role = normalize_text(role_text)
        role_tokens = set(tokenize(normalized_role, keep_stopwords=True))
        informative_tokens = role_tokens - self._GENERIC_ROLE_TOKENS
        return bool(informative_tokens)

    _GENERIC_ROLE_TOKENS = frozenset(
        {
            "employee",
            "employees",
            "dev",
            "developer",
            "developers",
            "engineer",
            "engineers",
            "manager",
            "managers",
            "analyst",
            "analysts",
            "assistant",
            "assistants",
            "staff",
            "operator",
            "operators",
            "assessment",
            "assessments",
            "test",
            "tests",
            "solution",
            "solutions",
            "role",
            "position",
            "hire",
            "hiring",
            "senior",
            "junior",
            "graduate",
            "entry",
            "level",
            "mid",
            "principal",
            "lead",
            "leadership",
        }
    )

    def _needs_skill_clarification(self, context: ConversationContext) -> bool:
        if context.previous_recommendations:
            return False
        if context.constraints.skills or context.constraints.assessment_types or context.actions.has_job_description:
            return False

        role_text = context.constraints.role_text
        if not role_text:
            return False

        normalized_role = normalize_text(role_text)
        role_tokens = set(tokenize(normalized_role, keep_stopwords=True))
        informative_tokens = role_tokens - self._GENERIC_ROLE_TOKENS

        if not informative_tokens:
            return True

        technical_markers = {"dev", "developer", "engineer", "software", "backend", "frontend", "fullstack"}
        return bool(role_tokens & technical_markers) and not context.constraints.skills

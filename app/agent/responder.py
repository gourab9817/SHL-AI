from app.catalog import CatalogProduct
from app.conversation import ConversationContext


class DeterministicResponder:
    """Builds safe, catalog-grounded replies before LLM phrasing is introduced."""

    def clarify(self, context: ConversationContext) -> str:
        if context.actions.is_vague_request:
            return "I can help recommend SHL assessments. What role or job family are you hiring for?"
        if context.constraints.role_text and not context.constraints.seniority:
            return "What seniority level or experience range should the assessment battery target?"
        if context.constraints.role_text and not context.constraints.language:
            return "What language or region should the assessment support?"
        return "What role, seniority, core skills, and assessment purpose should I optimize for?"

    def recommend(self, products: list[CatalogProduct]) -> str:
        if not products:
            return (
                "I could not find a strong SHL catalog match from the current details. "
                "Please share the role, seniority, skills, and language requirements."
            )
        return f"Here are {len(products)} SHL catalog assessments that best match the current hiring context."

    def refine(self, products: list[CatalogProduct]) -> str:
        if not products:
            return "I updated the shortlist, but no catalog-backed recommendations remain after the requested changes."
        return f"Updated the shortlist based on your latest constraints. It now contains {len(products)} SHL item(s)."

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
        return f"Confirmed. Final SHL shortlist contains {len(products)} item(s)."

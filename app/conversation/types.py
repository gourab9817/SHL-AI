from dataclasses import dataclass

from app.catalog import CatalogProduct


@dataclass(frozen=True)
class ConversationConstraints:
    role_text: str | None = None
    seniority: str | None = None
    skills: tuple[str, ...] = ()
    language: str | None = None
    region_or_accent: str | None = None
    use_case: str | None = None
    volume: int | None = None
    assessment_types: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConversationActions:
    requested_additions: tuple[str, ...] = ()
    requested_removals: tuple[str, ...] = ()
    requested_replacements: tuple[str, ...] = ()
    wants_shorter: bool = False
    says_no_preference: bool = False
    confirms_final: bool = False
    asks_comparison: bool = False
    asks_recommendation: bool = False
    is_vague_request: bool = False
    has_job_description: bool = False


@dataclass(frozen=True)
class ConversationContext:
    latest_user_message: str
    user_turn_count: int
    assistant_turn_count: int
    total_turn_count: int
    constraints: ConversationConstraints
    actions: ConversationActions
    mentioned_products: tuple[CatalogProduct, ...]
    previous_recommendations: tuple[CatalogProduct, ...]
    comparison_products: tuple[CatalogProduct, ...]

    @property
    def remaining_turn_budget(self) -> int:
        return max(0, 8 - self.total_turn_count)

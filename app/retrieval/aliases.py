from dataclasses import dataclass


@dataclass(frozen=True)
class AliasRule:
    """A deterministic retrieval hint for common recruiter vocabulary."""

    phrases: tuple[str, ...]
    product_names: tuple[str, ...]
    boost: float
    reason: str
    expansion_terms: tuple[str, ...] = ()


ALIAS_RULES: tuple[AliasRule, ...] = (
    AliasRule(
        phrases=("opq", "personality", "behavioural", "behavioral", "behavioral fit", "behavioural fit"),
        product_names=("Occupational Personality Questionnaire OPQ32r",),
        boost=90.0,
        reason="personality/OPQ alias",
        expansion_terms=("workplace behavior personality opq32r",),
    ),
    AliasRule(
        phrases=("senior leadership", "cxos", "cxo", "director level", "executive selection"),
        product_names=(
            "Occupational Personality Questionnaire OPQ32r",
            "OPQ Universal Competency Report 2.0",
            "OPQ Leadership Report",
        ),
        boost=80.0,
        reason="leadership assessment pattern",
    ),
    AliasRule(
        phrases=("cognitive", "reasoning", "general ability", "aptitude", "g plus", "g+"),
        product_names=("SHL Verify Interactive G+",),
        boost=85.0,
        reason="cognitive reasoning alias",
        expansion_terms=("verify interactive general ability reasoning",),
    ),
    AliasRule(
        phrases=("senior dev", "senior developer", "software developer", "software engineer"),
        product_names=(
            "Smart Interview Live Coding",
            "SHL Verify Interactive G+",
            "Occupational Personality Questionnaire OPQ32r",
        ),
        boost=70.0,
        reason="generic senior software role pattern",
        expansion_terms=("software development coding engineering technical interview",),
    ),
    AliasRule(
        phrases=("numerical", "numerical reasoning"),
        product_names=("SHL Verify Interactive – Numerical Reasoning",),
        boost=95.0,
        reason="numerical reasoning alias",
    ),
    AliasRule(
        phrases=("sjt", "situational judgement", "situational judgment", "graduate decision making"),
        product_names=("Graduate Scenarios",),
        boost=95.0,
        reason="graduate situational judgment alias",
    ),
    AliasRule(
        phrases=("rust",),
        product_names=(
            "Smart Interview Live Coding",
            "Linux Programming (General)",
            "Networking and Implementation (New)",
        ),
        boost=85.0,
        reason="no Rust-specific test; adjacent technical assessment",
    ),
    AliasRule(
        phrases=("contact center", "contact centre", "inbound calls", "call center", "customer service focus"),
        product_names=(
            "SVAR - Spoken English (US) (New)",
            "Contact Center Call Simulation (New)",
            "Entry Level Customer Serv-Retail & Contact Center",
            "Customer Service Phone Simulation",
        ),
        boost=85.0,
        reason="contact center assessment pattern",
    ),
    AliasRule(
        phrases=("spoken english", "english us", "us accent", "u.s. accent"),
        product_names=("SVAR - Spoken English (US) (New)",),
        boost=90.0,
        reason="spoken English US language pattern",
    ),
    AliasRule(
        phrases=("financial analyst", "finance knowledge", "financial analysts"),
        product_names=(
            "SHL Verify Interactive – Numerical Reasoning",
            "Financial Accounting (New)",
            "Basic Statistics (New)",
            "Occupational Personality Questionnaire OPQ32r",
        ),
        boost=75.0,
        reason="graduate finance analyst pattern",
    ),
    AliasRule(
        phrases=("sales organization", "sales organisation", "sales audit", "reskill", "re-skill", "talent audit"),
        product_names=(
            "Global Skills Assessment",
            "Global Skills Development Report",
            "Occupational Personality Questionnaire OPQ32r",
            "OPQ MQ Sales Report",
            "Sales Transformation 2.0 - Individual Contributor",
        ),
        boost=90.0,
        reason="sales reskilling audit pattern",
    ),
    AliasRule(
        phrases=("plant operator", "chemical facility", "safety", "procedure compliance", "reliability"),
        product_names=(
            "Dependability and Safety Instrument (DSI)",
            "Manufac. & Indust. - Safety & Dependability 8.0",
            "Workplace Health and Safety (New)",
        ),
        boost=80.0,
        reason="safety-critical industrial role pattern",
    ),
    AliasRule(
        phrases=("healthcare admin", "patient records", "hipaa", "medical terminology"),
        product_names=(
            "HIPAA (Security)",
            "Medical Terminology (New)",
            "Microsoft Word 365 - Essentials (New)",
            "Dependability and Safety Instrument (DSI)",
            "Occupational Personality Questionnaire OPQ32r",
        ),
        boost=85.0,
        reason="healthcare admin pattern",
    ),
    AliasRule(
        phrases=("spanish", "south texas", "latin american spanish"),
        product_names=(
            "Dependability and Safety Instrument (DSI)",
            "Occupational Personality Questionnaire OPQ32r",
        ),
        boost=35.0,
        reason="Spanish language support pattern",
    ),
    AliasRule(
        phrases=("admin assistant", "administrative assistant", "excel and word", "word daily", "excel daily"),
        product_names=(
            "MS Excel (New)",
            "MS Word (New)",
            "Microsoft Excel 365 (New)",
            "Microsoft Word 365 (New)",
            "Microsoft Word 365 - Essentials (New)",
            "Occupational Personality Questionnaire OPQ32r",
        ),
        boost=85.0,
        reason="office administration assessment pattern",
    ),
    AliasRule(
        phrases=("full stack", "backend", "microservice", "java spring sql", "core java"),
        product_names=(
            "Core Java (Advanced Level) (New)",
            "Spring (New)",
            "RESTful Web Services (New)",
            "SQL (New)",
            "SHL Verify Interactive G+",
            "Occupational Personality Questionnaire OPQ32r",
        ),
        boost=65.0,
        reason="senior software engineering pattern",
    ),
    AliasRule(
        phrases=("aws", "cloud native", "cloud-native"),
        product_names=("Amazon Web Services (AWS) Development (New)",),
        boost=95.0,
        reason="AWS skill alias",
    ),
    AliasRule(
        phrases=("docker", "container", "containers"),
        product_names=("Docker (New)",),
        boost=95.0,
        reason="Docker skill alias",
    ),
    AliasRule(
        phrases=("rest api", "restful", "api design"),
        product_names=("RESTful Web Services (New)",),
        boost=80.0,
        reason="REST API skill alias",
    ),
)

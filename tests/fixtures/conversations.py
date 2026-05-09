"""Conversation fixtures derived from the C1-C10 public sample conversations.

Each fixture captures:
- The full message history up to and including the final user turn.
- The expected product names from the sample's final recommendation table.
- A minimum Recall@10 threshold that must hold in deterministic (no-LLM) mode.

Assistant messages include product names in plain text so the stateless extractor
can recover previous_recommendations without markdown-table parsing.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ConversationFixture:
    name: str
    messages: tuple[tuple[str, str], ...]
    expected_names: frozenset[str]
    min_recall: float = 0.4
    description: str = ""


# ------------------------------------------------------------------ #
# C1 — Senior leadership selection (OPQ32r + reports)                #
# ------------------------------------------------------------------ #
C1 = ConversationFixture(
    name="C1_senior_leadership",
    description="CXO/Director selection with leadership benchmark",
    messages=(
        ("user", "We need a solution for senior leadership."),
        ("assistant", "Happy to help narrow that down. Who is this meant for?"),
        ("user", "The pool consists of CXOs, director-level positions; people with more than 15 years of experience."),
        ("assistant", "For such roles, the OPQ32r is the right instrument. Is this for a newly created position, or developmental feedback for an executive already in role?"),
        ("user", "Selection — comparing candidates against a leadership benchmark."),
        ("assistant", (
            "For selection with a leadership benchmark: "
            "Occupational Personality Questionnaire OPQ32r, "
            "OPQ Universal Competency Report 2.0, "
            "OPQ Leadership Report."
        )),
        ("user", "Perfect, that's what we need."),
    ),
    expected_names=frozenset({
        "Occupational Personality Questionnaire OPQ32r",
        "OPQ Universal Competency Report 2.0",
        "OPQ Leadership Report",
    }),
    min_recall=0.6,
)

# ------------------------------------------------------------------ #
# C2 — Senior Rust / networking engineer (live coding + Verify G+)   #
# ------------------------------------------------------------------ #
C2 = ConversationFixture(
    name="C2_senior_rust_engineer",
    description="Senior Rust engineer — no Rust test; live coding + systems depth",
    messages=(
        ("user", "I'm hiring a senior Rust engineer for high-performance networking infrastructure. What assessments should I use?"),
        ("assistant", "SHL's catalog doesn't include a Rust-specific knowledge test. The closest fit: Smart Interview Live Coding, Linux Programming (General), Networking and Implementation (New)."),
        ("user", "Yes, go ahead. Should I also add a cognitive test for this level?"),
        ("assistant", (
            "Full shortlist: "
            "Smart Interview Live Coding, "
            "Linux Programming (General), "
            "Networking and Implementation (New), "
            "SHL Verify Interactive G+, "
            "Occupational Personality Questionnaire OPQ32r."
        )),
        ("user", "That works. Thanks."),
    ),
    expected_names=frozenset({
        "Smart Interview Live Coding",
        "Linux Programming (General)",
        "Networking and Implementation (New)",
        "SHL Verify Interactive G+",
        "Occupational Personality Questionnaire OPQ32r",
    }),
    min_recall=0.5,
)

# ------------------------------------------------------------------ #
# C3 — Contact centre, English USA, high volume (SVAR + simulations) #
# ------------------------------------------------------------------ #
C3 = ConversationFixture(
    name="C3_contact_centre",
    description="500 entry-level contact centre agents, US English",
    messages=(
        ("user", "We're screening 500 entry-level contact centre agents. Inbound calls, customer service focus. What should we use?"),
        ("assistant", "What language do the agents need to work in?"),
        ("user", "English."),
        ("assistant", "Great. Is the deployment US or international?"),
        ("user", "US."),
        ("assistant", (
            "Recommended: "
            "SVAR Spoken English (US) (New), "
            "Contact Center Call Simulation (New), "
            "Entry Level Customer Serv - Retail & Contact Center, "
            "Customer Service Phone Simulation."
        )),
        ("user", "Is the Contact Center Call Simulation different from the Customer Service Phone Simulation?"),
        ("assistant", "Contact Center Call Simulation (New): Simulations; 15 minutes. Customer Service Phone Simulation: Biodata & Situational Judgment, Simulations; 20 minutes. The New simulation handles high volume; the older solution suits finalist screening."),
        ("user", "Perfect — new simulation for volume, old solution for finalists. Confirmed."),
    ),
    expected_names=frozenset({
        "SVAR Spoken English (US) (New)",
        "Contact Center Call Simulation (New)",
        "Entry Level Customer Serv - Retail & Contact Center",
        "Customer Service Phone Simulation",
    }),
    min_recall=0.3,
)

# ------------------------------------------------------------------ #
# C4 — Graduate financial analysts (numerical + SJT)                 #
# ------------------------------------------------------------------ #
C4 = ConversationFixture(
    name="C4_graduate_financial_analysts",
    description="Graduate financial analysts — numerical reasoning + SJT + domain tests",
    messages=(
        ("user", "Hiring graduate financial analysts — final-year students, no work experience. We need numerical reasoning and a finance knowledge test."),
        ("assistant", (
            "Recommended: "
            "SHL Verify Interactive – Numerical Reasoning, "
            "Financial Accounting (New), "
            "Basic Statistics (New), "
            "Occupational Personality Questionnaire OPQ32r."
        )),
        ("user", "Good. Can you also add a situational judgement element — work-context decision making for graduates?"),
        ("assistant", (
            "Updated shortlist: "
            "SHL Verify Interactive – Numerical Reasoning, "
            "Financial Accounting (New), "
            "Basic Statistics (New), "
            "Graduate Scenarios, "
            "Occupational Personality Questionnaire OPQ32r."
        )),
        ("user", "That covers it. Numerical + Graduate Scenarios as first filter, domain tests for shortlisted candidates."),
    ),
    expected_names=frozenset({
        "SHL Verify Interactive – Numerical Reasoning",
        "Financial Accounting (New)",
        "Basic Statistics (New)",
        "Graduate Scenarios",
        "Occupational Personality Questionnaire OPQ32r",
    }),
    min_recall=0.4,
)

# ------------------------------------------------------------------ #
# C5 — Sales reskilling audit (GSA + OPQ + sales reports)            #
# ------------------------------------------------------------------ #
C5 = ConversationFixture(
    name="C5_sales_reskilling_audit",
    description="Annual sales talent audit and reskilling",
    messages=(
        ("user", "As part of our restructuring and annual talent audit, we need to re-skill our Sales organization. What solutions do you recommend?"),
        ("assistant", (
            "Recommended: "
            "Global Skills Assessment, "
            "Global Skills Development Report, "
            "Occupational Personality Questionnaire OPQ32r, "
            "OPQ MQ Sales Report, "
            "Sales Transformation 2.0 - Individual Contributor."
        )),
        ("user", "What's the difference between OPQ and OPQ MQ Sales Report?"),
        ("assistant", "OPQ32r is the full personality questionnaire. OPQ MQ Sales Report is a focused sales motivation report generated from OPQ32r data, showing motivators aligned to sales competencies."),
        ("user", "Clear. We'll use OPQ for everyone and add MQ only where we want motivators in the Sales Report; keeping the five solutions as our audit stack."),
    ),
    expected_names=frozenset({
        "Global Skills Assessment",
        "Global Skills Development Report",
        "Occupational Personality Questionnaire OPQ32r",
        "OPQ MQ Sales Report",
        "Sales Transformation 2.0 - Individual Contributor",
    }),
    min_recall=0.3,
)

# ------------------------------------------------------------------ #
# C6 — Plant operators, industrial safety (Safety & Dependability)   #
# ------------------------------------------------------------------ #
C6 = ConversationFixture(
    name="C6_plant_operators_safety",
    description="Plant operators — industrial safety, DSI vs Safety & Dependability 8.0",
    messages=(
        ("user", "We're hiring plant operators for a chemical facility. Safety is absolute top priority — reliability, procedure compliance, never cutting corners. What do you recommend?"),
        ("assistant", (
            "Recommended: "
            "Dependability and Safety Instrument (DSI), "
            "Manufac. & Indust. - Safety & Dependability 8.0, "
            "Workplace Health and Safety (New)."
        )),
        ("user", "What's the difference between the DSI and the Safety & Dependability 8.0?"),
        ("assistant", "DSI is a shorter personality measure focused on dependability. Safety & Dependability 8.0 is an industrial bundle with additional depth for manufacturing environments."),
        ("user", "We're industrial. The 8.0 bundle is the right fit. Confirmed."),
    ),
    expected_names=frozenset({
        "Manufac. & Indust. - Safety & Dependability 8.0",
        "Workplace Health and Safety (New)",
    }),
    min_recall=0.4,
)

# ------------------------------------------------------------------ #
# C7 — Healthcare admin, Spanish/English hybrid, HIPAA               #
# ------------------------------------------------------------------ #
C7 = ConversationFixture(
    name="C7_healthcare_admin_hipaa",
    description="Bilingual healthcare admin — South Texas, HIPAA + legal refusal",
    messages=(
        ("user", "We're hiring bilingual healthcare admin staff in South Texas — they handle patient records and need to be assessed in Spanish. HIPAA compliance is critical. What assessments work?"),
        ("assistant", (
            "Recommended: "
            "HIPAA (Security), "
            "Medical Terminology (New), "
            "Microsoft Word 365 - Essentials (New), "
            "Dependability and Safety Instrument (DSI), "
            "Occupational Personality Questionnaire OPQ32r."
        )),
        ("user", "They're functionally bilingual — English fluent for written work. Go with the hybrid."),
        ("assistant", (
            "Updated for hybrid English-assessed shortlist: "
            "HIPAA (Security), "
            "Medical Terminology (New), "
            "Microsoft Word 365 - Essentials (New), "
            "Dependability and Safety Instrument (DSI), "
            "Occupational Personality Questionnaire OPQ32r."
        )),
        ("user", "Are we legally required under HIPAA to test all staff who touch patient records? And does this SHL test satisfy that requirement?"),
        ("assistant", "I can help with SHL assessment selection, but I cannot provide legal or compliance advice about HIPAA obligations. Please consult legal counsel for that question."),
        ("user", "Understood. Keep the shortlist as-is."),
    ),
    expected_names=frozenset({
        "HIPAA (Security)",
        "Medical Terminology (New)",
        "Microsoft Word 365 - Essentials (New)",
        "Dependability and Safety Instrument (DSI)",
        "Occupational Personality Questionnaire OPQ32r",
    }),
    min_recall=0.4,
)

# ------------------------------------------------------------------ #
# C8 — Admin assistants, Excel/Word quick tests then simulations     #
# ------------------------------------------------------------------ #
C8 = ConversationFixture(
    name="C8_admin_assistants_office",
    description="Admin assistants — quick Excel/Word tests then full simulations",
    messages=(
        ("user", "I need to quickly screen admin assistants for Excel and Word daily."),
        ("assistant", (
            "Quick knowledge tests: "
            "MS Excel (New), "
            "MS Word (New), "
            "Occupational Personality Questionnaire OPQ32r."
        )),
        ("user", "In that case, I am OK with adding a simulation - we want to capture the capabilities."),
        ("assistant", (
            "Updated shortlist with simulations: "
            "Microsoft Excel 365 (New), "
            "Microsoft Word 365 (New), "
            "MS Excel (New), "
            "MS Word (New), "
            "Occupational Personality Questionnaire OPQ32r."
        )),
        ("user", "That's good."),
    ),
    expected_names=frozenset({
        "Microsoft Excel 365 (New)",
        "Microsoft Word 365 (New)",
        "MS Excel (New)",
        "MS Word (New)",
        "Occupational Personality Questionnaire OPQ32r",
    }),
    min_recall=0.4,
)

# ------------------------------------------------------------------ #
# C9 — Senior backend/full-stack JD (Java + cloud + OPQ + Verify G+) #
# ------------------------------------------------------------------ #
C9 = ConversationFixture(
    name="C9_senior_fullstack_jd",
    description="Senior Full-Stack Engineer JD — multi-turn refinement to final 7-item battery",
    messages=(
        ("user", (
            "Here's the JD for an engineer we need to fill. Can you recommend an assessment battery?\n\n"
            '"Senior Full-Stack Engineer — 5+ years across Core Java, Spring, REST API design, '
            "Angular, SQL/relational databases, AWS deployment, and Docker. Will own end-to-end "
            "microservice delivery, contribute to architectural decisions, and mentor mid-level engineers. "
            'Strong CI/CD and cloud-native experience required."'
        )),
        ("assistant", "Let me clarify: is the role backend-leaning or full-stack? And what's the seniority — Senior IC or engineering manager?"),
        ("user", "Backend-leaning. Day-one priorities are Core Java and Spring; SQL is constant. Angular is occasional — they'd review frontend PRs but not own features."),
        ("assistant", (
            "Recommended for backend-leaning senior engineer: "
            "Core Java (Advanced Level) (New), "
            "Spring (New), "
            "SQL (New), "
            "RESTful Web Services (New), "
            "SHL Verify Interactive G+, "
            "Occupational Personality Questionnaire OPQ32r."
        )),
        ("user", "Senior IC. They lead design on their own services but don't manage other engineers directly."),
        ("assistant", (
            "Confirmed Senior IC: "
            "Core Java (Advanced Level) (New), "
            "Spring (New), "
            "SQL (New), "
            "RESTful Web Services (New), "
            "SHL Verify Interactive G+, "
            "Occupational Personality Questionnaire OPQ32r."
        )),
        ("user", "Add AWS and Docker. Drop REST — the API design signal will already come through in Spring and the live interview."),
        ("assistant", (
            "Updated shortlist: "
            "Core Java (Advanced Level) (New), "
            "Spring (New), "
            "SQL (New), "
            "Amazon Web Services (AWS) Development (New), "
            "Docker (New), "
            "SHL Verify Interactive G+, "
            "Occupational Personality Questionnaire OPQ32r."
        )),
        ("user", "On Java — they'd be working on existing services, not greenfield. Is the Advanced level the right pick?"),
        ("assistant", "The Advanced level is the right pick for engineers working on complex existing services; it tests deeper patterns and legacy code comprehension rather than pure language basics."),
        ("user", "Do we really need Verify G+ on top of all the technical tests? Feels redundant."),
        ("assistant", (
            "SHL Verify Interactive G+ measures general cognitive ability — capacity for complex "
            "problem-solving and learning speed — which complements domain knowledge tests. "
            "Current shortlist: "
            "Core Java (Advanced Level) (New), "
            "Spring (New), "
            "SQL (New), "
            "Amazon Web Services (AWS) Development (New), "
            "Docker (New), "
            "SHL Verify Interactive G+, "
            "Occupational Personality Questionnaire OPQ32r."
        )),
        ("user", "Keep Verify G+. Locking it in."),
    ),
    expected_names=frozenset({
        "Core Java (Advanced Level) (New)",
        "Spring (New)",
        "SQL (New)",
        "Amazon Web Services (AWS) Development (New)",
        "Docker (New)",
        "SHL Verify Interactive G+",
        "Occupational Personality Questionnaire OPQ32r",
    }),
    min_recall=0.6,
)

# ------------------------------------------------------------------ #
# C10 — Graduate trainee battery (drop OPQ32r)                       #
# ------------------------------------------------------------------ #
C10 = ConversationFixture(
    name="C10_graduate_trainee_battery",
    description="Graduate management trainee battery — drop OPQ32r on user request",
    messages=(
        ("user", "We run a graduate management trainee scheme. We need a full battery — cognitive, personality, and situational judgement. All recent graduates."),
        ("assistant", (
            "Recommended graduate battery: "
            "SHL Verify Interactive G+, "
            "Occupational Personality Questionnaire OPQ32r, "
            "Graduate Scenarios."
        )),
        ("user", "But can you remove the OPQ32r and replace it with something shorter? Candidates complain it takes too long."),
        ("assistant", (
            "Updated shortlist without OPQ32r: "
            "SHL Verify Interactive G+, "
            "Graduate Scenarios."
        )),
        ("user", "Drop the OPQ. Final list: Verify G+ and Graduate Scenarios."),
    ),
    expected_names=frozenset({
        "SHL Verify Interactive G+",
        "Graduate Scenarios",
    }),
    min_recall=0.6,
)

# ------------------------------------------------------------------ #
# All fixtures in a single ordered list for parametrized tests        #
# ------------------------------------------------------------------ #
CONVERSATION_FIXTURES: tuple[ConversationFixture, ...] = (
    C1, C2, C3, C4, C5, C6, C7, C8, C9, C10
)

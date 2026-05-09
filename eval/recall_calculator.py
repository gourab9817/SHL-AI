#!/usr/bin/env python3
"""Calculate Recall@10 metrics for recommendation ranking quality.

Compares agent recommendations against known-good products for each sample.

Usage:
    python eval/recall_calculator.py                    # Show Recall@10 summary
    python eval/recall_calculator.py --detailed        # Show per-sample results
    python eval/recall_calculator.py --json > out.json # JSON output
"""
import argparse
import asyncio
import json
import logging
from pathlib import Path

from app.catalog import load_catalog
from app.config import get_settings
from app.conversation import ConversationContextExtractor
from app.guardrails import GuardrailService
from app.llm import GroqClient, LLMGenerator
from app.agent import AssessmentAgent
from app.agent.responder import DeterministicResponder
from app.retrieval import CatalogRetriever
from app.schemas import ChatRequest, Message

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


SAMPLES_DIR = Path(__file__).parent.parent / "Data" / "samples"


def load_ground_truth() -> dict[str, set[str]]:
    """Load expected product names for each sample.

    Format: {"C1": {"OPQ32r", "Verify G+"}, "C2": {...}}
    """
    truth_file = SAMPLES_DIR / "ground_truth.json"
    if not truth_file.exists():
        logger.warning("Ground truth file not found: %s", truth_file)
        return {}

    try:
        with open(truth_file) as f:
            data = json.load(f)
        return {k: set(v) for k, v in data.items()}
    except Exception as e:
        logger.error("Failed to load ground truth: %s", e)
        return {}


def load_samples() -> dict[str, list[dict]]:
    """Load conversation samples."""
    samples_file = SAMPLES_DIR / "conversations.json"
    if not samples_file.exists():
        logger.warning("Sample file not found: %s", samples_file)
        return {}

    try:
        with open(samples_file) as f:
            return json.load(f)
    except Exception as e:
        logger.error("Failed to load samples: %s", e)
        return {}


def calculate_recall_at_k(recommended: list[str], expected: set[str], k: int = 10) -> float:
    """Calculate Recall@K: what fraction of expected items were in top-K recommendations."""
    if not expected:
        return 1.0

    recommended_set = set(recommended[:k])
    intersection = recommended_set & expected
    return len(intersection) / len(expected)


async def evaluate_recall(
    agent: AssessmentAgent,
    sample_name: str,
    messages: list[dict],
    expected: set[str],
) -> dict:
    """Run sample and calculate Recall@10."""
    try:
        msg_list = [Message(role=m["role"], content=m["content"]) for m in messages]
        request = ChatRequest(messages=msg_list)
        response = await asyncio.wait_for(agent.chat(request), timeout=30.0)

        recommended = [item.name for item in response.recommendations]
        recall_at_10 = calculate_recall_at_k(recommended, expected, k=10)

        return {
            "sample": sample_name,
            "recall_at_10": round(recall_at_10, 3),
            "expected_count": len(expected),
            "recommended_count": len(recommended),
            "recommended_names": recommended,
            "expected_names": sorted(list(expected)),
            "matched": sorted(list(set(recommended[:10]) & expected)),
            "missed": sorted(list(expected - set(recommended[:10]))),
        }
    except Exception as e:
        return {
            "sample": sample_name,
            "recall_at_10": 0.0,
            "error": str(e),
        }


async def run_recall_evaluation(
    agent: AssessmentAgent,
    samples: dict[str, list],
    ground_truth: dict[str, set[str]],
) -> list[dict]:
    """Evaluate all samples."""
    results = []

    for sample_name in sorted(samples.keys()):
        if sample_name not in ground_truth:
            logger.warning("Skipping %s — no ground truth", sample_name)
            continue

        print(f"Evaluating {sample_name}...", end=" ", flush=True)
        result = await evaluate_recall(agent, sample_name, samples[sample_name], ground_truth[sample_name])

        if "error" in result:
            print(f"ERROR: {result['error']}")
        else:
            print(f"Recall@10 = {result['recall_at_10']}")

        results.append(result)

    return results


def print_summary(results: list[dict]) -> None:
    """Print human-readable summary."""
    if not results:
        print("No results to summarize.")
        return

    successful = [r for r in results if "error" not in r]
    if not successful:
        print("All samples failed evaluation.")
        return

    recalls = [r["recall_at_10"] for r in successful]
    mean_recall = sum(recalls) / len(recalls) if recalls else 0.0

    print("\n" + "=" * 60)
    print("RECALL@10 EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Total samples:   {len(results)}")
    print(f"Successful:      {len(successful)}")
    print(f"Failed:          {len(results) - len(successful)}")
    print("=" * 60)
    print(f"Mean Recall@10:  {mean_recall:.3f}")
    print(f"Min Recall@10:   {min(recalls):.3f}")
    print(f"Max Recall@10:   {max(recalls):.3f}")
    print("=" * 60)

    print("\nPer-Sample Results:")
    for r in sorted(successful, key=lambda x: x["recall_at_10"]):
        status = "✓" if r["recall_at_10"] >= 0.7 else "✗"
        print(f"  {status} {r['sample']}: {r['recall_at_10']:.3f} ({len(r['matched'])}/{r['expected_count']} matched)")

    print("=" * 60)


async def main():
    parser = argparse.ArgumentParser(description="Calculate Recall@10 metrics")
    parser.add_argument("--detailed", action="store_true", help="Show detailed results")
    parser.add_argument("--json", action="store_true", help="Output JSON results")
    args = parser.parse_args()

    ground_truth = load_ground_truth()
    samples = load_samples()

    if not ground_truth or not samples:
        print("Error: Could not load samples or ground truth.")
        return

    settings = get_settings()
    catalog = load_catalog(settings.catalog_path)
    retriever = CatalogRetriever(catalog)
    extractor = ConversationContextExtractor(catalog)
    guardrail = GuardrailService()
    responder = DeterministicResponder()

    groq_client = GroqClient(settings)
    llm_gen = LLMGenerator(client=groq_client, catalog=catalog, responder=responder)

    agent = AssessmentAgent(
        catalog=catalog,
        retriever=retriever,
        context_extractor=extractor,
        guardrail_service=guardrail,
        llm_generator=llm_gen,
    )

    results = await run_recall_evaluation(agent, samples, ground_truth)

    if args.json:
        print(json.dumps(results, indent=2))
    elif args.detailed:
        for r in results:
            if "error" not in r:
                print(f"\n{r['sample']}:")
                print(f"  Recall@10: {r['recall_at_10']}")
                print(f"  Expected:  {', '.join(r['expected_names'][:3])}...")
                print(f"  Matched:   {', '.join(r['matched'][:3])}...")
                if r['missed']:
                    print(f"  Missed:    {', '.join(r['missed'][:3])}...")
    else:
        print_summary(results)


if __name__ == "__main__":
    asyncio.run(main())

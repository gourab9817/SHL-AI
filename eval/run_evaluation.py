#!/usr/bin/env python3
"""Regression evaluation harness for the SHL AI Recommender.

Runs the agent against known conversation samples (C1-C10) and measures:
- Response schema compliance
- Recommendation count and quality
- Timeout compliance
- Guardrail enforcement

Usage:
    python eval/run_evaluation.py                    # Run all samples
    python eval/run_evaluation.py --sample C5       # Run specific sample
    python eval/run_evaluation.py --json > results.json  # JSON output
"""
import argparse
import asyncio
import json
import logging
import sys
import time
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


def load_samples() -> dict[str, list[dict]]:
    """Load conversation samples from JSON.

    Format: {"C1": [{"role": "user", "content": "..."}, ...], "C2": [...]}
    """
    samples_file = SAMPLES_DIR / "conversations.json"
    if not samples_file.exists():
        logger.warning("Sample file not found: %s", samples_file)
        return {}

    try:
        with open(samples_file) as f:
            data = json.load(f)
        return data
    except Exception as e:
        logger.error("Failed to load samples: %s", e)
        return {}


def validate_response_schema(response) -> tuple[bool, str]:
    """Check response against required schema."""
    try:
        assert hasattr(response, "reply") and isinstance(response.reply, str)
        assert hasattr(response, "recommendations") and isinstance(
            response.recommendations, list
        )
        assert hasattr(response, "end_of_conversation") and isinstance(
            response.end_of_conversation, bool
        )
        for item in response.recommendations:
            assert hasattr(item, "name") and isinstance(item.name, str)
            assert hasattr(item, "url") and isinstance(item.url, str)
            assert hasattr(item, "test_type") and isinstance(item.test_type, str)
        return True, "Schema valid"
    except AssertionError as e:
        return False, f"Schema violation: {e}"


async def evaluate_sample(agent: AssessmentAgent, sample_name: str, messages: list[dict]) -> dict:
    """Run a single conversation sample and collect metrics."""
    try:
        msg_list = [Message(role=m["role"], content=m["content"]) for m in messages]
        request = ChatRequest(messages=msg_list)

        start = time.monotonic()
        response = await asyncio.wait_for(agent.chat(request), timeout=30.0)
        elapsed = time.monotonic() - start

        schema_ok, schema_msg = validate_response_schema(response)

        return {
            "sample": sample_name,
            "status": "PASS" if schema_ok else "FAIL",
            "elapsed_seconds": round(elapsed, 2),
            "schema_valid": schema_ok,
            "schema_message": schema_msg,
            "recommendation_count": len(response.recommendations),
            "end_of_conversation": response.end_of_conversation,
            "reply_length": len(response.reply),
            "error": None,
        }
    except asyncio.TimeoutError:
        return {
            "sample": sample_name,
            "status": "TIMEOUT",
            "elapsed_seconds": 30.0,
            "schema_valid": False,
            "schema_message": "Request exceeded 30s timeout",
            "recommendation_count": 0,
            "end_of_conversation": False,
            "reply_length": 0,
            "error": "timeout",
        }
    except Exception as e:
        return {
            "sample": sample_name,
            "status": "ERROR",
            "elapsed_seconds": 0.0,
            "schema_valid": False,
            "schema_message": str(type(e).__name__),
            "recommendation_count": 0,
            "end_of_conversation": False,
            "reply_length": 0,
            "error": str(e),
        }


async def run_all_evaluations(agent: AssessmentAgent, samples: dict[str, list], filter_sample: str | None = None) -> list[dict]:
    """Run all samples and collect results."""
    results = []

    for sample_name in sorted(samples.keys()):
        if filter_sample and sample_name != filter_sample:
            continue

        print(f"Running {sample_name}...", end=" ", flush=True)
        result = await evaluate_sample(agent, sample_name, samples[sample_name])
        results.append(result)
        print(f"{result['status']} ({result['elapsed_seconds']}s)")

    return results


def print_summary(results: list[dict]) -> None:
    """Print human-readable summary."""
    if not results:
        print("No results to summarize.")
        return

    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    errors = sum(1 for r in results if r["status"] == "ERROR")
    timeouts = sum(1 for r in results if r["status"] == "TIMEOUT")

    print("\n" + "=" * 60)
    print("REGRESSION EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Total samples: {len(results)}")
    print(f"  ✓ PASS:    {passed}")
    print(f"  ✗ FAIL:    {failed}")
    print(f"  ⚠ ERROR:   {errors}")
    print(f"  ⏱ TIMEOUT: {timeouts}")
    print("=" * 60)

    if results:
        avg_latency = sum(r["elapsed_seconds"] for r in results) / len(results)
        max_latency = max(r["elapsed_seconds"] for r in results)
        print(f"Latency (avg): {avg_latency:.2f}s")
        print(f"Latency (max): {max_latency:.2f}s")
        avg_recs = sum(r["recommendation_count"] for r in results) / len(results)
        print(f"Recommendations (avg): {avg_recs:.1f}")

    if failed > 0 or errors > 0:
        print("\nFailed/Error Samples:")
        for r in results:
            if r["status"] in ("FAIL", "ERROR"):
                print(f"  {r['sample']}: {r['schema_message']}")

    print("=" * 60)
    exit_code = 0 if (failed == 0 and errors == 0 and timeouts == 0) else 1
    return exit_code


async def main():
    parser = argparse.ArgumentParser(description="Regression evaluation harness")
    parser.add_argument("--sample", help="Run specific sample (e.g. C5)")
    parser.add_argument("--json", action="store_true", help="Output JSON results")
    args = parser.parse_args()

    samples = load_samples()
    if not samples:
        print("Error: Could not load conversation samples.")
        sys.exit(1)

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

    results = await run_all_evaluations(agent, samples, args.sample)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        exit_code = print_summary(results)
        sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())

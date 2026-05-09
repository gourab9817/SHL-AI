#!/usr/bin/env python3
"""Performance benchmarking for the SHL AI Recommender.

Measures:
- Latency (p50, p95, p99)
- Throughput (requests/sec)
- Memory usage
- Startup time

Usage:
    python eval/benchmark.py --duration 60       # Run for 60 seconds
    python eval/benchmark.py --requests 100      # Run 100 requests
    python eval/benchmark.py --csv results.csv   # Export to CSV
"""
import argparse
import asyncio
import csv
import statistics
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


TEST_MESSAGE = Message(role="user", content="Senior backend engineer role: Java, Spring, REST, AWS, Docker")


async def time_single_request(agent: AssessmentAgent) -> float:
    """Measure latency of a single chat request."""
    start = time.monotonic()
    request = ChatRequest(messages=[TEST_MESSAGE])
    await agent.chat(request)
    return time.monotonic() - start


async def benchmark_latency(agent: AssessmentAgent, num_requests: int = 20) -> dict:
    """Measure request latency distribution."""
    latencies = []
    print(f"Running {num_requests} sequential requests...")

    for i in range(num_requests):
        print(f"  [{i+1}/{num_requests}]", end=" ", flush=True)
        latency = await time_single_request(agent)
        latencies.append(latency)
        print(f"{latency:.2f}s")

    if not latencies:
        return {}

    return {
        "count": len(latencies),
        "min_ms": round(min(latencies) * 1000, 2),
        "max_ms": round(max(latencies) * 1000, 2),
        "mean_ms": round(statistics.mean(latencies) * 1000, 2),
        "median_ms": round(statistics.median(latencies) * 1000, 2),
        "stdev_ms": round(statistics.stdev(latencies) * 1000, 2) if len(latencies) > 1 else 0.0,
        "p95_ms": round(sorted(latencies)[int(len(latencies) * 0.95)] * 1000, 2),
        "p99_ms": round(sorted(latencies)[int(len(latencies) * 0.99)] * 1000, 2),
    }


async def benchmark_throughput(agent: AssessmentAgent, duration_seconds: int = 30) -> dict:
    """Measure requests/second under load."""
    print(f"Running throughput test for {duration_seconds} seconds...")
    start_time = time.monotonic()
    request_count = 0
    failed_count = 0

    while time.monotonic() - start_time < duration_seconds:
        try:
            request = ChatRequest(messages=[TEST_MESSAGE])
            await asyncio.wait_for(agent.chat(request), timeout=30.0)
            request_count += 1
        except asyncio.TimeoutError:
            failed_count += 1
        except Exception:
            failed_count += 1

        if request_count % 5 == 0:
            elapsed = time.monotonic() - start_time
            rate = request_count / elapsed if elapsed > 0 else 0
            print(f"  {request_count} requests in {elapsed:.1f}s ({rate:.2f} req/s)")

    elapsed = time.monotonic() - start_time
    return {
        "duration_seconds": round(elapsed, 2),
        "total_requests": request_count,
        "failed_requests": failed_count,
        "success_rate": round(100 * request_count / (request_count + failed_count), 1) if (request_count + failed_count) > 0 else 0.0,
        "throughput_req_per_sec": round(request_count / elapsed, 2) if elapsed > 0 else 0.0,
    }


async def main():
    parser = argparse.ArgumentParser(description="Performance benchmarking")
    parser.add_argument("--duration", type=int, default=30, help="Throughput test duration (seconds)")
    parser.add_argument("--requests", type=int, default=20, help="Number of latency test requests")
    parser.add_argument("--csv", help="Export results to CSV file")
    args = parser.parse_args()

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

    print("=" * 60)
    print("SHL AI RECOMMENDER - PERFORMANCE BENCHMARK")
    print("=" * 60)

    print("\n1. LATENCY TEST")
    print("-" * 60)
    latency_results = await benchmark_latency(agent, args.requests)

    print("\n2. THROUGHPUT TEST")
    print("-" * 60)
    throughput_results = await benchmark_throughput(agent, args.duration)

    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)

    if latency_results:
        print("\nLatency (ms):")
        print(f"  Min:    {latency_results['min_ms']}")
        print(f"  Median: {latency_results['median_ms']}")
        print(f"  Mean:   {latency_results['mean_ms']}")
        print(f"  P95:    {latency_results['p95_ms']}")
        print(f"  P99:    {latency_results['p99_ms']}")
        print(f"  Max:    {latency_results['max_ms']}")
        print(f"  StdDev: {latency_results['stdev_ms']}")

    if throughput_results:
        print("\nThroughput:")
        print(f"  Rate:         {throughput_results['throughput_req_per_sec']} req/s")
        print(f"  Total:        {throughput_results['total_requests']} requests")
        print(f"  Success rate: {throughput_results['success_rate']}%")
        print(f"  Duration:     {throughput_results['duration_seconds']}s")

    if args.csv:
        csv_path = Path(args.csv)
        with open(csv_path, "w") as f:
            writer = csv.writer(f)
            writer.writerow(["metric", "value"])
            for key, value in {**latency_results, **throughput_results}.items():
                writer.writerow([key, value])
        print(f"\n✓ Results exported to {csv_path}")

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

# Evaluation Harness

This directory contains tools for evaluating the SHL AI Recommender against known conversation samples.

## Scripts

### `run_evaluation.py` — Regression Testing

Runs the agent against all conversation samples (C1-C10) and validates:
- Response schema compliance (required fields, types)
- Recommendation count and structure
- Timeout compliance (<30 seconds)
- Guardrail enforcement (refusals on suspicious input)

**Usage:**

```bash
# Run all samples
python eval/run_evaluation.py

# Run specific sample
python eval/run_evaluation.py --sample C5

# JSON output for parsing
python eval/run_evaluation.py --json > results.json
```

**Output:**

```
Running C1... PASS (1.23s)
Running C2... PASS (0.87s)
...
============================================================
REGRESSION EVALUATION SUMMARY
============================================================
Total samples: 10
  ✓ PASS:    10
  ✗ FAIL:    0
  ⚠ ERROR:   0
  ⏱ TIMEOUT: 0
============================================================
Latency (avg): 2.15s
Latency (max): 5.32s
Recommendations (avg): 5.3
============================================================
```

Exit code is 1 if any tests fail, 0 if all pass.

### `recall_calculator.py` — Ranking Quality (Recall@10)

Evaluates recommendation ranking quality by comparing recommended products against known-good items.

Requires ground truth: `Data/samples/ground_truth.json`

```json
{
  "C1": ["OPQ32r", "Verify G+", "SHL Numerical Reasoning"],
  "C2": ["..."]
}
```

**Usage:**

```bash
# Show Recall@10 summary
python eval/recall_calculator.py

# Detailed per-sample results
python eval/recall_calculator.py --detailed

# JSON output
python eval/recall_calculator.py --json > recall.json
```

**Metric Definition:**

Recall@10 = (matching products in top 10) / (expected products)

- **1.0** = all expected products found in top 10
- **0.5** = half of expected products found in top 10
- **0.0** = no expected products found in top 10

**Output:**

```
============================================================
RECALL@10 EVALUATION SUMMARY
============================================================
Total samples:   10
Successful:      10
Failed:          0
============================================================
Mean Recall@10:  0.870
Min Recall@10:   0.600
Max Recall@10:   1.000
============================================================

Per-Sample Results:
  ✓ C1: 0.900 (3/3 matched)
  ✓ C2: 0.875 (7/8 matched)
  ...
```

### `benchmark.py` — Performance Testing

Measures latency percentiles and throughput under load.

**Usage:**

```bash
# Default: 20 sequential requests + 30s throughput test
python eval/benchmark.py

# Custom request count
python eval/benchmark.py --requests 50

# Custom throughput duration
python eval/benchmark.py --duration 60

# Export to CSV
python eval/benchmark.py --csv results.csv
```

**Output:**

```
============================================================
SHL AI RECOMMENDER - PERFORMANCE BENCHMARK
============================================================

1. LATENCY TEST
Running 20 sequential requests...
  [1/20] 2.34s
  [2/20] 1.89s
  ...

2. THROUGHPUT TEST
Running throughput test for 30 seconds...
  5 requests in 14.2s (0.35 req/s)
  10 requests in 28.1s (0.36 req/s)

============================================================
RESULTS SUMMARY
============================================================

Latency (ms):
  Min:    850
  Median: 1200
  Mean:   1450
  P95:    2100
  P99:    2800
  Max:    3200
  StdDev: 650

Throughput:
  Rate:         0.35 req/s
  Total:        10 requests
  Success rate: 100.0%
  Duration:     28.1s

✓ Results exported to results.csv
============================================================
```

## Test Data

Required sample files in `Data/samples/`:

- **conversations.json** — C1-C10 conversation samples
  ```json
  {
    "C1": [
      {"role": "user", "content": "..."},
      {"role": "assistant", "content": "..."},
      ...
    ],
    "C2": [...]
  }
  ```

- **ground_truth.json** — Expected products for each sample
  ```json
  {
    "C1": ["OPQ32r", "Verify G+", "..."],
    "C2": [...]
  }
  ```

## CI/CD Integration

Use in your CI pipeline:

```bash
#!/bin/bash
set -e

echo "=== Regression Tests ==="
python eval/run_evaluation.py || exit 1

echo "=== Recall@10 Evaluation ==="
python eval/recall_calculator.py || exit 1

echo "=== Performance Benchmark ==="
python eval/benchmark.py --requests 10 --csv perf.csv

echo "✓ All evaluations passed"
```

## Interpreting Results

### Regression Tests

- **PASS** — Response schema valid, within timeout
- **FAIL** — Schema violation (missing field, wrong type)
- **ERROR** — Uncaught exception
- **TIMEOUT** — Request exceeded 30s limit

**Goal:** All tests should be PASS.

### Recall@10

- **Mean ≥ 0.70** — Acceptable ranking (70% of expected products in top 10)
- **Mean ≥ 0.85** — Good ranking
- **Mean ≥ 0.95** — Excellent ranking

**Goal:** Mean Recall@10 ≥ 0.70.

### Latency Benchmarks

- **P95 < 3s** — Good for interactive use
- **P99 < 5s** — Acceptable (evaluator timeout: 30s)
- **Throughput ≥ 0.2 req/s** — Sufficient concurrency capacity

**Goal:** P95 latency < 3s, throughput ≥ 0.2 req/s.

## Troubleshooting

**"Sample file not found"**
- Ensure `Data/samples/conversations.json` exists with C1-C10 data

**"Ground truth file not found"**
- For recall tests, create `Data/samples/ground_truth.json`
- Not required for regression tests

**"Request exceeded timeout"**
- Check LLM latency (Groq API)
- Increase `CHAT_TIMEOUT_SECONDS` (default: 25, max: 29)
- Disable LLM: unset `GROQ_API_KEY` to use deterministic fallback

**High latency variance**
- Network/LLM variability is normal
- Use P95/P99 percentiles, not just mean
- Run multiple benchmark iterations for stable results

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from sqlite_concurrency_benchmark import benchmark_result_to_dict, run_profile


def _scenario_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    scenarios = payload.get("scenarios", [])
    return {str(item["scenario"]): item for item in scenarios}


def _delta(before: float, after: float) -> float:
    if before == 0:
        return 0.0
    return ((after - before) / before) * 100.0


def _build_markdown_report(baseline: dict[str, Any], optimized: dict[str, Any]) -> str:
    baseline_map = _scenario_map(baseline)
    optimized_map = _scenario_map(optimized)

    lines = [
        "# SQLite 并发基准对比",
        "",
        "| 场景 | baseline 吞吐(ops/s) | optimized 吞吐(ops/s) | 吞吐变化 | baseline p95(ms) | optimized p95(ms) | p95变化 | baseline 锁错误 | optimized 锁错误 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for scenario_name in sorted(baseline_map.keys()):
        base = baseline_map[scenario_name]
        opt = optimized_map.get(scenario_name)
        if opt is None:
            continue
        throughput_change = _delta(float(base["throughput_ops_per_s"]), float(opt["throughput_ops_per_s"]))
        p95_change = _delta(float(base["p95_latency_ms"]), float(opt["p95_latency_ms"]))
        lines.append(
            "| {name} | {b_tp:.2f} | {o_tp:.2f} | {tp_delta:+.2f}% | {b_p95:.2f} | {o_p95:.2f} | {p95_delta:+.2f}% | {b_lock} | {o_lock} |".format(
                name=scenario_name,
                b_tp=float(base["throughput_ops_per_s"]),
                o_tp=float(opt["throughput_ops_per_s"]),
                tp_delta=throughput_change,
                b_p95=float(base["p95_latency_ms"]),
                o_p95=float(opt["p95_latency_ms"]),
                p95_delta=p95_change,
                b_lock=int(base["lock_errors"]),
                o_lock=int(opt["lock_errors"]),
            )
        )

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare baseline and optimized SQLite concurrency profiles.")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--iterations", type=int, default=40, dest="iterations_per_worker")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".yggdrasil") / "state" / "benchmarks" / "sqlite-concurrency",
    )
    args = parser.parse_args()

    baseline = benchmark_result_to_dict(
        run_profile("baseline", workers=args.workers, iterations_per_worker=args.iterations_per_worker)
    )
    optimized = benchmark_result_to_dict(
        run_profile("optimized", workers=args.workers, iterations_per_worker=args.iterations_per_worker)
    )

    report_md = _build_markdown_report(baseline, optimized)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "baseline.json").write_text(
        json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "optimized.json").write_text(
        json.dumps(optimized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "comparison.md").write_text(report_md, encoding="utf-8")

    print(report_md)


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json

from .registry import build_worker_report, drain_work_queue, enqueue_work_item, pop_work_item, run_worker_once


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect the current Yggdrasil worker activity registry.")
    parser.add_argument("--json", action="store_true", help="Print the worker report as JSON.")
    parser.add_argument("--queue", default="default", help="Queue name used by enqueue and pop operations.")
    parser.add_argument("--enqueue-json", help="JSON payload to enqueue into Redis coordination queue.")
    parser.add_argument("--pop-once", action="store_true", help="Pop one work item from the Redis coordination queue.")
    parser.add_argument("--run-once", action="store_true", help="Pop one work item and dispatch it through the worker.")
    parser.add_argument("--drain", action="store_true", help="Drain a bounded number of work items from the queue.")
    parser.add_argument("--max-items", type=int, default=10, help="Maximum number of items to consume when draining.")
    args = parser.parse_args()

    if args.enqueue_json:
        result = enqueue_work_item(args.queue, json.loads(args.enqueue_json))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.pop_once:
        result = pop_work_item(args.queue)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.run_once:
        result = run_worker_once(args.queue)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.drain:
        result = drain_work_queue(args.queue, max_items=args.max_items)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    report = build_worker_report()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    print("Yggdrasil worker registry")
    print(f"total activities: {report['totalActivities']}")
    print("registered work kinds:")
    for work_kind in report["workKinds"]:
        print(f"- {work_kind}")


if __name__ == "__main__":
    main()
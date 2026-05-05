from __future__ import annotations

import argparse
import json

from .evaluation_runtime import list_evaluation_suite_definitions, run_evaluation_suite
from .support import load_workspace_dotenv


def main() -> None:
    load_workspace_dotenv()

    parser = argparse.ArgumentParser(description="Run Project Yggdrasil evaluation suites.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List available evaluation suites.")

    run_parser = subparsers.add_parser("run", help="Run one evaluation suite.")
    run_parser.add_argument("--suite", required=True, help="Evaluation suite id.")

    args = parser.parse_args()

    if args.command == "list":
        print(json.dumps({"suites": list_evaluation_suite_definitions()}, ensure_ascii=False, indent=2))
        return

    result = run_evaluation_suite(args.suite)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .ops_runtime import create_runtime_backup, latest_snapshot_dir, launch_local_product, prepare_real_user_validation_sandbox, resolve_backup_root, restore_runtime_backup, run_compose_smoke, run_real_user_live_task_pack, summarize_real_user_scorecard
from .support import load_workspace_dotenv


def main() -> None:
    load_workspace_dotenv()

    parser = argparse.ArgumentParser(description="Project Yggdrasil runtime backup and infra smoke tools.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup_parser = subparsers.add_parser("backup", help="Create or restore runtime backups.")
    backup_subparsers = backup_parser.add_subparsers(dest="backup_command", required=True)

    create_parser = backup_subparsers.add_parser("create", help="Create a backup snapshot.")
    create_parser.add_argument("--snapshot", help="Optional snapshot directory.")

    restore_parser = backup_subparsers.add_parser("restore", help="Restore a backup snapshot.")
    restore_parser.add_argument("--snapshot", help="Snapshot directory. Defaults to the latest snapshot.")

    smoke_parser = subparsers.add_parser("compose-smoke", help="Verify local compose dependencies.")
    smoke_parser.add_argument("--ensure-up", action="store_true", help="Run docker compose up -d before smoke checks.")

    launch_parser = subparsers.add_parser("launch", help="Start local product mode and print the Web URL.")
    launch_parser.add_argument("--allow-missing-provider", action="store_true", help="Allow fallback-only startup when no provider key is configured.")
    launch_parser.add_argument("--allow-existing-services", action="store_true", help="Do not fail if product ports are already in use.")
    launch_parser.add_argument("--skip-infra", action="store_true", help="Do not run docker compose up -d.")
    launch_parser.add_argument("--detach", action="store_true", help="Return after startup instead of keeping services in the foreground.")
    launch_parser.add_argument("--wait-timeout-seconds", type=int, default=90, help="Timeout while waiting for Core API and Web.")

    pilot_parser = subparsers.add_parser("pilot-sandbox", help="Prepare an isolated sandbox for real-user validation.")
    pilot_subparsers = pilot_parser.add_subparsers(dest="pilot_command", required=True)

    pilot_create_parser = pilot_subparsers.add_parser("create", help="Create a real-user validation sandbox.")
    pilot_create_parser.add_argument("--output", help="Sandbox directory. Defaults to a sibling folder outside the repo.")
    pilot_create_parser.add_argument("--workspace", help="Optional workspace root to snapshot. Defaults to the current repo root.")
    pilot_create_parser.add_argument("--disable-live-llm", action="store_true", help="Set YGGDRASIL_DISABLE_LIVE_LLM=1 in activation scripts.")

    scorecard_parser = subparsers.add_parser("pilot-scorecard", help="Summarize real-user validation scorecards.")
    scorecard_subparsers = scorecard_parser.add_subparsers(dest="scorecard_command", required=True)

    scorecard_summarize_parser = scorecard_subparsers.add_parser("summarize", help="Summarize a scorecard CSV for G2 metrics.")
    scorecard_summarize_parser.add_argument("--csv", required=True, help="Path to the scorecard CSV file.")

    live_parser = subparsers.add_parser("pilot-live", help="Run the frozen real-user live task pack inside an isolated sandbox.")
    live_subparsers = live_parser.add_subparsers(dest="live_command", required=True)

    live_run_parser = live_subparsers.add_parser("run-pack", help="Run YGG-CI-01 / YGG-CG-01 / YGG-CG-03 with a real live provider.")
    live_run_parser.add_argument("--sandbox-root", required=True, help="Path to the isolated real-user validation sandbox root.")
    live_run_parser.add_argument("--tasks", help="Comma-separated task ids. Defaults to YGG-CI-01,YGG-CG-01,YGG-CG-03.")
    live_run_parser.add_argument("--provider", default="longcat", help="Requested live provider. Defaults to longcat.")
    live_run_parser.add_argument("--model", default="LongCat-2.0-Preview", help="Requested live model. Defaults to LongCat-2.0-Preview.")
    live_run_parser.add_argument("--scorecard-csv", help="Optional scorecard CSV to append generated rows to.")
    live_run_parser.add_argument("--output", help="Optional JSON output path for the structured run summary.")
    live_run_parser.add_argument("--batch-id", help="Optional batch id written into generated scorecard rows.")
    live_run_parser.add_argument("--environment-id", help="Optional environment id written into generated scorecard rows.")

    paths_parser = subparsers.add_parser("paths", help="Show runtime backup paths.")
    paths_parser.add_argument("--latest", action="store_true", help="Resolve the latest snapshot path too.")

    args = parser.parse_args()

    if args.command == "backup" and args.backup_command == "create":
        snapshot_dir = Path(args.snapshot).resolve() if args.snapshot else None
        result = create_runtime_backup(snapshot_dir=snapshot_dir)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "backup" and args.backup_command == "restore":
        snapshot_dir = Path(args.snapshot).resolve() if args.snapshot else None
        result = restore_runtime_backup(snapshot_dir=snapshot_dir)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "compose-smoke":
        result = run_compose_smoke(ensure_up=args.ensure_up)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "launch":
        result = launch_local_product(
            allow_missing_provider=bool(args.allow_missing_provider),
            allow_existing_services=bool(args.allow_existing_services),
            skip_infra=bool(args.skip_infra),
            detach=bool(args.detach),
            wait_timeout_seconds=int(args.wait_timeout_seconds),
        )
        if args.detach:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "pilot-sandbox" and args.pilot_command == "create":
        output_dir = Path(args.output).resolve() if args.output else None
        workspace_root = Path(args.workspace).resolve() if args.workspace else None
        result = prepare_real_user_validation_sandbox(
            output_dir=output_dir,
            workspace_root=workspace_root,
            disable_live_llm=bool(args.disable_live_llm),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "pilot-scorecard" and args.scorecard_command == "summarize":
        result = summarize_real_user_scorecard(Path(args.csv).resolve())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "pilot-live" and args.live_command == "run-pack":
        task_ids = [item.strip() for item in str(args.tasks or "YGG-CI-01,YGG-CG-01,YGG-CG-03").split(",") if item.strip()]
        result = run_real_user_live_task_pack(
            sandbox_root=Path(args.sandbox_root).resolve(),
            tasks=task_ids,
            provider=str(args.provider),
            model=str(args.model),
            scorecard_csv=Path(args.scorecard_csv).resolve() if args.scorecard_csv else None,
            output_path=Path(args.output).resolve() if args.output else None,
            batch_id=str(args.batch_id) if args.batch_id else None,
            environment_id=str(args.environment_id) if args.environment_id else None,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    payload = {"backupRoot": str(resolve_backup_root())}
    if args.latest:
        try:
            payload["latestSnapshot"] = str(latest_snapshot_dir())
        except FileNotFoundError:
            payload["latestSnapshot"] = None
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

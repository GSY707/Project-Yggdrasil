from __future__ import annotations

import argparse
import json
from pathlib import Path

from .ops_runtime import create_runtime_backup, latest_snapshot_dir, prepare_real_user_validation_sandbox, resolve_backup_root, restore_runtime_backup, run_compose_smoke


def main() -> None:
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

    pilot_parser = subparsers.add_parser("pilot-sandbox", help="Prepare an isolated sandbox for real-user validation.")
    pilot_subparsers = pilot_parser.add_subparsers(dest="pilot_command", required=True)

    pilot_create_parser = pilot_subparsers.add_parser("create", help="Create a real-user validation sandbox.")
    pilot_create_parser.add_argument("--output", help="Sandbox directory. Defaults to a sibling folder outside the repo.")
    pilot_create_parser.add_argument("--workspace", help="Optional workspace root to snapshot. Defaults to the current repo root.")
    pilot_create_parser.add_argument("--disable-live-llm", action="store_true", help="Set YGGDRASIL_DISABLE_LIVE_LLM=1 in activation scripts.")

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

    payload = {"backupRoot": str(resolve_backup_root())}
    if args.latest:
        try:
            payload["latestSnapshot"] = str(latest_snapshot_dir())
        except FileNotFoundError:
            payload["latestSnapshot"] = None
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
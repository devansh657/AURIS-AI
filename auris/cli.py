from __future__ import annotations

import argparse
import json

from auris.audit import record_event
from auris.supervisor import create_task_plan


def main() -> None:
    parser = argparse.ArgumentParser(prog="auris", description="AURIS One local core loop.")
    parser.add_argument("command", help="Natural-language command for AURIS to plan.")
    args = parser.parse_args()

    plan = create_task_plan(args.command)
    audit_path = record_event("task.created", plan.to_dict())

    print(json.dumps(plan.to_dict(), indent=2))
    print(f"\nAudit written to: {audit_path}")


if __name__ == "__main__":
    main()

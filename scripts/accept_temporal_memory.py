from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from auris.database import get_memory
from auris.memory_service import (
    MemoryValidationError,
    correct_memory,
    effective_memories,
    export_memory_archive,
    memory_dashboard,
    memory_history,
    resolve_memory_conflict,
    set_memory_category_enabled,
    store_memory,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="auris-memory-acceptance-") as folder:
        path = Path(folder) / "auris.db"
        first = store_memory(
            "Development backend port is 8000",
            category="project",
            project_id="auris-one",
            subject_key="development backend port",
            environment="development",
            path=path,
        )["memory"]
        second_result = store_memory(
            "Development backend port is 8001",
            category="project",
            project_id="auris-one",
            subject_key="development backend port",
            environment="development",
            path=path,
        )
        second = second_result["memory"]
        require(second_result["requires_resolution"], "Contradiction was not preserved.")
        require(get_memory(first["memory_id"], path=path)["status"] == "active", "Old fact changed before user resolution.")

        dashboard = memory_dashboard(project_id="auris-one", path=path)
        require(len(dashboard["conflicts"]) == 1, "Conflict was not inspectable.")
        conflict = dashboard["conflicts"][0]
        require(not conflict["analysis"]["automatic_resolution"], "Conflict resolved automatically.")

        resolve_memory_conflict(
            conflict["conflict_id"],
            chosen_memory_id=second["memory_id"],
            path=path,
        )
        require(get_memory(first["memory_id"], path=path)["status"] == "superseded", "Rejected fact remained current.")
        require(get_memory(second["memory_id"], path=path)["status"] == "active", "Chosen fact did not become current.")

        corrected = correct_memory(
            second["memory_id"],
            content="Development backend port is 8002",
            reason="Acceptance exercise confirms exact correction history.",
            path=path,
        )["memory"]
        history = memory_history(second["memory_id"], path=path)
        require(corrected["supersedes"] == second["memory_id"], "Correction was not linked to its predecessor.")
        require(len(history["versions"]) >= 3, "Temporal version history is incomplete.")

        relationship = store_memory(
            "Alex is an authorised contact",
            category="relationship",
            subject_key="alex",
            path=path,
        )["memory"]
        set_memory_category_enabled("relationship", False, path=path)
        effective_ids = {item["memory_id"] for item in effective_memories(project_id=None, path=path)}
        require(relationship["memory_id"] not in effective_ids, "Disabled category leaked into retrieval.")

        try:
            store_memory(
                "Credential reference",
                structured_data={"access_token": "access token: abcdefghijklmnop"},
                path=path,
            )
        except MemoryValidationError:
            pass
        else:
            raise SystemExit("Secret material was accepted into ordinary memory.")

        archive = export_memory_archive(project_id=None, path=path)
        encoded = json.dumps(archive, ensure_ascii=True, sort_keys=True)
        require("embeddings" not in encoded.casefold(), "Memory export exposed embedding vectors.")
        require("abcdefghijklmnop" not in encoded, "Rejected secret leaked into export.")
        require(bool(archive["histories"]), "Memory export omitted temporal histories.")
        require(bool(archive["conflicts"]), "Memory export omitted conflict history.")

        print(
            json.dumps(
                {
                    "ok": True,
                    "release": "0.8.7",
                    "memories": len(archive["memories"]),
                    "conflicts_preserved": len(archive["conflicts"]),
                    "corrected_memory_id": corrected["memory_id"],
                    "secret_rejection": True,
                    "disabled_category_retrieval": "blocked",
                    "database": "disposable",
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()

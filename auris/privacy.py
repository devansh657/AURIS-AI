from __future__ import annotations

from copy import deepcopy
from typing import Any


EPHEMERAL_COMMUNICATION_OPERATIONS = {"search_mail", "calendar", "search_contacts"}


def minimise_persisted_result(result: dict[str, Any]) -> dict[str, Any]:
    durable = deepcopy(result)
    communications = durable.get("communications_action")
    if not isinstance(communications, dict):
        return durable
    if communications.get("operation") not in EPHEMERAL_COMMUNICATION_OPERATIONS:
        return durable
    items = communications.pop("items", [])
    communications["item_count"] = len(items) if isinstance(items, list) else 0
    communications["content_persisted"] = False
    return durable

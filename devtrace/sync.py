from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

from devtrace.storage import LocalStore


def sync_pending_events(base_path: Path, endpoint: str, batch_size: int = 100) -> tuple[int, int]:
    """Sync pending local events to a central ingestion endpoint."""
    store = LocalStore(base_path)
    store.ensure_storage()

    pending = store.pending_sync_events(batch_size=batch_size)
    if not pending:
        return 0, 0

    payload = json.dumps({"events": pending}).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    event_ids = [event["id"] for event in pending]
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            code = response.getcode()
            if code < 200 or code >= 300:
                raise RuntimeError(f"sync failed with status {code}")
            payload = json.loads(response.read().decode("utf-8") or "{}")
            accepted = int(payload.get("accepted", 0))
            if accepted != len(event_ids):
                raise RuntimeError(f"sync accepted {accepted}/{len(event_ids)} events")
        store.mark_synced(event_ids)
        return len(event_ids), 0
    except (urllib.error.URLError, RuntimeError) as exc:
        store.mark_sync_failed(event_ids, str(exc))
        return 0, len(event_ids)

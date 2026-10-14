from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO


class LocalAuditIncidentSink:
    """Persist audit checkpoint alerts to a local append-only JSONL file and stderr.

    This is a local operational log, not tamper-proof storage: an administrator
    controlling the host can alter or delete it. The sink makes no network calls.
    """

    def __init__(self, path: str | Path, *, stderr: TextIO | None = None) -> None:
        self.path = Path(path)
        self.stderr = stderr if stderr is not None else sys.stderr

    def alert(self, message: str) -> None:
        if not message.strip():
            raise ValueError("audit incident message must not be empty")
        event = {
            "incident_id": str(uuid.uuid4()),
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "kind": "audit_checkpoint_alert",
            "message": message,
        }
        encoded = (json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            remaining = memoryview(encoded)
            while remaining:
                written = os.write(descriptor, remaining)
                if written <= 0:
                    raise OSError("failed to append complete audit incident record")
                remaining = remaining[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        print(f"PRECOG AUDIT ALERT: {message}", file=self.stderr, flush=True)

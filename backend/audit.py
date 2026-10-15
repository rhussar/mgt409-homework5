"""Append real public events to a JSON array using an atomic file replacement."""
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from models import AuditEvent

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'output'
OUTPUT.mkdir(exist_ok=True)
LOCK = threading.RLock()

def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w') as file:
        json.dump(value, file, indent=2, default=str)
        file.write('\n')
        file.flush()
        os.fsync(file.fileno())
    os.replace(temporary, path)

class Auditor:
    def __init__(self):
        self.path = OUTPUT / 'audit_trail.json'
        self.events = json.loads(self.path.read_text()) if self.path.exists() else []

    def append(self, *, session_id, agent, event, summary, **kwargs):
        with LOCK:
            entry = AuditEvent(id=len(self.events)+1, timestamp=datetime.now(timezone.utc).isoformat(), session_id=session_id,
                agent=agent, event=event, summary=summary, **kwargs).model_dump()
            self.events.append(entry)
            atomic_json(self.path, self.events)
            return entry

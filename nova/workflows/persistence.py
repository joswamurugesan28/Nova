from __future__ import annotations

import sqlite3, json, time
from pathlib import Path


class WorkflowStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.execute("""CREATE TABLE IF NOT EXISTS workflows (
            id TEXT PRIMARY KEY,
            name TEXT,
            state TEXT,
            data TEXT,
            updated REAL
        )""")
        self.conn.commit()

    def save(self, workflow_id: str, name: str, state: str, data: dict) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO workflows (id, name, state, data, updated) VALUES (?,?,?,?,?)",
            (workflow_id, name, state, json.dumps(data), time.time()),
        )
        self.conn.commit()

    def load(self, workflow_id: str) -> dict | None:
        cur = self.conn.execute("SELECT name, state, data FROM workflows WHERE id=?", (workflow_id,))
        row = cur.fetchone()
        if not row:
            return None
        return {"name": row[0], "state": row[1], "data": json.loads(row[2])}

    def list_ids(self) -> list[str]:
        cur = self.conn.execute("SELECT id FROM workflows")
        return [r[0] for r in cur.fetchall()]

    def close(self) -> None:
        self.conn.close()
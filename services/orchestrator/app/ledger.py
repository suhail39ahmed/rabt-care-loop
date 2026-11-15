"""Case ledger + idempotency (SQLite by default)."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

import aiosqlite

from app.state_machine import S


SCHEMA = """
CREATE TABLE IF NOT EXISTS processed_events (
  idempotency_key TEXT PRIMARY KEY,
  created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS cases (
  case_id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL,
  state TEXT NOT NULL,
  urgency TEXT,
  pathway TEXT,
  owner_id TEXT,
  owner_name TEXT,
  language TEXT DEFAULT 'en',
  result_code TEXT,
  result_display TEXT,
  result_value TEXT,
  result_unit TEXT,
  plan_id TEXT,
  plan_name TEXT,
  consent_messaging INTEGER DEFAULT 1,
  teachback_fails INTEGER DEFAULT 0,
  ladder_step INTEGER DEFAULT 0,
  evidence_json TEXT DEFAULT '{}',
  provenance_json TEXT DEFAULT '[]',
  timeline_json TEXT DEFAULT '[]',
  messages_json TEXT DEFAULT '[]',
  options_json TEXT DEFAULT '[]',
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
  token TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  action TEXT NOT NULL,
  required INTEGER NOT NULL,
  created_at REAL NOT NULL,
  due_at REAL NOT NULL,
  status TEXT NOT NULL,
  evidence_json TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS approval_votes (
  token TEXT NOT NULL,
  user_id TEXT NOT NULL,
  decision TEXT NOT NULL,
  reason TEXT,
  at REAL NOT NULL,
  PRIMARY KEY (token, user_id)
);

CREATE TABLE IF NOT EXISTS queue_items (
  id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  urgency TEXT,
  title TEXT NOT NULL,
  detail TEXT,
  ladder_step INTEGER DEFAULT 0,
  status TEXT DEFAULT 'open',
  created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS fhir_resources (
  resource_type TEXT NOT NULL,
  resource_id TEXT NOT NULL,
  version_id TEXT NOT NULL,
  body_json TEXT NOT NULL,
  PRIMARY KEY (resource_type, resource_id)
);
"""


class Ledger:
    def __init__(self, db_path: str = "./data/rabt.db") -> None:
        self.db_path = db_path

    async def connect(self) -> aiosqlite.Connection:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        db = await aiosqlite.connect(self.db_path)
        db.row_factory = aiosqlite.Row
        await db.executescript(SCHEMA)
        await db.commit()
        return db

    async def seen_event(self, db: aiosqlite.Connection, key: str) -> bool:
        cur = await db.execute(
            "SELECT 1 FROM processed_events WHERE idempotency_key = ?", (key,)
        )
        return await cur.fetchone() is not None

    async def mark_event(self, db: aiosqlite.Connection, key: str) -> bool:
        """Return True if newly inserted, False if already seen."""
        try:
            await db.execute(
                "INSERT INTO processed_events(idempotency_key, created_at) VALUES (?, ?)",
                (key, time.time()),
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

    async def create_case(self, db: aiosqlite.Connection, payload: dict[str, Any]) -> dict[str, Any]:
        now = time.time()
        case_id = payload.get("case_id") or f"case-{uuid.uuid4().hex[:10]}"
        row = {
            "case_id": case_id,
            "patient_id": payload["patient_id"],
            "state": S.NEW.value,
            "urgency": payload.get("urgency"),
            "pathway": payload.get("pathway"),
            "owner_id": payload.get("owner_id"),
            "owner_name": payload.get("owner_name"),
            "language": payload.get("language", "en"),
            "result_code": payload.get("result_code"),
            "result_display": payload.get("result_display"),
            "result_value": payload.get("result_value"),
            "result_unit": payload.get("result_unit"),
            "plan_id": payload.get("plan_id"),
            "plan_name": payload.get("plan_name"),
            "consent_messaging": 1 if payload.get("consent_messaging", True) else 0,
            "teachback_fails": 0,
            "ladder_step": 0,
            "evidence_json": json.dumps(payload.get("evidence", {})),
            "provenance_json": json.dumps([]),
            "timeline_json": json.dumps(
                [
                    {
                        "at": now,
                        "kind": "fact",
                        "label": "Case opened",
                        "detail": payload.get("result_display", "Screening result received"),
                        "actor": "system:intake",
                    }
                ]
            ),
            "messages_json": json.dumps([]),
            "options_json": json.dumps([]),
            "created_at": now,
            "updated_at": now,
        }
        await db.execute(
            """
            INSERT INTO cases(
              case_id, patient_id, state, urgency, pathway, owner_id, owner_name, language,
              result_code, result_display, result_value, result_unit, plan_id, plan_name,
              consent_messaging, teachback_fails, ladder_step, evidence_json, provenance_json,
              timeline_json, messages_json, options_json, created_at, updated_at
            ) VALUES (
              :case_id, :patient_id, :state, :urgency, :pathway, :owner_id, :owner_name, :language,
              :result_code, :result_display, :result_value, :result_unit, :plan_id, :plan_name,
              :consent_messaging, :teachback_fails, :ladder_step, :evidence_json, :provenance_json,
              :timeline_json, :messages_json, :options_json, :created_at, :updated_at
            )
            """,
            row,
        )
        await db.commit()
        return await self.get_case(db, case_id)

    async def get_case(self, db: aiosqlite.Connection, case_id: str) -> dict[str, Any] | None:
        cur = await db.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,))
        row = await cur.fetchone()
        if not row:
            return None
        return self._hydrate(dict(row))

    async def list_cases(self, db: aiosqlite.Connection) -> list[dict[str, Any]]:
        cur = await db.execute("SELECT * FROM cases ORDER BY updated_at DESC")
        rows = await cur.fetchall()
        return [self._hydrate(dict(r)) for r in rows]

    async def update_case(self, db: aiosqlite.Connection, case_id: str, **fields: Any) -> dict[str, Any]:
        case = await self.get_case(db, case_id)
        if not case:
            raise KeyError(case_id)
        normalised: dict[str, Any] = {}
        for k, v in fields.items():
            if k in {"evidence", "provenance", "timeline", "messages", "options"}:
                normalised[f"{k}_json"] = json.dumps(v)
            elif k.endswith("_json") and not isinstance(v, str):
                normalised[k] = json.dumps(v)
            else:
                normalised[k] = v
        normalised["updated_at"] = time.time()
        sets = ", ".join(f"{k} = ?" for k in normalised)
        await db.execute(
            f"UPDATE cases SET {sets} WHERE case_id = ?",
            [*normalised.values(), case_id],
        )
        await db.commit()
        return await self.get_case(db, case_id)  # type: ignore[return-value]

    async def append_timeline(
        self,
        db: aiosqlite.Connection,
        case_id: str,
        *,
        kind: str,
        label: str,
        detail: str,
        actor: str,
    ) -> None:
        case = await self.get_case(db, case_id)
        if not case:
            return
        timeline = case["timeline"]
        timeline.append(
            {"at": time.time(), "kind": kind, "label": label, "detail": detail, "actor": actor}
        )
        await self.update_case(db, case_id, timeline=timeline)

    async def put_fhir(self, db: aiosqlite.Connection, resource: dict[str, Any]) -> dict[str, Any]:
        rtype = resource["resourceType"]
        rid = resource.get("id") or uuid.uuid4().hex[:12]
        resource["id"] = rid
        meta = resource.setdefault("meta", {})
        version = str(int(meta.get("versionId", "0")) + 1)
        meta["versionId"] = version
        meta["lastUpdated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        await db.execute(
            """
            INSERT INTO fhir_resources(resource_type, resource_id, version_id, body_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(resource_type, resource_id) DO UPDATE SET
              version_id = excluded.version_id,
              body_json = excluded.body_json
            """,
            (rtype, rid, version, json.dumps(resource)),
        )
        await db.commit()
        return resource

    async def get_fhir(
        self, db: aiosqlite.Connection, resource_type: str, resource_id: str
    ) -> dict[str, Any] | None:
        cur = await db.execute(
            "SELECT body_json FROM fhir_resources WHERE resource_type = ? AND resource_id = ?",
            (resource_type, resource_id),
        )
        row = await cur.fetchone()
        return json.loads(row["body_json"]) if row else None

    def _hydrate(self, row: dict[str, Any]) -> dict[str, Any]:
        row["evidence"] = json.loads(row.pop("evidence_json") or "{}")
        row["provenance"] = json.loads(row.pop("provenance_json") or "[]")
        row["timeline"] = json.loads(row.pop("timeline_json") or "[]")
        row["messages"] = json.loads(row.pop("messages_json") or "[]")
        row["options"] = json.loads(row.pop("options_json") or "[]")
        row["consent_messaging"] = bool(row.get("consent_messaging", 1))
        return row

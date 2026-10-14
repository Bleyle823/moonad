"""Lunar-side tasking and settlement (no keys, no RPC).

Machines on the surface share this folder like a local mesh sync. The prospector
and lander task agent read/write here. Earth settler tails the same paths after
sync and only signs payouts that match an open job and a settlement intent.
"""

from __future__ import annotations

import json
import os
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
ACTIVE_JOB = os.path.join(ROOT, "active_job.json")
ESCROW_LEDGER = os.path.join(ROOT, "escrow_ledger.json")
LANDER_LOG = os.path.join(ROOT, "lander_events.jsonl")
SETTLEMENT_INTENTS = os.path.join(ROOT, "settlement_intents.jsonl")


def _append(path: str, rec: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, separators=(",", ":")) + "\n")


def write_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def read_json(path: str):
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def post_job(
    job_id: str,
    buyer_machine_id: str,
    worker_machine_id: str,
    per_discovery_agung: str,
    escrow_total_agung: str,
    sample_ids: list[str],
) -> dict:
    job = {
        "job_id": job_id,
        "buyer_machine_id": buyer_machine_id,
        "worker_machine_id": worker_machine_id,
        "per_discovery_agung": per_discovery_agung,
        "escrow_total_agung": escrow_total_agung,
        "sample_ids": sample_ids,
        "posted_at": int(time.time()),
    }
    write_json(ACTIVE_JOB, job)
    ledger = {
        "job_id": job_id,
        "buyer_machine_id": buyer_machine_id,
        "worker_machine_id": worker_machine_id,
        "escrow_total_agung": escrow_total_agung,
        "remaining_agung": escrow_total_agung,
        "per_discovery_agung": per_discovery_agung,
    }
    write_json(ESCROW_LEDGER, ledger)
    _append(
        LANDER_LOG,
        {
            "event": "job_posted",
            "payload": job,
        },
    )
    _append(
        LANDER_LOG,
        {
            "event": "escrow_committed",
            "payload": {
                "job_id": job_id,
                "buyer_machine_id": buyer_machine_id,
                "escrow_total_agung": escrow_total_agung,
                "remaining_agung": escrow_total_agung,
            },
        },
    )
    return job


def load_active_job():
    return read_json(ACTIVE_JOB)


def load_escrow_ledger():
    return read_json(ESCROW_LEDGER)


def request_discovery_release(
    job: dict,
    sample_id: str,
    verification: str,
    worker_pose: dict | None = None,
) -> bool:
    """Record a moon-local release intent (buyer policy checks happen on Earth)."""
    ledger = load_escrow_ledger()
    if not ledger or ledger.get("job_id") != job.get("job_id"):
        return False
    try:
        remaining = float(ledger.get("remaining_agung", 0))
        per = float(job.get("per_discovery_agung", 0))
    except (TypeError, ValueError):
        return False
    if per <= 0 or remaining < per:
        print("[lunar] escrow insufficient for", sample_id)
        return False
    remaining = round(remaining - per, 8)
    ledger["remaining_agung"] = str(remaining)
    write_json(ESCROW_LEDGER, ledger)
    intent = {
        "intent": "release_discovery",
        "job_id": job["job_id"],
        "sample_id": sample_id,
        "amount_agung": job["per_discovery_agung"],
        "buyer_machine_id": job["buyer_machine_id"],
        "worker_machine_id": job["worker_machine_id"],
        "verification": verification,
        "worker_pose": worker_pose or {},
        "ts": int(time.time()),
    }
    _append(SETTLEMENT_INTENTS, intent)
    _append(
        LANDER_LOG,
        {
            "event": "settlement_intent",
            "payload": intent,
        },
    )
    return True

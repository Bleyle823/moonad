"""Ground segment: sign lunar settlement intents and anchor peaq events.

Lunar machines post jobs and intents under webots/rover/controllers/lunar_economy/.
This process never drives the rover. It tails synced logs and signs transfers from the
buyer (lander) machine wallet to the worker (prospector) wallet when a release intent
matches an open job and escrow policy.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
LUNAR = ROOT / "webots" / "rover" / "controllers" / "lunar_economy"
LOG_PATH = ROOT / "webots" / "rover" / "controllers" / "prospecting" / "peaq_events.jsonl"
LANDER_LOG = LUNAR / "lander_events.jsonl"
INTENTS_PATH = LUNAR / "settlement_intents.jsonl"
WALLET_PATH = HERE / "config" / "wallets.json"
STATE_PATH = HERE / "config" / "submitted.json"
ENV_PATH = HERE / ".env"
AGUNG_CHAIN_ID = 9990


def _load_dotenv():
    if not ENV_PATH.exists():
        return
    for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _ensure_machine_key() -> str | None:
    if os.environ.get("PEAQOS_PRIVATE_KEY"):
        return os.environ["PEAQOS_PRIVATE_KEY"]
    wallet = _read_json(WALLET_PATH, {})
    key = wallet.get("private_key")
    if key:
        os.environ["PEAQOS_PRIVATE_KEY"] = key
        if wallet.get("address"):
            os.environ.setdefault("PEAQOS_MACHINE_ADDRESS", wallet["address"])
        return key
    if not os.environ.get("PEAQOS_RPC_URL"):
        return None
    try:
        from eth_account import Account
    except ImportError:
        print("[settler] no PEAQOS_PRIVATE_KEY and eth-account is not installed")
        return None
    acct = Account.create()
    pk = acct.key.hex()
    if not pk.startswith("0x"):
        pk = "0x" + pk
    rec = {"address": acct.address, "private_key": pk, "label": "prospector-1"}
    _write_json(WALLET_PATH, rec)
    os.environ["PEAQOS_PRIVATE_KEY"] = pk
    os.environ.setdefault("PEAQOS_MACHINE_ADDRESS", acct.address)
    print("[settler] wrote worker wallet to", WALLET_PATH, "address", acct.address)
    return pk


def _peaq_ready() -> bool:
    needed = (
        "PEAQOS_RPC_URL",
        "PEAQOS_PRIVATE_KEY",
        "IDENTITY_REGISTRY_ADDRESS",
        "IDENTITY_STAKING_ADDRESS",
        "EVENT_REGISTRY_ADDRESS",
        "MACHINE_NFT_ADDRESS",
        "DID_REGISTRY_ADDRESS",
        "BATCH_PRECOMPILE_ADDRESS",
    )
    missing = [k for k in needed if not os.environ.get(k)]
    if missing:
        print("[settler] peaq skipped, missing", ", ".join(missing))
        return False
    return True


def _client():
    from peaq_os_sdk import PeaqosClient

    return PeaqosClient.from_env()


def _register(client) -> int | None:
    env_id = os.environ.get("PEAQOS_MACHINE_ID")
    if env_id:
        print("[settler] using PEAQOS_MACHINE_ID", env_id)
        return int(env_id)
    try:
        machine_id = int(client.register_machine())
        print("[settler] register_machine", machine_id)
        wallet = _read_json(WALLET_PATH, {})
        wallet["machine_id"] = machine_id
        _write_json(WALLET_PATH, wallet)
        return machine_id
    except Exception as exc:
        code = getattr(exc, "code", "") or exc.__class__.__name__
        print("[settler] register refused:", code, exc)
        return None


def _submit(client, machine_id: int, rec: dict) -> str | None:
    from peaq_os_sdk import EVENT_TYPE_ACTIVITY, TRUST_SELF_REPORTED

    kind = rec.get("event", "activity")
    payload = rec.get("payload") or {}
    raw = json.dumps({"event": kind, "payload": payload}, separators=(",", ":")).encode()
    ts = int(time.time()) - 2
    value = 1
    if kind == "sample_found":
        amt = payload.get("amount_agung") or os.environ.get("DISCOVERY_PAY_AMOUNT", "")
        try:
            if amt:
                value = max(1, int(float(amt) * 1_000_000))
        except (TypeError, ValueError):
            value = 1
    try:
        tx_hash, data_hash = client.submit_event(
            machine_id=machine_id,
            event_type=EVENT_TYPE_ACTIVITY,
            value=value,
            currency="",
            timestamp=ts,
            raw_data=raw,
            trust_level=TRUST_SELF_REPORTED,
            source_chain_id=AGUNG_CHAIN_ID,
            source_tx_hash=None,
            metadata=b"",
        )
        digest = data_hash.hex() if isinstance(data_hash, (bytes, bytearray)) else str(data_hash)
        print("[settler] submitted", kind, "tx", tx_hash, "hash", digest)
        return str(tx_hash)
    except Exception as exc:
        code = getattr(exc, "code", "") or exc.__class__.__name__
        print("[settler] submit refused:", kind, code, exc)
        return None


def _buyer_dynamic_account() -> str | None:
    return os.environ.get("LANDER_DYNAMIC_ACCOUNT_ADDRESS") or os.environ.get("DYNAMIC_ACCOUNT_ADDRESS")


def _dynamic_ready() -> bool:
    return bool(
        os.environ.get("DYNAMIC_AUTH_TOKEN")
        and os.environ.get("DYNAMIC_ENVIRONMENT_ID")
        and _buyer_dynamic_account()
    )


def _parse_tx_from_pay_output(out: str) -> str | None:
    for line in out.splitlines():
        if "tx" not in line:
            continue
        if "paid_escrow_release" in line or "paid_discovery" in line:
            parts = line.split()
            if "tx" in parts:
                idx = parts.index("tx")
                if idx + 1 < len(parts):
                    return parts[idx + 1]
    return None


def _run_pay(buyer_account: str, worker_address: str, amount: str, reference: str) -> tuple[bool, str | None]:
    pay_script = HERE / "pay.mjs"
    if not pay_script.exists():
        print("[settler] pay skipped, no pay.mjs")
        return True, None
    if not _dynamic_ready():
        print("[settler] pay skipped, Dynamic env incomplete (need LANDER_DYNAMIC_ACCOUNT_ADDRESS)")
        return False, None
    env = os.environ.copy()
    env["PAYER_DYNAMIC_ACCOUNT_ADDRESS"] = buyer_account
    env["MACHINE_ADDRESS"] = worker_address
    env["PAY_AMOUNT"] = amount
    env["PAY_REFERENCE"] = reference
    try:
        proc = subprocess.run(
            ["node", str(pay_script)],
            cwd=str(HERE),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        print("[settler] pay skipped, node failed:", exc)
        return False, None
    out = (proc.stdout or "") + (proc.stderr or "")
    if out.strip():
        print(out.rstrip())
    if proc.returncode != 0:
        return False, None
    return True, _parse_tx_from_pay_output(out)


def _sync_job_from_lander(rec: dict, state: dict) -> None:
    kind = rec.get("event")
    payload = rec.get("payload") or {}
    if kind == "job_posted":
        jid = payload.get("job_id")
        if not jid:
            return
        try:
            per = float(payload.get("per_discovery_agung", 0))
            total = float(payload.get("escrow_total_agung", 0))
        except (TypeError, ValueError):
            return
        jobs = state.setdefault("jobs", {})
        jobs[jid] = {
            "buyer_machine_id": payload.get("buyer_machine_id"),
            "worker_machine_id": payload.get("worker_machine_id"),
            "per_discovery": per,
            "escrow_total": total,
            "remaining": total,
        }
        _write_json(STATE_PATH, state)
        print("[settler] lunar job registered", jid, "escrow", total)
    elif kind == "escrow_committed":
        jid = payload.get("job_id")
        jobs = state.setdefault("jobs", {})
        if jid and jid in jobs:
            try:
                jobs[jid]["remaining"] = float(payload.get("remaining_agung", jobs[jid]["remaining"]))
            except (TypeError, ValueError):
                pass
            _write_json(STATE_PATH, state)


def _release_intent(intent: dict, state: dict, worker_address: str) -> bool:
    if intent.get("intent") != "release_discovery":
        return True
    sample_id = intent.get("sample_id")
    job_id = intent.get("job_id")
    if not sample_id or not job_id:
        print("[settler] intent skipped, missing sample or job")
        return True
    paid = state.setdefault("discovery_paid", {})
    key = f"{job_id}:{sample_id}"
    if key in paid:
        return True
    jobs = state.get("jobs") or {}
    job = jobs.get(job_id)
    if not job:
        print("[settler] intent waiting for lunar job", job_id)
        return False
    try:
        amount = float(intent.get("amount_agung", job.get("per_discovery", 0)))
        remaining = float(job.get("remaining", 0))
    except (TypeError, ValueError):
        print("[settler] intent skipped, bad amounts")
        return True
    if amount <= 0 or remaining < amount:
        print("[settler] intent refused, escrow exhausted for", job_id)
        return True
    if intent.get("worker_machine_id") and intent.get("worker_machine_id") != job.get("worker_machine_id"):
        print("[settler] intent refused, worker mismatch")
        return True
    buyer = _buyer_dynamic_account()
    if not buyer or not worker_address:
        return False
    ref = f"{job_id}:{sample_id}"
    ok, tx = _run_pay(buyer, worker_address, str(amount), ref)
    if not ok:
        return False
    job["remaining"] = round(remaining - amount, 8)
    jobs[job_id] = job
    state["jobs"] = jobs
    paid[key] = {"tx": tx, "amount": amount, "buyer": job.get("buyer_machine_id")}
    state["discovery_paid"] = paid
    _write_json(STATE_PATH, state)
    print("[settler] escrow release", ref, "buyer machine", job.get("buyer_machine_id"), tx or "")
    return True


def _maybe_fund_worker(machine_address: str) -> None:
    token = os.environ.get("DYNAMIC_AUTH_TOKEN")
    env_id = os.environ.get("DYNAMIC_ENVIRONMENT_ID")
    account = os.environ.get("DYNAMIC_ACCOUNT_ADDRESS")
    if not (token and env_id and account and machine_address):
        print("[settler] worker gas fund skipped (optional DYNAMIC_ACCOUNT_ADDRESS)")
        return
    fund = HERE / "fund.mjs"
    if not fund.exists():
        return
    env = os.environ.copy()
    env["MACHINE_ADDRESS"] = machine_address
    try:
        subprocess.run(["node", str(fund)], cwd=str(HERE), env=env, check=False)
    except OSError as exc:
        print("[settler] worker gas fund skipped:", exc)


def _fingerprint(line: str) -> str:
    return line.strip()


def _tail_jsonl(path: Path, offset: int, chunk_handler) -> int:
    if not path.exists():
        return offset
    data = path.read_text(encoding="utf-8")
    if len(data) < offset:
        offset = 0
    chunk = data[offset:]
    new_offset = len(data)
    for line in chunk.splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            print("[settler] skip bad line in", path.name)
            continue
        chunk_handler(line, rec)
    return new_offset


def main() -> int:
    _load_dotenv()
    print("[settler] ground segment — lunar bus at", LUNAR)
    print("[settler] watching prospector", LOG_PATH.name, "intents", INTENTS_PATH.name)
    _ensure_machine_key()
    worker_address = os.environ.get("PEAQOS_MACHINE_ADDRESS") or _read_json(WALLET_PATH, {}).get("address")
    _maybe_fund_worker(worker_address or "")

    client = None
    machine_id = None
    if _peaq_ready():
        try:
            client = _client()
            machine_id = _register(client)
        except Exception as exc:
            code = getattr(exc, "code", "") or exc.__class__.__name__
            print("[settler] peaq client refused:", code, exc)
            client = None

    state = _read_json(STATE_PATH, {"done": [], "lander_done": [], "intent_done": []})
    done = set(state.get("done") or [])
    lander_done = set(state.get("lander_done") or [])
    intent_done = set(state.get("intent_done") or [])
    prospector_offset = 0
    lander_offset = 0
    intent_offset = 0

    while True:
        def on_lander(line, rec):
            nonlocal state, lander_done
            fp = _fingerprint(line)
            if fp in lander_done:
                return
            print("[settler] lunar", rec.get("event"), rec.get("payload"))
            _sync_job_from_lander(rec, state)
            lander_done.add(fp)
            state["lander_done"] = list(lander_done)[-200:]
            _write_json(STATE_PATH, state)

        lander_offset = _tail_jsonl(LANDER_LOG, lander_offset, on_lander)

        def on_intent(line, intent):
            nonlocal state, intent_done
            fp = _fingerprint(line)
            if fp in intent_done:
                return
            print("[settler] lunar intent", intent.get("intent"), intent.get("sample_id"))
            if _release_intent(intent, state, worker_address or ""):
                intent_done.add(fp)
                state["intent_done"] = list(intent_done)[-200:]
                _write_json(STATE_PATH, state)

        intent_offset = _tail_jsonl(INTENTS_PATH, intent_offset, on_intent)

        def on_prospector(line, rec):
            nonlocal done, state
            fp = _fingerprint(line)
            if fp in done:
                return
            kind = rec.get("event")
            print("[settler] prospector", kind, rec.get("payload"))
            if client is None or machine_id is None:
                print("[settler] local only, no peaq write")
                done.add(fp)
                state["done"] = list(done)[-200:]
                _write_json(STATE_PATH, state)
                return
            _submit(client, machine_id, rec)
            done.add(fp)
            state["done"] = list(done)[-200:]
            _write_json(STATE_PATH, state)

        prospector_offset = _tail_jsonl(LOG_PATH, prospector_offset, on_prospector)

        time.sleep(1.0)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        sys.exit(0)

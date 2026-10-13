"""Tail the Webots peaq event log and submit on agung.

Keys stay here. The Webots controller never loads peaq-os-sdk.
If PEAQOS_* or DYNAMIC_* are missing, or the chain refuses the call, print the
event and the reason. Do not invent a transaction hash.
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
LOG_PATH = ROOT / "webots" / "rover" / "controllers" / "prospecting" / "peaq_events.jsonl"
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
    rec = {"address": acct.address, "private_key": pk, "label": "moonad-sawppy"}
    _write_json(WALLET_PATH, rec)
    os.environ["PEAQOS_PRIVATE_KEY"] = pk
    os.environ.setdefault("PEAQOS_MACHINE_ADDRESS", acct.address)
    print("[settler] wrote machine wallet to", WALLET_PATH, "address", acct.address)
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
    try:
        tx_hash, data_hash = client.submit_event(
            machine_id=machine_id,
            event_type=EVENT_TYPE_ACTIVITY,
            value=1,
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


def _maybe_fund(machine_address: str) -> None:
    token = os.environ.get("DYNAMIC_AUTH_TOKEN")
    env_id = os.environ.get("DYNAMIC_ENVIRONMENT_ID")
    account = os.environ.get("DYNAMIC_ACCOUNT_ADDRESS")
    if not (token and env_id and account and machine_address):
        missing = []
        if not token:
            missing.append("DYNAMIC_AUTH_TOKEN")
        if not env_id:
            missing.append("DYNAMIC_ENVIRONMENT_ID")
        if not account:
            missing.append("DYNAMIC_ACCOUNT_ADDRESS")
        if not machine_address:
            missing.append("machine address")
        print("[settler] Dynamic fund skipped, missing", ", ".join(missing))
        return
    fund = HERE / "fund.mjs"
    if not fund.exists():
        print("[settler] Dynamic fund skipped, no fund.mjs")
        return
    env = os.environ.copy()
    env["MACHINE_ADDRESS"] = machine_address
    try:
        subprocess.run(["node", str(fund)], cwd=str(HERE), env=env, check=False)
    except OSError as exc:
        print("[settler] Dynamic fund skipped, node failed:", exc)


def _fingerprint(line: str) -> str:
    return line.strip()


def main() -> int:
    _load_dotenv()
    print("[settler] watching", LOG_PATH)
    _ensure_machine_key()
    machine_address = os.environ.get("PEAQOS_MACHINE_ADDRESS") or _read_json(WALLET_PATH, {}).get("address")
    _maybe_fund(machine_address or "")

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

    state = _read_json(STATE_PATH, {"done": []})
    done = set(state.get("done") or [])
    offset = 0
    while True:
        if LOG_PATH.exists():
            data = LOG_PATH.read_text(encoding="utf-8")
            if len(data) < offset:
                offset = 0
            chunk = data[offset:]
            offset = len(data)
            for line in chunk.splitlines():
                if not line.strip():
                    continue
                fp = _fingerprint(line)
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    print("[settler] skip bad line")
                    continue
                kind = rec.get("event")
                print("[settler] event", kind, rec.get("payload"))
                if fp in done:
                    continue
                if client is None or machine_id is None:
                    print("[settler] local only, no chain write")
                    done.add(fp)
                    continue
                tx = _submit(client, machine_id, rec)
                if tx:
                    done.add(fp)
                    state["done"] = list(done)[-200:]
                    _write_json(STATE_PATH, state)
                else:
                    done.add(fp)
                    state["done"] = list(done)[-200:]
                    _write_json(STATE_PATH, state)
        time.sleep(1.0)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        sys.exit(0)

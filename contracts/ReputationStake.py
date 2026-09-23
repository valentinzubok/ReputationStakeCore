# v0.3.0
# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }

import genlayer as gl
import hashlib
import json
import re

# ReputationStake v0.2 — reputation escrow with consensus-gated slash.
# Copyright (c) 2026 Valentyn Zubok. MIT License.
#
# Lifecycle: credit → stake → active → released | slashed
# release: target or owner only (staker cannot unwind unilaterally).
# slash: get_webpage(evidence_url) + prompt_comparative on {"breach": bool}.
# Balances are bookkeeping units (Portal points metaphor) — no native GL transfer.

MAX_ID_LEN = 64
MAX_PURPOSE_LEN = 512
MAX_REASON_LEN = 512
MAX_STAKE_AMOUNT = 1_000_000_000
PREVIEW_CHARS = 280
HASH_ALGO = "sha256"

STATUS_ACTIVE = "active"
STATUS_RELEASED = "released"
STATUS_SLASHED = "slashed"

ADDR_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
HTTPS_URL_RE = re.compile(r"^https://[^\s<>\"']+$", re.IGNORECASE)


def _normalize_id(stake_id: str) -> str:
    sid = str(stake_id).strip()
    if not sid:
        raise Exception("stake_id is required")
    if len(sid) > MAX_ID_LEN:
        raise Exception("stake_id exceeds 64 chars")
    for ch in sid:
        ok = ("a" <= ch.lower() <= "z") or ("0" <= ch <= "9") or ch in "-_/"
        if not ok:
            raise Exception("stake_id: only a-z, 0-9, -, _, /")
    return sid


def _require_address(label: str, value: str) -> str:
    addr = str(value).strip()
    if not ADDR_RE.match(addr):
        raise Exception(f"{label} must be a 0x address")
    return addr


def _parse_amount(amount) -> int:
    try:
        amt = int(str(amount).strip())
    except Exception:
        raise Exception("amount must be a positive integer")
    if amt <= 0:
        raise Exception("amount must be positive")
    if amt > MAX_STAKE_AMOUNT:
        raise Exception("amount exceeds max stake")
    return amt


def _sanitize_text(label: str, text: str, max_len: int) -> str:
    cleaned = " ".join(str(text).split())
    if not cleaned:
        raise Exception(f"{label} is required")
    if len(cleaned) > max_len:
        raise Exception(f"{label} exceeds {max_len} chars")
    return cleaned


def _require_https(url: str) -> str:
    u = str(url).strip()
    if not HTTPS_URL_RE.match(u):
        raise Exception("evidence_url must be https:// with no whitespace")
    if len(u) > 2048:
        raise Exception("evidence_url exceeds 2048 chars")
    return u


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize(text: str) -> str:
    return " ".join(str(text).split())


def _capture_evidence(url: str) -> str:
    entry = {
        "url": url,
        "content_hash": "",
        "hash_algo": HASH_ALGO,
        "preview": "",
        "byte_len": 0,
        "status": "error",
    }
    try:
        raw = gl.nondet.web.render(url, mode="text")
        if raw is None or str(raw).strip() == "":
            raw = gl.nondet.web.render(url, mode="html")
        normalized = _normalize(raw if raw is not None else "")
        if normalized == "":
            entry["status"] = "empty"
        else:
            entry["content_hash"] = _hash_text(normalized)
            entry["preview"] = normalized[:PREVIEW_CHARS]
            entry["byte_len"] = len(normalized)
            entry["status"] = "ok"
    except Exception as exc:
        entry["preview"] = str(exc)[:120]
        entry["status"] = "error"
    return json.dumps(entry, sort_keys=True, separators=(",", ":"))


def _judge_breach(purpose: str, reason: str, preview: str) -> str:
    judge = (
        "You are a GenLayer escrow arbiter.\n"
        "Decide if the staker BREACHED the stated purpose given the slash reason "
        "and evidence page preview.\n"
        f"Purpose (what was promised):\n{purpose}\n"
        f"Slash reason (claim):\n{reason}\n"
        f"Evidence page preview:\n{preview}\n"
        "PASS breach=true only if evidence + reason clearly show the purpose was "
        "not fulfilled. If evidence is empty/irrelevant or claim is weak, breach=false.\n"
        'Return JSON with exactly one field: {"breach": true} or {"breach": false}\n'
        "No other keys."
    )
    try:
        result = gl.nondet.exec_prompt(judge, response_format="json")
    except Exception:
        try:
            result = gl.nondet.exec_prompt(judge)
        except Exception:
            return json.dumps({"breach": False}, sort_keys=True, separators=(",", ":"))

    if isinstance(result, str):
        try:
            result = json.loads(result)
        except Exception:
            result = {"breach": False}
    if not isinstance(result, dict):
        result = {"breach": False}
    return json.dumps(
        {"breach": bool(result.get("breach", False))},
        sort_keys=True,
        separators=(",", ":"),
    )


class ReputationStake(gl.contract.Contract):
    owner: str
    arbiter: str
    fee_receiver: str
    fee_per_action: str
    balances_json: str
    stakes_json: str
    order_json: str
    seq: str
    events_json: str

    def __init__(self, owner_address: str, arbiter_address: str = ""):
        owner = _require_address("owner_address", owner_address)
        self.owner = owner
        self.arbiter = _require_address("arbiter_address", arbiter_address or owner_address)
        self.fee_receiver = owner
        self.fee_per_action = "0"
        self.balances_json = "{}"
        self.stakes_json = "{}"
        self.order_json = "[]"
        self.seq = "0"
        self.events_json = "[]"

    def _load_balances(self):
        return json.loads(self.balances_json)

    def _save_balances(self, balances):
        self.balances_json = json.dumps(balances, sort_keys=True, separators=(",", ":"))

    def _load_stakes(self):
        return json.loads(self.stakes_json)

    def _save_stakes(self, stakes):
        self.stakes_json = json.dumps(stakes, sort_keys=True, separators=(",", ":"))

    def _load_order(self):
        return json.loads(self.order_json)

    def _save_order(self, order):
        self.order_json = json.dumps(order, separators=(",", ":"))

    def _append_event(self, kind: str, payload: dict):
        events = json.loads(self.events_json)
        events.append({"kind": kind, **payload})
        if len(events) > 200:
            events = events[-200:]
        self.events_json = json.dumps(events, separators=(",", ":"))

    def _only_owner(self):
        if str(gl.message.sender_address) != self.owner:
            raise Exception("only owner")

    def _only_arbiter(self):
        caller = str(gl.message.sender_address)
        if caller != self.arbiter and caller != self.owner:
            raise Exception("only arbiter or owner")

    def _balance_of(self, balances, user: str) -> dict:
        key = str(user)
        if key not in balances:
            balances[key] = {"available": 0, "escrowed": 0}
        return balances[key]

    def _next_stake_id(self) -> str:
        n = int(self.seq) + 1
        self.seq = str(n)
        return f"stake-{n}"

    @gl.public.write
    def transfer_ownership(self, new_owner: str) -> None:
        self._only_owner()
        self.owner = _require_address("new_owner", new_owner)
        self._append_event("OwnershipTransferred", {"to": self.owner})

    @gl.public.write
    def set_arbiter(self, new_arbiter: str) -> None:
        self._only_owner()
        self.arbiter = _require_address("new_arbiter", new_arbiter)
        self._append_event("ArbiterUpdated", {"arbiter": self.arbiter})

    @gl.public.write
    def set_fee(self, receiver: str, amount: str) -> None:
        """Bookkeeping fee hint per action (no native payout on Studionet)."""
        self._only_owner()
        self.fee_receiver = _require_address("receiver", receiver)
        amt = str(amount).strip()
        if not amt.isdigit():
            raise Exception("amount must be digits only")
        self.fee_per_action = amt
        self._append_event("FeeUpdated", {"receiver": self.fee_receiver, "amount": amt})

    @gl.public.write
    def credit_reputation(self, user: str, amount: str) -> None:
        """Owner bookkeeping mint for demos / steward bootstrap (not native GL)."""
        self._only_owner()
        addr = _require_address("user", user)
        amt = _parse_amount(amount)
        balances = self._load_balances()
        row = self._balance_of(balances, addr)
        row["available"] = int(row.get("available", 0)) + amt
        balances[addr] = row
        self._save_balances(balances)
        self._append_event("ReputationCredited", {"user": addr, "amount": amt})

    @gl.public.write
    def stake(self, amount: str, target: str, purpose: str) -> None:
        staker = str(gl.message.sender_address)
        target_addr = _require_address("target", target)
        if target_addr == staker:
            raise Exception("cannot stake to yourself")
        amt = _parse_amount(amount)
        purpose_txt = _sanitize_text("purpose", purpose, MAX_PURPOSE_LEN)

        balances = self._load_balances()
        row = self._balance_of(balances, staker)
        available = int(row.get("available", 0))
        if available < amt:
            raise Exception("insufficient reputation balance")

        row["available"] = available - amt
        row["escrowed"] = int(row.get("escrowed", 0)) + amt
        balances[staker] = row
        self._save_balances(balances)

        stake_id = self._next_stake_id()
        stakes = self._load_stakes()
        stakes[stake_id] = {
            "stake_id": stake_id,
            "staker": staker,
            "target": target_addr,
            "amount": amt,
            "purpose": purpose_txt,
            "status": STATUS_ACTIVE,
            "reason": "",
            "evidence_url": "",
            "evidence_hash": "",
            "breach": False,
        }
        self._save_stakes(stakes)
        order = self._load_order()
        order.append(stake_id)
        self._save_order(order)
        self._append_event(
            "StakeCreated",
            {
                "id": stake_id,
                "staker": staker,
                "target": target_addr,
                "amount": amt,
                "purpose": purpose_txt,
            },
        )

    @gl.public.write
    def release(self, stake_id: str) -> None:
        """Target acknowledges success, or owner override. Staker cannot self-unwind."""
        sid = _normalize_id(stake_id)
        stakes = self._load_stakes()
        if sid not in stakes:
            raise Exception("unknown stake_id")
        entry = stakes[sid]
        if entry.get("status") != STATUS_ACTIVE:
            raise Exception("stake is not active")

        caller = str(gl.message.sender_address)
        if caller not in (entry["target"], self.owner):
            raise Exception("only target or owner may release")

        amt = int(entry["amount"])
        balances = self._load_balances()
        row = self._balance_of(balances, entry["staker"])
        row["escrowed"] = max(0, int(row.get("escrowed", 0)) - amt)
        row["available"] = int(row.get("available", 0)) + amt
        balances[entry["staker"]] = row
        self._save_balances(balances)

        entry["status"] = STATUS_RELEASED
        stakes[sid] = entry
        self._save_stakes(stakes)
        self._append_event(
            "StakeReleased",
            {
                "id": sid,
                "staker": entry["staker"],
                "amount": amt,
                "caller": caller,
                "fee_receiver": self.fee_receiver,
                "fee_per_action": self.fee_per_action,
            },
        )

    @gl.public.write
    def slash(self, stake_id: str, reason: str, evidence_url: str) -> None:
        """Arbiter/owner: fetch evidence_url, LLM-judge breach, then transfer escrow.

        Consensus: get_webpage under strict_eq, then prompt_comparative on breach bool only.
        """
        self._only_arbiter()
        sid = _normalize_id(stake_id)
        stakes = self._load_stakes()
        if sid not in stakes:
            raise Exception("unknown stake_id")
        entry = stakes[sid]
        if entry.get("status") != STATUS_ACTIVE:
            raise Exception("stake is not active")

        reason_txt = _sanitize_text("reason", reason, MAX_REASON_LEN)
        url = _require_https(evidence_url)

        def fetch_fn() -> str:
            return _capture_evidence(url)

        snap_json = gl.eq_principle.strict_eq(fetch_fn)
        snap = json.loads(snap_json)
        if snap.get("status") != "ok":
            raise Exception("evidence_url fetch failed or empty")

        purpose = entry.get("purpose", "")
        preview = snap.get("preview", "")

        def leader_fn() -> str:
            return _judge_breach(purpose, reason_txt, preview)

        try:
            verdict_json = gl.eq_principle.prompt_comparative(
                leader_fn,
                principle="boolean field breach must be identical across validators",
            )
        except Exception:
            verdict_json = gl.eq_principle.strict_eq(leader_fn)

        verdict = json.loads(verdict_json) if isinstance(verdict_json, str) else verdict_json
        if not isinstance(verdict, dict):
            verdict = {"breach": False}
        breach = bool(verdict.get("breach", False))

        self._append_event(
            "SlashJudged",
            {
                "id": sid,
                "breach": breach,
                "evidence_url": url,
                "evidence_hash": snap.get("content_hash", ""),
                "caller": str(gl.message.sender_address),
            },
        )

        if not breach:
            raise Exception("validators did not find breach — slash aborted")

        amt = int(entry["amount"])
        balances = self._load_balances()
        staker_row = self._balance_of(balances, entry["staker"])
        staker_row["escrowed"] = max(0, int(staker_row.get("escrowed", 0)) - amt)
        balances[entry["staker"]] = staker_row

        target_row = self._balance_of(balances, entry["target"])
        target_row["available"] = int(target_row.get("available", 0)) + amt
        balances[entry["target"]] = target_row
        self._save_balances(balances)

        entry["status"] = STATUS_SLASHED
        entry["reason"] = reason_txt
        entry["evidence_url"] = url
        entry["evidence_hash"] = snap.get("content_hash", "")
        entry["breach"] = True
        stakes[sid] = entry
        self._save_stakes(stakes)
        self._append_event(
            "StakeSlashed",
            {
                "id": sid,
                "staker": entry["staker"],
                "target": entry["target"],
                "amount": amt,
                "reason": reason_txt,
                "evidence_url": url,
                "arbiter": str(gl.message.sender_address),
                "fee_receiver": self.fee_receiver,
                "fee_per_action": self.fee_per_action,
            },
        )

    @gl.public.view
    def get_stake(self, stake_id: str) -> str:
        sid = _normalize_id(stake_id)
        stakes = self._load_stakes()
        if sid not in stakes:
            return json.dumps({"error": "unknown stake_id"})
        return json.dumps(stakes[sid], sort_keys=True)

    @gl.public.view
    def list_ids(self) -> str:
        return self.order_json

    @gl.public.view
    def list_by_status(self, status: str) -> str:
        wanted = str(status).strip().lower()
        stakes = self._load_stakes()
        order = self._load_order()
        ids = [sid for sid in order if sid in stakes and stakes[sid].get("status") == wanted]
        return json.dumps(ids, separators=(",", ":"))

    @gl.public.view
    def get_balance(self, user: str) -> str:
        addr = _require_address("user", user)
        balances = self._load_balances()
        row = balances.get(addr, {"available": 0, "escrowed": 0})
        return json.dumps({"user": addr, **row}, separators=(",", ":"))

    @gl.public.view
    def get_events(self) -> str:
        return self.events_json

    @gl.public.view
    def get_owner(self) -> str:
        return self.owner

    @gl.public.view
    def get_arbiter(self) -> str:
        return self.arbiter

    @gl.public.view
    def get_fee(self) -> str:
        return json.dumps(
            {"receiver": self.fee_receiver, "amount": self.fee_per_action},
            separators=(",", ":"),
        )

    @gl.public.view
    def get_stats(self) -> str:
        stakes = self._load_stakes()
        active = released = slashed = total_escrowed = 0
        for s in stakes.values():
            st = s.get("status")
            amt = int(s.get("amount", 0))
            if st == STATUS_ACTIVE:
                active += 1
                total_escrowed += amt
            elif st == STATUS_RELEASED:
                released += 1
            elif st == STATUS_SLASHED:
                slashed += 1
        return json.dumps(
            {
                "total": len(stakes),
                "active": active,
                "released": released,
                "slashed": slashed,
                "total_escrowed": total_escrowed,
                "arbiter": self.arbiter,
            },
            separators=(",", ":"),
        )

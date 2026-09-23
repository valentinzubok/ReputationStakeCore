#!/usr/bin/env python3
"""Fail if the Studio Dev deployment no longer matches contracts/ReputationStake.py."""

import base64
import hashlib
import json
import pathlib
import sys
import urllib.request

RPC = "https://studio-dev.genlayer.com/api"
ADDRESS = "0x795b7661E10dF78BEd921dB7986C05b115614015"
SOURCE = pathlib.Path(__file__).resolve().parents[1] / "contracts" / "ReputationStake.py"


def on_chain_hash() -> str:
    payload = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": "gen_getContractCode", "params": [ADDRESS]}
    ).encode()
    headers = {"content-type": "application/json", "user-agent": "reputationstake-ci/1.0"}
    req = urllib.request.Request(RPC, payload, headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.load(resp)["result"]
    return hashlib.sha256(base64.b64decode(result)).hexdigest()


def main() -> int:
    local = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    try:
        remote = on_chain_hash()
    except Exception as exc:  # network flake must not fail the build
        print(f"skipped: could not reach {RPC} ({exc})")
        return 0
    print(f"local   {local}\non-chain {remote}")
    if local != remote:
        print("MISMATCH: redeploy this exact source before submitting", file=sys.stderr)
        return 1
    print("match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

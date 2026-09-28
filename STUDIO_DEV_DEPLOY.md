# ReputationStake v0.4 — Studio Dev (chain 61997) deploy record

| | |
|---|---|
| **Network** | GenLayer Studio Dev / Studio Next — chain `61997`, GenVM `v0.3.0` |
| **Contract** | [`0x1E075794c6404F8f5b9ef87aE29Cf77071Cec86f`](https://explorer-studio-dev.genlayer.com/address/0x1E075794c6404F8f5b9ef87aE29Cf77071Cec86f) |
| **Source** | [`contracts/ReputationStake.py`](contracts/ReputationStake.py) — runner `py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng` |
| **Source sha256** | `e38ca5472ab97da4c02850f80aa3331794b7b809ead4e5bd91ee2e8ea1772d18` |
| **Console** | https://valentinzubok.github.io/ReputationStake/ · [ReputationStake](https://github.com/valentinzubok/ReputationStake) |
| **Owner / arbiter** | `0xBA989D240AAB780d3d2eD2201f5F677098901408` (test account, both roles, so the whole lifecycle could be exercised) |

The v0.2 deploy `0x795b7661…` is superseded: its slash path accepted any URL at dispute time,
judged only the first 280 characters, coerced the model answer with `bool(...)` and silently fell
back to `strict_eq` when comparative consensus failed. See "What changed in v0.4" below.

## Verify that the deployed code equals this source

```bash
curl -s -X POST https://studio-dev.genlayer.com/api -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"gen_getContractCode","params":["0x1E075794c6404F8f5b9ef87aE29Cf77071Cec86f"]}' \
  | python3 -c "import sys,json,base64,hashlib; print(hashlib.sha256(base64.b64decode(json.load(sys.stdin)['result'])).hexdigest())"
shasum -a 256 contracts/ReputationStake.py
# both print e38ca5472ab97da4c02850f80aa3331794b7b809ead4e5bd91ee2e8ea1772d18
```

`scripts/verify_deployment.py` does the same check and runs in CI.

## On-chain lifecycle

| # | Step | Result | Tx |
|---|------|--------|----|
| 0 | deploy | contract created | `0x14ebb892fcf86e990b4e48f7719974b20c489dcadecf1ce7a35fe32e206653f9` |
| 1 | `credit_reputation(staker, 1000)` | balance 1000 | `0x5c6fb480fcc61587e2ef1bc321f57e8ec49a32137bd6d530a021532fcc2c18ba` |
| 2 | `stake("300", target, "Publish a page whose text says: Hello world", "https://test-server.genlayer.com/static/genvm")` | `stake-1` active; the policy is now part of the stake | `0x1f96514250fd7abf2c21d8ad8914611e3f7033807b84733c11b95944a113c666` |
| 3 | `stake("120", target, same purpose, "https://example.com")` | `stake-2` active | `0x3c4d3105123e0a94def996092015c00af96ed235335a073d1f8749de65b3f16b` |
| 4 | `slash("stake-2", "the published page is the IANA example domain page, not the promised hello world page", "https://example.com/")` | **slashed** — real `prompt_comparative` consensus, `breach: true`, document hash `27319d96…` over all 911 chars, 500 chars of excerpts judged, `evidence_source https://example.com` | `0x2bf098c808f867901f273c619dd4e7a1dd11bfdf4e0fb28470142465121d33f1` |
| 5 | `slash("stake-1", …, "https://example.com/")` | **rejected before any LLM spend** — that URL is outside the policy `stake-1` was created with. No `SlashJudged` event, escrow untouched. | `0xb0422555adcce9a68cb300d91f923b30997be8089dcefbdd9c34df8a4de44a12` (ERROR: "evidence_url is outside the evidence_policy agreed when the stake was created") |
| 6 | `slash("stake-1", "the hello world page was never published", ".../hello.html")` | **rejected by consensus** — evidence is inside the policy, but the page does contain the promised text, so validators agreed `no_breach` and the call reverted | `0x16441e992916cd209f2fd07c574c1a5a1b1a3f6d2ef3c0561427c27f83ce7970` (ERROR: "validators did not find breach — slash aborted") |
| 7 | `stake("150", target, "Deliver the hello page as agreed", …)` → `release("stake-3")` | **released**, units returned | `0xd72ff2bdf3bfa96183bebdcf79fee6c5bb776c767135a5554bca625b11766370`, `0x9256969e39614154df120c897ce7a962c1c5973bc170c94b401f08b232a8bce6` |

State (`get_stats`): `{"total":3,"active":1,"released":1,"slashed":1,"total_escrowed":300}`

Read the policy of a live stake without a wallet:

```bash
# allowed source, and a URL that is refused
curl -s -X POST https://studio-dev.genlayer.com/api -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"gen_call","params":[{"to":"0x1E075794c6404F8f5b9ef87aE29Cf77071Cec86f","data":"","type":"read","method":"get_evidence_policy","args":["stake-1"]}]}'
```

or use the console, which shows the policy on every stake card and dry-runs
`check_evidence_url` before the arbiter pays a fee.

## What changed in v0.4

| Steward request | Change |
|---|---|
| Evidence must be constrained by rules agreed at stake creation | `stake()` now takes a required `evidence_policy` (up to 5 https sources). `slash()` calls `check_policy()` first: exact origin, path-prefix on a boundary, dot segments refused. A URL chosen only at dispute time cannot be used. |
| Judge a bounded representation of the relevant evidence, not the first 280 chars | The whole normalized document is hashed, and `build_evidence_digest()` builds up to 6 non-overlapping windows — the head plus windows around the words of the obligation and the claim — capped at 4000 chars. Deterministic, so `strict_eq` still agrees. `evidence_chars` / `evidence_covered_chars` are stored. |
| Validate the model result as an actual JSON boolean | `literal_bool()` accepts only `True`/`False`; `"true"`, `1`, `"yes"`, `[]`, `{}` are not verdicts. The leader returns `verdict: "breach" \| "no_breach" \| "invalid"`, and anything but the first two reverts. |
| Treat purpose, reason and evidence as untrusted quoted data | `quote_untrusted()` fences each of them and neutralizes fences inside the data; the prompt frame states they are data, never instructions; `injection_flags()` reports injection phrasing to the model and stores it in the `SlashJudged` event. |
| Fail closed if comparative consensus fails | The `except: strict_eq` fallback is gone. **Removing it exposed a real bug:** `principle` is positional-only in GenVM v0.3, so `prompt_comparative(leader_fn, principle=...)` always raised `TypeError` and the old contract had been silently deciding under `strict_eq`. The call is now positional, and the test double enforces positional-only so this cannot regress. |
| Adversarial tests | `tests/test_adversarial.py`: 12 malformed/non-boolean model outputs, model error, consensus failure, 5 out-of-policy URLs, dot segments, policy parsing, injection in page/purpose/reason with fence assertions, evidence 6 KB deep in the page, digest bounds/determinism/non-overlap, conflicting evidence, empty and failing fetches. 37 tests total. |
| Frontend must distinguish ACCEPTED from FINALIZED | The console now waits for `ACCEPTED`, labels it "accepted — awaiting finalization", then polls to `FINALIZED` and only then calls the transaction complete. |

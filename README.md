# ReputationStakeCore

<p align="center">
  <img src="assets/cover.png" alt="ReputationStake — stake reputation, build trust" width="100%" />
</p>

<p align="center">
  <strong>The ReputationStake intelligent contract on its own: escrowed reputation stakes that can only be slashed when validators agree, from frozen web evidence, that the obligation was breached.</strong>
</p>

<p align="center">
  <a href="https://github.com/valentinzubok/ReputationStakeCore/actions/workflows/ci.yml"><img src="https://github.com/valentinzubok/ReputationStakeCore/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <img src="https://img.shields.io/badge/GenLayer-Studio%20Dev%2061997-0ea5e9?style=flat-square" alt="Studio Dev" />
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=flat-square" alt="MIT" /></a>
</p>

---

## The primitive

Someone promises something off-chain. You want them to have skin in the game, but you do not want the
counterparty — or you — to be judge and jury. ReputationStake escrows the stake and puts the breach question
under consensus:

```
credit_reputation(user, amount)          owner bootstraps bookkeeping units
stake(amount, target, purpose, policy)   staker locks units against a named obligation AND
                                         fixes the https sources a slash may cite
release(stake_id)                        target (or owner) releases: obligation met, units return
slash(stake_id, reason, evidence_url)    the arbiter asks the network and cannot steer it:
      1. evidence_url must match the evidence_policy agreed at stake time
         (exact origin, path prefix on a boundary, no dot segments) — else it reverts
         here, before any LLM is spent
      2. validators fetch the page and agree on the SHA-256 of the WHOLE normalized
         document plus a bounded deterministic digest of it (eq_principle.strict_eq)
      3. validators' LLMs judge that digest with obligation, claim and page text quoted
         as untrusted data, and must return a literal JSON boolean
         (eq_principle.prompt_comparative — no fallback)
      4. breach == true  → escrow moves to the target, verdict + document hash stored
         anything else   → the whole transaction reverts and the escrow does not move
```

The last line is the point: an arbiter cannot slash on assertion alone. A slash needs evidence that the
network, reading it independently, agrees supports the claim.

### Hardening (v0.4)

| Risk | What stops it |
|---|---|
| Arbiter picks convenient evidence at dispute time | `evidence_policy` is committed by the staker in `stake()`; `slash()` enforces exact origin + path-prefix-on-a-boundary and refuses dot segments. `check_evidence_url` dry-runs it for free. |
| The judged text is only the top of the page | The whole document is hashed; the model reads up to 4000 chars assembled from the head plus non-overlapping windows around the obligation's and claim's own words. |
| `bool("no")` is `True` | `literal_bool()` accepts only JSON `true`/`false`; every other shape reverts the transaction. |
| Prompt injection inside purpose, reason or the page | Each is fenced as untrusted data, inner fences are neutralized, injection phrasing is flagged to the model and recorded in the event. |
| Consensus quietly degrading | No fallback: if `prompt_comparative` cannot run, the slash reverts. (Removing the old fallback surfaced a real bug — `principle` is positional-only in GenVM v0.3, so the keyword form had always raised and the old contract decided under `strict_eq`.) |

### Design decisions worth reviewing

| Decision | Why |
|---|---|
| Only `breach` goes through `prompt_comparative` | A boolean converges across models; summaries do not. |
| Evidence is frozen first under `strict_eq` | The verdict is tied to the exact text validators saw, and the hash stays on chain. |
| A rejected slash reverts the whole call | No partial state, no "attempted slash" bookkeeping, and the escrow stays put. |
| Stake, release and slash are separate roles | Staker locks, target or owner releases, only the arbiter can ask for a slash. |
| Bookkeeping units, not native transfers | Studio-safe and auditable; the same logic maps onto a token later. |

## API

| Function | Access | Effect |
|---|---|---|
| `credit_reputation(user, amount)` | owner | Bootstrap balances. |
| `stake(amount, target, purpose, evidence_policy)` | anyone with balance | Escrow units against an obligation and fix the evidence sources a slash may cite (cannot stake to yourself). |
| `release(stake_id)` | target or owner | Obligation met: units go back to the staker. |
| `slash(stake_id, reason, evidence_url)` | arbiter or owner | Consensus-gated slash, as above. |
| `set_arbiter` · `set_fee` · `transfer_ownership` | owner | Wiring. |
| `get_evidence_policy` · `check_evidence_url` | view | Read a stake's evidence rules; dry-run a URL against them. |
| `get_stake` · `list_ids` · `list_by_status` · `get_balance` · `get_events` · `get_stats` · `get_owner` · `get_arbiter` · `get_fee` | view | Read state. |

## Live deployment (verified by CI)

| | |
|---|---|
| Network | GenLayer Studio Dev / Studio Next, chain `61997` |
| Contract | [`0x1E075794c6404F8f5b9ef87aE29Cf77071Cec86f`](https://explorer-studio-dev.genlayer.com/address/0x1E075794c6404F8f5b9ef87aE29Cf77071Cec86f) |
| Source sha256 | `e38ca5472ab97da4c02850f80aa3331794b7b809ead4e5bd91ee2e8ea1772d18` |
| Full record | [`STUDIO_DEV_DEPLOY.md`](STUDIO_DEV_DEPLOY.md) |

`scripts/verify_deployment.py` compares the deployed bytes with `contracts/ReputationStake.py` on every CI run,
so the repository cannot drift away from the contract a reviewer inspects.

## Tests

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest -q     # 37 tests, including tests/test_adversarial.py
```

The suite substitutes a fake GenVM module (whose `prompt_comparative` is positional-only, exactly like
the real one) and covers the lifecycle, access control and validation, plus an adversarial file:
malformed and non-boolean model output, model errors, consensus failure, out-of-policy and
dot-segment URLs, prompt injection in the page/obligation/claim, evidence 6 KB deep in a document,
digest bounds and determinism, conflicting evidence, and empty or failing fetches.

## Using it from an app

Contract-only by design. The reference console (Next.js + `genlayer-js` + MetaMask) lives in
**[ReputationStake](https://github.com/valentinzubok/ReputationStake)**.

## License

[MIT](LICENSE) © 2026 Valentyn Zubok

# ReputationStake — Studio Dev (chain 61997) deploy record

| | |
|---|---|
| **Network** | GenLayer Studio Dev / Studio Next — chain `61997`, GenVM `v0.3.0-rc7` |
| **Contract** | [`0x795b7661E10dF78BEd921dB7986C05b115614015`](https://explorer-studio-dev.genlayer.com/address/0x795b7661E10dF78BEd921dB7986C05b115614015) |
| **Source** | [`contracts/ReputationStake.py`](contracts/ReputationStake.py) — runner `py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng` |
| **Source sha256** | `8945223c774a1837942948ceecb625f8ded16b478585d1eb8732d14c112bf858` |
| **Console (separate repo)** | https://reputationstake-console.vercel.app · [ReputationStake](https://github.com/valentinzubok/ReputationStake) |

Owner and arbiter are the same test account in this deployment so the whole lifecycle could be exercised;
`set_arbiter` and `transfer_ownership` move both.

## Verify that the deployed code equals this source

```bash
curl -s -X POST https://studio-dev.genlayer.com/api -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"gen_getContractCode","params":["0x795b7661E10dF78BEd921dB7986C05b115614015"]}' \
  | python3 -c "import sys,json,base64,hashlib; print(hashlib.sha256(base64.b64decode(json.load(sys.stdin)['result'])).hexdigest())"
shasum -a 256 contracts/ReputationStake.py
# both print 8945223c774a1837942948ceecb625f8ded16b478585d1eb8732d14c112bf858
```

`scripts/verify_deployment.py` does the same check and runs in CI.

## On-chain lifecycle (all `ACCEPTED`)

| # | Step | Result | Tx |
|---|------|--------|----|
| 0 | deploy (owner = arbiter = test account) | contract created | `0xe10528446664cae6f568d5b0b7b73e82d98ab8527abe96f535813e4a95e33adb` |
| 1 | `credit_reputation(staker, 1000)` | balance 1000 | `0x84837451e829e90fe3c92c706c0ef2e5ada388c8096085f5063ed167c99df3cd` |
| 2 | `stake("200", target, "Deliver the hello page as agreed")` | `stake-1` active, 200 escrowed | `0xd27784c9bc1d25eaed4baf42957d72b3d05fec39e1229183ca06c71b9f02cc04` |
| 3 | `stake("150", target, "Publish a page that says Hello world")` | `stake-2` active | `0x71a7a7cc3bfeb4e4fe280c2d9fa79731b5fcc76dde686119a64d42a6736fb52b` |
| 4 | `release("stake-2")` by the target | **released**, units returned | `0x54f65abf482a98cf69fe11126bd05ed8e4097b40a43550ab47ca8dea23fe58bd` |
| 5 | `slash("stake-1", "page was never published", hello.html)` | **rejected by consensus** — the evidence shows the page *is* published, so validators found no breach and the call reverted with "validators did not find breach — slash aborted". `stake-1` stayed active. | `0xe0353c6a01b204dcfd4de92d0006417d49eea39b7966ef8153d04ac06c8fe46e` |
| 6 | `stake("120", target, "Publish a page whose text says: Hello world")` | `stake-3` active | `0x2c9a8547e0369d89f6bb3a41a3921cfef447fc4b35d621536c5dc4404b19bf0f` |
| 7 | `slash("stake-3", "the published page is the IANA example domain page", https://example.com/)` | **slashed** — `breach: true`, `evidence_hash 8c1e8564…`, escrow moved to the target | `0x26327df47fed83963d624481eeb6e582755de9f8c7820ba9c99b567daf6ac2d8` |

State (`get_stats`): `{"total":3,"active":1,"released":1,"slashed":1,"total_escrowed":200}`

Step 5 is the interesting one: an arbiter tried to slash with evidence that did not support the claim, the
validators' LLMs agreed there was no breach, and the transaction aborted instead of moving the escrow.

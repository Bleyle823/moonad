# Lunar economy bus (on-surface)

This directory is the **lunar control and settlement plane**. Webots runs both machines on one laptop, but the layout matches a surface mesh: the lander task agent and the prospector only talk through files here—no Earth RPC, no keys.

| File | Writer | Meaning |
| --- | --- | --- |
| `active_job.json` | Lander task agent | Open job: buyer, worker, per-discovery pay, escrow cap |
| `escrow_ledger.json` | Lander (commit) + prospector (decrement on intent) | Escrow balance remaining on the Moon |
| `lander_events.jsonl` | Lander | `job_posted`, `escrow_committed`, mirrored intents |
| `settlement_intents.jsonl` | Prospector | `release_discovery` after a verified find |

**Earth (ground segment)** runs `packages/settler`. It reads the same folder after sync, matches intents to the job, and signs a transfer **from the buyer machine wallet to the worker machine wallet** on peaq agung. Dynamic holds signing policy for the lander wallet; the prospector wallet receives earnings.

Runtime files are gitignored. Defaults for the demo job live in the lander controller.

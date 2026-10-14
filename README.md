# moonad

Moon rover for the lunar machine economy

Webots Sawppy port of `ros2_rover` (drive, teleop, moon and Mars worlds): `webots/rover/`.
The live prospecting run is that Sawppy in `webots/rover/worlds/moon.wbt`. An earlier short demo sits in `webots/lunar_prospecting/`.

## Prospecting (Sawppy)

Open `webots/rover/worlds/moon.wbt` in Webots R2025a. Two surface controllers run:

| Machine | Controller | Role |
| --- | --- | --- |
| `lander_task_agent` | `lander_agent` | Buyer — posts job + escrow to the lunar bus |
| Sawppy | `prospecting` | Worker — drives, verifies samples, requests escrow release |

The chassis is the six-wheel, four-steer Sawppy. The contest stack’s behaviour sits on top of that drive:

- A* around rocks on a 0.5 m grid (`algorithm/global_planner.py`)
- Slow down when the forward view has few features (`algorithm/odometer.py`, `algorithm/vehicle.py`)
- Stop and replan on a close depth window (`algorithm/detecter.py`)
- Orange HSV plus Webots recognition for ilmenite boxes, then return to the lander pad

Keyboard teleop remains `controllers/sawppy_drive` if you switch the Sawppy `controller` field back.

Neither controller holds keys or calls RPC. Economic state lives under `webots/rover/controllers/lunar_economy/` (see that README). The prospector also mirrors work events to `prospecting/peaq_events.jsonl` for the ground segment.

## Machine-to-machine flow (control on the Moon, signing on Earth)

```
  [lander-1]  job_posted + escrow_committed  ──►  lunar_economy/
  [prospector-1]  drive + sample_found       ──►  settlement_intent (release_discovery)
                                                      │
  Earth: packages/settler  ◄── same folder (synced) ──┘
           signs AGUNG: lander wallet → prospector wallet
           anchors prospector events on peaq agung
```

A field machine earns into **its own wallet** when the lunar bus records a verified discovery and a release intent. The **buyer is lander-1**, which posted the job and committed escrow on the surface. Earth only runs signing policy (Dynamic server wallet for `lander-1`); it does not steer the rover.

In production, the lunar folder is the surface mesh; chain settlement trails the 1.3 s link. In the demo, Webots and the settler share one filesystem.

## Settler (ground segment)

Python 3.10+ (Webots controller Python is 3.9 and cannot load `peaq-os-sdk`).

```
cd packages/settler
copy .env.example .env
pip install -r requirements.txt
npm install
python settler.py
```

- **Worker wallet:** `PEAQOS_*` / `config/wallets.json` — prospector-1 payee.
- **Buyer wallet:** `LANDER_DYNAMIC_ACCOUNT_ADDRESS` — lander-1 payer for escrow releases.
- **Optional gas:** `DYNAMIC_ACCOUNT_ADDRESS` funds the worker wallet on startup via `fund.mjs`.

The settler tails `lunar_economy/settlement_intents.jsonl` and pays only when an intent matches a registered `job_posted` and escrow balance. It separately tails `peaq_events.jsonl` for peaq activity anchors.

Never commit `.env`, wallet files, or runtime lunar bus logs.

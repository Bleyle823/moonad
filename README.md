# moonad

Moon rover for the lunar machine economy

Webots Sawppy port of `ros2_rover` (drive, teleop, moon and Mars worlds): `webots/rover/`.
The live prospecting run is that Sawppy in `webots/rover/worlds/moon.wbt`. An earlier short demo sits in `webots/lunar_prospecting/`.

## Prospecting (Sawppy)

Open `webots/rover/worlds/moon.wbt` in Webots R2025a. The robot controller is `prospecting`.

The chassis is the six-wheel, four-steer Sawppy. The contest stack’s behaviour sits on top of that drive:

- A* around rocks on a 0.5 m grid (`algorithm/global_planner.py`)
- Slow down when the forward view has few features (`algorithm/odometer.py`, `algorithm/vehicle.py`)
- Stop and replan on a close depth window (`algorithm/detecter.py`)
- Orange HSV plus Webots recognition for ilmenite boxes, then return to the lander pad

Keyboard teleop remains `controllers/sawppy_drive` if you switch the world’s controller field back.

The controller appends `machine_online`, `traverse`, `sample_found`, and `sample_delivered` to `webots/rover/controllers/prospecting/peaq_events.jsonl`. It does not hold keys or call RPC.

## Settler (peaq + Dynamic)

A separate process on Python 3.10+ tails that log. Webots controller Python is 3.9 and cannot load `peaq-os-sdk`.

```
cd packages/settler
copy .env.example .env
pip install -r requirements.txt
python settler.py
```

Fill `PEAQOS_*` for agung (chain id `9990`). Tokenomics 1.0 constructor addresses are in `.env.example`. `TOKENOMICS_DEPLOYMENT_ID=agung-2026-08-28` selects the Economics 2.0 snapshot. If registration is paused or a call reverts, the settler prints the event and the reason and leaves the local log as the record.

Dynamic is the Earth-side owner wallet on the same chain. Optional:

```
cd packages/settler
npm install
```

Set `DYNAMIC_AUTH_TOKEN`, `DYNAMIC_ENVIRONMENT_ID`, and `DYNAMIC_ACCOUNT_ADDRESS`. On start, `settler.py` runs `fund.mjs`, which uses Dynamic `getWalletClient({ chainId: 9990, rpcUrl })` to send AGUNG to the machine address.

Never commit `.env`, `config/wallets.json`, or the event log.

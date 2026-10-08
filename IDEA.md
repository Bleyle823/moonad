# MOONAD: a lunar rover that earns, trades with other machines, and is owned by people on Earth

> One rover. One onchain identity. Thousands of co-owners. Paid by the job.

## The pitch

Every lunar mission so far has been a government or company spending money and
getting data back. MOONAD flips that. A rover is born onchain, with its own identity,
wallet and credit record. It does paid work on the lunar surface. It buys what it needs
from other machines. The people who funded it share in what it earns.

The parking-lot argument applies here at an extreme. A lunar rover costs millions, works a
fraction of the lunar day, and sits dormant through the 14-day lunar night. Idle capacity
that expensive is a strong case for letting the machine sell its time to many customers
and be financed by many owners, instead of being a single-purpose government asset.

**Claim to make carefully:** "first onchain rover on the Moon" is a milestone to earn, not a
fact to assert today. See "Honest framing" below.

## The loop (what the rover actually does)

```
Earth co-owners fund the rover
        |
        v
Rover has an onchain identity (peaqID / Machine NFT) + wallet
        |
        +--> accepts a paid task (survey a crater, haul regolith, relay a signal)
        |       buyer opens an Escrow claim, both sides stake
        |
        +--> buys services from other machines (power, compute, comms relay)
        |
        +--> signs its sensor data at capture; buyers verify, then pay
        |
        v
Validator machine (inspector rover / orbiter) attests the job was done
        |
        v
Escrow releases payment -> revenue splits to the co-owners automatically
        |
        v
Every job lands in the rover's onchain record -> Machine Credit Rating improves
        -> cheaper financing for the next rover
```

## Why this fits peaq (and what each piece does)

| Need | peaq primitive | Status per the docs |
| --- | --- | --- |
| Rover has an identity and wallet | peaqOS Activate: peaqID, omnichain wallet, Machine NFT | Live (registration marked paused at time of research; check before building) |
| Pay and get paid per task, with stakes | peaq Escrow (ERC-8004, ClaimRegistry on peaq, BaseEscrow on Base, LayerZero sync) | Live on agung testnet |
| Rover finds and buys power, compute, relay | peaqOS Scale (agent pairing, delegation limits, x402) | Live |
| Data that can't be faked | peaqOS Stream: Edge Agent signs and encrypts at capture (ROS 2) | Live; buyer purchase routes return 404 today |
| "Proof the machine is genuine" | peaqOS Verify | Beta; one chip family only |
| Reputation, "did this job really happen" | ERC-8004 Reputation + Validation registries | Live |
| A credit record lenders can read | peaqOS Qualify: Machine Credit Rating, AAA to NR | Live; trust level 2 (hardware-signed) weighs most |
| Fractional ownership | Tokenize | **Not shipped.** See below |

### Co-ownership: the part we build ourselves

peaq's Tokenize function is announced but has no shipped product. What does exist: under
Economics 2.0 the Machine NFT is an ERC-721 whose token ID *is* the machine ID, and
transferring it moves ownership of the machine.

So MOONAD builds a **RoverVault** contract:

1. The rover's Machine NFT is locked in the vault.
2. The vault mints fungible **share tokens** (ERC-20) to co-owners, sold in a fixed-price sale.
3. Rover revenue (stablecoin) is deposited to the vault and distributed pro rata. Shares stay
   transferable and the accounting follows them, so past revenue does not leak to new buyers.
4. Operators (the mission team) hold a founder allocation, minted at launch.

That is the "co-owned by people on Earth" half of the idea, and it is a real contribution
because the official primitive does not exist yet.

## The 1.3-second problem, and why it's a feature

The Earth-Moon one-way delay is about 1.3 seconds, with comms blackouts on top. A chain
cannot sit in a control loop.

- The rover and nearby machines run **locally and autonomously**.
- peaq is the **settlement and trust layer**: identity, escrow, reputation, credit.
- For blackouts, machines sign payment intents locally and settle among themselves over a
  local mesh. The batch anchors to peaq when the Earth link returns (the delay-tolerant
  settlement gateway). This is the technically distinctive part of the project.

## Roles in the lunar economy

| Machine | Job | Earns / pays |
| --- | --- | --- |
| **Rover (the star)** | Surveys, hauls, builds; sells signed data | Earns per task; pays for power and comms |
| Power cart / solar tower | Sells kWh, especially in the lunar night | Earns per kWh |
| Relay orbiter / comms node | Sells bandwidth windows | Earns per window |
| Inspector rover | Posts a Validation Registry attestation that a job was done | Earns a validation fee; reputation at stake |
| Edge-compute node | Runs inference for the rover (no cloud 1.3 s away) | Earns per answer over x402 |
| Earth buyers | Space agencies, researchers, resource companies | Pay for tasks and data |

## MVP (what we can really show)

A **digital-twin lunar rover** that behaves exactly as the real one would, with real onchain
state:

- A Webots simulation of a lunar surface with the rover, a power cart and an inspector.
- Each machine gets an ERC-8004 identity on peaq agung testnet.
- A buyer posts a survey task as an Escrow claim. The rover accepts and stakes, signs its data
  with the Edge Agent, the inspector attests, and payment releases.
- Revenue flows into the RoverVault and splits to co-owners; a dashboard shows shares, claims
  and the rating trend.
- Clear labels on screen for what is a live peaq call and what is mocked.

**Hardware path afterwards:** an analog rover on a terrestrial regolith simulant bed, with a
secure element (Infineon OPTIGA Trust M Express, the one chip Verify supports), then a payload
slot on a commercial lander mission.

## Honest framing (important for credibility)

- **We do not have a rover on the Moon.** The MVP is a faithful simulation plus a plan.
  Say "the first onchain-native lunar rover design," not "the first rover on the Moon."
- Several peaq pieces are early: Tokenize is unshipped, Stream purchase routes are not serving
  yet, Verify supports one chip, Monetize v1 covers compute only. We build around those or
  mock them, and label it.
- Flight electronics need radiation-tolerant parts; a secure element is not automatically
  flight-qualified.
- **Legal:** selling shares of a revenue-earning machine looks like a securities offering in
  many places, and lunar resource activity sits under the Outer Space Treaty and national
  licensing. Treat the vault as a testnet prototype until counsel signs off. Sell data and
  services first; sell ownership last.

## Lessons from "payments in space" (WIRED) and how they change the design

Source: a WIRED feature on off-world finance. Its points that matter here, and what we do
about each:

| What the article says | Design change |
| --- | --- |
| Earth-Moon delay is at least 2-3 s round trip; card-style transactions time out | No transaction waits on Earth. Local machines settle locally first (see "Local ledger, Earth anchor") |
| Earth-Moon data is expensive (relay satellites, antennas); phoning home for each payment could cost more than the goods | Batch and net payments. Anchor only a Merkle root plus net balances to peaq, never raw data or per-payment messages |
| Off-world payments will likely need a local banking entity that later syncs to an Earth ledger; a blockchain can serve as the intermediate record and help prevent fraud across places and times | This is exactly MOONAD's architecture. peaq is the Earth-side record; a local gateway is the "lunar branch" |
| JPMorgan (Kinexys) and GomSpace ran blockchain on LEO satellites and moved value between two of them. Limits: satellite power and memory, and the need for constant sync | Our two-satellite phase is a direct, differentiated follow-up: add identity, escrow, reputation, credit and co-ownership. Use light clients on the satellites (signatures only) and keep heavy chain logic on the ground |
| Value off-world will centre on consumables: oxygen, water, power. Credits backed by them may form a currency | Add resource-backed credits (see below) |
| LEO already has internet and uses Earth payment rails; tourists mostly prepay | Do not pitch LEO payments for tourists. Pitch the LEO satellites as a **testbed for off-world settlement**, sold to agencies, station operators and banks |
| Outer Space Treaty bars sovereign claims; nations answer for their private entities | Sell services, data and machine ownership, never territory. A licensed operator company, not a DAO, must be the legally responsible party |
| Mars-style blackouts can last days or weeks | Same mechanism as lunar far-side or relay outages: pre-funded budgets plus signed intents that settle on reconnect |

### Local ledger, Earth anchor (the core mechanism)

Machines near each other settle between themselves and report to Earth in batches.

1. **Pre-funded allowance.** Before a machine goes out of contact, a buyer or the vault locks
   funds on Earth (a peaq escrow or a spending policy with per-transaction and daily limits,
   which peaqOS Scale already supports). The machine can spend up to that cap and no more.
2. **Local signed updates.** Two machines in radio range exchange signed balance updates
   (a bilateral payment channel). Each update carries a sequence number so older ones lose.
3. **Anchor.** When a link to Earth exists, the gateway submits the latest signed state and a
   Merkle root of the batch. peaq settles the net amount, releases stakes, and writes the
   reputation and rating events.
4. **Disputes.** If two states conflict, the highest-sequence state signed by both parties
   wins; the loser's stake is at risk.

Why the allowance matters: without it, two disconnected ledgers can double-spend the same
funds. A pre-funded cap removes that risk by design, because you can never spend more than
was locked.

**Open question to test:** the article notes satellites have limited power and memory. We
must measure signing cost on a flight-class microcontroller before promising this works.

### Resource-backed credits (stretch, after the core works)

A local unit of account minted against *verified production* and redeemable for the physical
thing: kWh of power, kg of oxygen, kg of water ice. The rover and power cart sign their output
(Stream, hardware-signed events weigh most in the rating). Credits are minted only against
those signed outputs. Stablecoins stay the Earth-facing money; credits are the local one.
Risks: oracle and fraud design, and legal classification. Prototype on testnet only.

### The satellite testbed, repositioned

Two co-owned LEO satellites are not "a cheaper rover." They are the **first public test of
the off-world settlement layer**: independent witnessing of data, escrow-paid tasking,
bilateral channels, and anchoring after blackout. Metrics worth publishing: per-payment data
cost, time to final settlement after reconnect, number of conflicts, and signing power draw.
These numbers are what agencies and banks will actually ask for.

## Roadmap

**Phase 0: software simulation (weeks 1-4)**
1. RoverVault (rename to AssetVault) contract and tests; agent identities on agung; one
   escrow task end to end.
2. Two simulated satellites plus a gateway with pass-window delays; pre-funded allowance and
   a bilateral channel; anchor to agung.
3. Webots lunar scene; Edge Agent signing; inspector validation; dashboard.

**Phase 1: orbit (12-24 months)**
4. Balloon test of the signing hardware, then two small satellites (payloads: secure element
   and GNSS, radiation and magnetometer sensors, camera; stretch: relay or onboard compute).
5. Publish the settlement-layer metrics above. Talk to agencies and station operators.

**Phase 2: lunar (later)**
6. Rideshare or lander payload through a partner; delay-tolerant gateway with a relay.

**Phase 3: the rover**
7. Analog rover on a regolith bed, then a flight slot, then resource-backed credits and a
   licensed operator structure for co-owners.

## One-line version

*A lunar rover that is born onchain, does paid work, pays its machine neighbours, builds a
credit record, and shares its earnings with thousands of owners on Earth.*

## Status of this repo

- Hardhat + OpenZeppelin installed; `hardhat.config.js` targets peaq agung.
- Next to write: `contracts/AssetVault.sol` (+ mocks and tests), then the gateway, the two
  simulated satellites with payment channels, and the Webots world.

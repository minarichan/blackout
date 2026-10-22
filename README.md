# Blackout

Blackout is a small risk desk for lending books spread across chains.

Paste a wallet. It reads Aave v3 and Compound v3 on Ethereum, Arbitrum, Base and Optimism, then tells you which account is closest to getting liquidated. Balances are there, but they are not the point. The point is health, how far the book is from a liquidation and whether one asset, one chain or one protocol is carrying too much of it.

Collateral in one account does not back debt in another. Aave on Arbitrum and Compound on Base are separate. Because of that, a single portfolio health factor can look fine while one account is close to the edge. Blackout leads with the worst account.

There is a demo book if you want to click around before pointing it at a real wallet. The positions are made up. The math is the same math a live wallet goes through.

## How to read the screen

Health is collateral value times each asset's liquidation threshold, divided by debt. Under 1.0, the account can be liquidated. When Aave reports its own health factor, that number is the one on screen, because that is the number liquidations actually use.

Two distances sit next to health, and they are not the same thing. Collateral drawdown is how far the collateral basket can fall together before liquidation: `(health − 1) / health`. Debt expansion is how far the debt basket can rise: `health − 1`. Borrowing ETH against stables gets worse when ETH goes up. Posting ETH and borrowing stables gets worse when ETH goes down.

The liquidation price on a single row moves only that asset and holds the rest still. Stress is a handful of set scenarios — ETH down 15% and 20%, ETH up 20%, BTC down 20%, a broader selloff, and a small USDC depeg. They are what-ifs, not a correlation model.

Concentration is the share of collateral or debt in one asset, one protocol, one chain or one factor (ETH, BTC, stables and so on). HHI squashes the asset shares into one number. 1.00 means the whole side is a single name.

Prices need a second look. The protocol oracle is what health and liquidation use. Chainlink (ETH and BTC, on Ethereum) and a one-dollar peg for stables are only a reference. If they disagree, the row is marked divergent and the protocol price stays. If the oracle is missing, Chainlink or CoinGecko can fill the gap, and the row is marked fallback so you can see that health is leaning on a substitute. A Chainlink round older than a day is ignored. Staked ETH is not compared with spot ETH, because the premium would look like a broken oracle.

## What it covers right now

Ethereum, Arbitrum, Base and Optimism. Aave v3 core markets and Compound v3 base-asset markets.

Perps, restaking and wallet login are not in this version. Nothing here sends a transaction. It only reads.

## Run it

You need Python 3.12 and Node 20 or newer. The database is SQLite. You do not need Redis.

```powershell
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

```powershell
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173. Load the demo book or paste a wallet that actually has Aave or Compound positions. The API docs live at http://127.0.0.1:8000/docs. `scripts/run_local.ps1` starts both processes.

Public RPCs are filled in already, which is fine for trying it. The first live read often takes 10–30 seconds. If you leave it running, put your own endpoints in `.env`. There is an example in `.env.example`.

Docker is the other way:

```powershell
docker compose up --build
```

The desk is on http://localhost:8080 and the API is on http://localhost:8000.

## API

`demo` works anywhere an address does. `?refresh=true` skips the short cache.

| Method | Path | |
| --- | --- | --- |
| GET | `/health` | Process is up. This does not call the chains. |
| GET | `/protocols` | Chains and markets this process will read. |
| GET | `/portfolio/{address}` | Positions, health, concentration, stress, alerts. |
| GET | `/portfolio/{address}/positions` | The normalized positions. |
| GET | `/portfolio/{address}/risk` | Health, concentration, and stress. |
| GET | `/portfolio/{address}/alerts` | What crossed a threshold. |
| GET | `/portfolio/{address}/history` | Recent snapshots for this address. |
| POST | `/watchlist` | Save an address. Body: `{ "address", "label" }`. |
| GET | `/watchlist` | Saved addresses. |
| DELETE | `/watchlist/{address}` | Remove one. |

## Tests

```powershell
cd backend
python -m pytest
```

The risk and price tests do not need a network. `scripts/smoke_rpc.py` checks that the configured RPCs can still see Aave reserve lists and Compound base tokens.

## Where things live

`backend/app/adapters` talks to Aave, Compound, Chainlink and CoinGecko. `backend/app/core` is the health, distance, concentration, stress and alert math. `backend/app/api` is the HTTP surface. `frontend/src` is the desk.

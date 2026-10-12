# Blackout

Cross-chain lending risk for Aave v3 and Compound v3. Blackout reads collateral and debt on Ethereum, Arbitrum, Base and Optimism, then shows which account is closest to liquidation.

It is a risk desk, not a portfolio tracker. Health is calculated inside each lending account. Collateral is not shared across protocols or chains. The debt-weighted portfolio health factor is a summary and can hide one weak account. The worst health factor is the liquidation signal.

## What the numbers mean

- **Health factor** is `sum(collateral value × liquidation threshold) / debt`. Under 1.0 is liquidatable. Aave's own health factor is the headline when the protocol reports one, because that is the figure liquidations use.
- **Collateral drawdown** is `(health − 1) / health`: how far the collateral basket can fall together before liquidation.
- **Debt expansion** is `health − 1`: how far the debt basket can rise. A book that borrows ETH against stables is hurt by ETH going up.
- **Isolated liquidation price** moves one asset and holds the others still.
- **Stress** reprices ETH, BTC, alts and a USDC depeg, then recomputes health. These are scenarios, not a full correlation model.
- **Concentration** is the share of collateral or debt in one asset, chain, protocol or factor bucket (ETH, BTC, stables).

## MVP coverage

| | |
| --- | --- |
| Chains | Ethereum, Arbitrum, Base, Optimism |
| Protocols | Aave v3 core markets, Compound v3 base-asset markets |
| Not in this version | Perps margin, restaking, ML correlation, wallet-signature auth |

The demo book is a fixture. It runs through the same risk engine as a live wallet so the dashboard can be reviewed without RPC access.

## Run locally

Python 3.12 and Node 20+ are enough. SQLite is the default database. Redis is not required.

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

Open http://127.0.0.1:5173 and load the demo book, or paste a wallet that has Aave v3 or Compound v3 positions.

`scripts/run_local.ps1` starts both processes. API docs are at http://127.0.0.1:8000/docs.

Public RPCs are configured by default. For a deployment, set your own endpoints in `.env` (see `.env.example`). The first live read can take 10–30 seconds.

## Docker

```powershell
docker compose up --build
```

The app is published on http://localhost:8080. The API is on http://localhost:8000.

## API

| Method | Path | |
| --- | --- | --- |
| GET | `/health` | Process health. Does not probe RPCs. |
| GET | `/protocols` | Chains and markets enabled in this process. |
| GET | `/portfolio/{address}` | Positions, account risk, concentration, stress, and alerts. |
| GET | `/portfolio/{address}/positions` | Normalized positions. |
| GET | `/portfolio/{address}/risk` | Health, concentration, and stress. |
| GET | `/portfolio/{address}/alerts` | Threshold and correlation alerts. |
| GET | `/portfolio/{address}/history` | Recent risk snapshots. |
| POST | `/watchlist` | Save an address. Body: `{ "address", "label" }`. |
| GET | `/watchlist` | Saved addresses. |
| DELETE | `/watchlist/{address}` | Remove an address. |

Use `demo` as the address for the fixture book. Add `?refresh=true` to skip the short response cache.

## Tests

```powershell
cd backend
python -m pytest
```

Risk math is covered without a network. `scripts/smoke_rpc.py` checks that the configured RPCs can read Aave reserve lists and Compound base tokens.

## Layout

```
backend/app/adapters    Aave v3, Compound v3, Chainlink, CoinGecko
backend/app/core        Health, distance, concentration, stress, alerts
backend/app/api         REST routes
frontend/src            Risk dashboard
```

Protocol oracle prices are what liquidation uses. Chainlink (ETH and BTC on Ethereum) and CoinGecko only fill a missing price or flag a divergence. They do not replace the protocol price.

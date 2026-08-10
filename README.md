# Global Economic Complexity Investment Scanner

A finance-grade research application that ranks countries using productive complexity, capability momentum and macro investability, then surfaces adjacent high-complexity product opportunities.

## Core question

**Which economies are building increasingly sophisticated productive capabilities, and which adjacent sectors appear structurally feasible for them to enter next?**

Economic complexity is used as a structural lens, not a short-term market-return model.

## Data sources

### Harvard Growth Lab Atlas of Economic Complexity
The Atlas GraphQL adapter requests ECI, export values, product RCA, product complexity, product distance, Complexity Outlook Gain and HS92 product metadata.

### World Bank Indicators API
The macro layer requests GDP growth, CPI inflation, FDI/GDP, public debt/GDP when available, exports/GDP and listed market capitalization/GDP when available.

## Structural Investment Score

A 0–100 **cross-sectional ranking heuristic**, not probability or expected return.

| Component | Weight |
|---|---:|
| ECI level | 30% |
| ECI momentum | 20% |
| GDP growth | 15% |
| FDI / GDP | 12% |
| Inflation stability | 10% |
| Market depth | 8% |
| Export scale | 5% |

Missing macro fields are reweighted across the available components rather than filled with zero.

Classifications:
- 80–100: Structural Leader
- 65–79.9: Emerging Compounder
- 50–64.9: Watchlist
- Below 50: Early / Fragile

## Product adjacency score

Products with RCA below 1 are ranked by:
- 50% product complexity percentile
- 35% capability proximity percentile, lower Atlas distance is better
- 15% Complexity Outlook Gain percentile

## Guardrails

- No investment probability is produced.
- No valuation signal is inferred from complexity.
- No missing economic-complexity data are fabricated.
- Risk flags are descriptive thresholds only.
- Country rankings depend on the comparison universe.
- This is research software, not investment advice.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest -q
uvicorn app:app --reload
```

## API

- `GET /health`
- `GET /snapshot`
- `GET /countries`
- `GET /country/{iso3}`
- `GET /methodology`
- `GET /docs`

## Production hardening roadmap

1. Persist scheduled country snapshots instead of recomputing the universe on demand.
2. Add provider-schema contract tests for Atlas GraphQL.
3. Add export diversification and concentration metrics.
4. Add sovereign accessibility, FX liquidity and governance-risk layers.
5. Backtest whether ECI changes and product adjacency contain information for subsequent country equity, FX, sovereign spread or FDI outcomes.
6. Keep the structural score and any future market-return model as separate outputs.

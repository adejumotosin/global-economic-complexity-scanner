from __future__ import annotations

import re
import time
import requests
import pandas as pd

from .config import ATLAS_GRAPHQL_URL, WORLD_BANK_API, Settings, WB_INDICATORS

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "Global-Economic-Complexity-Scanner/0.1 research"})

class ProviderError(RuntimeError):
    pass

def _numeric_country_id(value) -> int:
    """Normalize Atlas country IDs such as 156 or 'country-156' to numeric M49-style IDs."""
    if isinstance(value, int):
        return value
    text = str(value or "").strip()
    if text.isdigit():
        return int(text)
    match = re.search(r"(?:^|[-_])(\d+)$", text)
    if match:
        return int(match.group(1))
    raise ProviderError(f"Unrecognized Atlas country ID format: {text[:40] or 'empty'}")

def _graphql(query: str, timeout: int) -> dict:
    try:
        r = _SESSION.post(
            ATLAS_GRAPHQL_URL,
            json={"query": query},
            timeout=timeout,
            headers={"Content-Type": "application/json"},
        )
        r.raise_for_status()
        payload = r.json()
    except (requests.RequestException, ValueError) as exc:
        raise ProviderError(f"Atlas API request failed: {type(exc).__name__}") from exc
    if payload.get("errors"):
        msg = payload["errors"][0].get("message", "GraphQL error")
        raise ProviderError(f"Atlas GraphQL error: {msg}")
    return payload.get("data") or {}

def atlas_locations(settings: Settings) -> list[dict]:
    data = _graphql("""
    {
      locationCountry {
        countryId
        iso3Code
        nameEn
      }
    }
    """, settings.request_timeout_seconds)
    return data.get("locationCountry") or []

def atlas_country_history(settings: Settings) -> pd.DataFrame:
    locations = atlas_locations(settings)
    by_iso = {
        str(x.get("iso3Code") or "").upper(): x
        for x in locations
        if x.get("iso3Code") and x.get("countryId") is not None
    }
    targets = [(iso, by_iso[iso]) for iso in settings.universe if iso in by_iso]
    rows: list[dict] = []
    y0 = settings.trade_year - settings.history_years
    fields = "year gdp gdppc population exportValue importValue eci"

    for start in range(0, len(targets), settings.atlas_batch_size):
        batch = targets[start:start + settings.atlas_batch_size]
        chunks, alias_map = [], {}
        for i, (iso, meta) in enumerate(batch):
            alias = f"c{i}"
            numeric_id = _numeric_country_id(meta["countryId"])
            alias_map[alias] = (iso, meta, numeric_id)
            chunks.append(
                f'{alias}: countryYear(countryId: {numeric_id}, '
                f'yearMin: {y0}, yearMax: {settings.trade_year}) {{ {fields} }}'
            )
        data = _graphql("{\n" + "\n".join(chunks) + "\n}", settings.request_timeout_seconds)
        for alias, series in data.items():
            iso, meta, numeric_id = alias_map.get(alias, ("", {}, None))
            for obs in series or []:
                rows.append({
                    "iso3": iso,
                    "country": meta.get("nameEn") or iso,
                    "country_id": numeric_id,
                    **obs,
                })
        time.sleep(0.05)
    return pd.DataFrame(rows)

def world_bank_country_metadata(settings: Settings) -> pd.DataFrame:
    try:
        r = _SESSION.get(
            f"{WORLD_BANK_API}/country",
            params={"format": "json", "per_page": 400},
            timeout=settings.request_timeout_seconds,
        )
        r.raise_for_status()
        payload = r.json()
    except (requests.RequestException, ValueError) as exc:
        raise ProviderError(f"World Bank country metadata request failed: {type(exc).__name__}") from exc
    records = payload[1] if isinstance(payload, list) and len(payload) > 1 else []
    rows, wanted = [], set(settings.universe)
    for x in records or []:
        iso = str(x.get("id") or "").upper()
        if iso not in wanted:
            continue
        rows.append({
            "iso3": iso,
            "region": (x.get("region") or {}).get("value"),
            "income_level": (x.get("incomeLevel") or {}).get("value"),
            "capital": x.get("capitalCity"),
            "longitude": x.get("longitude"),
            "latitude": x.get("latitude"),
        })
    return pd.DataFrame(rows)

def world_bank_indicators(settings: Settings) -> pd.DataFrame:
    countries = ";".join(settings.universe)
    indicators = ";".join(WB_INDICATORS.values())
    params = {
        "format": "json",
        "source": 2,
        "date": f"{settings.trade_year - 5}:{settings.trade_year}",
        "per_page": 20000,
    }
    try:
        r = _SESSION.get(
            f"{WORLD_BANK_API}/country/{countries}/indicator/{indicators}",
            params=params,
            timeout=settings.request_timeout_seconds,
        )
        r.raise_for_status()
        payload = r.json()
    except (requests.RequestException, ValueError) as exc:
        raise ProviderError(f"World Bank indicator request failed: {type(exc).__name__}") from exc
    records = payload[1] if isinstance(payload, list) and len(payload) > 1 else []
    reverse = {v: k for k, v in WB_INDICATORS.items()}
    rows = []
    for x in records or []:
        code = (x.get("indicator") or {}).get("id")
        iso = str(x.get("countryiso3code") or "").upper()
        value = x.get("value")
        year_text = str(x.get("date", ""))
        year = int(year_text) if year_text.isdigit() else None
        if code not in reverse or iso not in settings.universe or value is None or year is None or year > settings.trade_year:
            continue
        rows.append({
            "iso3": iso,
            "indicator": reverse[code],
            "year": year,
            "value": float(value),
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["iso3", *WB_INDICATORS.keys()])
    latest = (
        df.sort_values(["iso3", "indicator", "year"])
          .groupby(["iso3", "indicator"], as_index=False)
          .tail(1)
    )
    wide = latest.pivot(index="iso3", columns="indicator", values="value").reset_index()
    wide.columns.name = None
    return wide

def atlas_product_opportunities(country_id: int, settings: Settings) -> tuple[pd.DataFrame, pd.DataFrame]:
    numeric_id = _numeric_country_id(country_id)
    query = f"""
    {{
      products: productHs92(productLevel: {settings.product_level}) {{
        productId
        code
        nameEn
        clusterId
        naturalResource
        greenProduct
      }}
      country: countryProductYear(
        countryId: {numeric_id}
        productClass: HS92
        productLevel: {settings.product_level}
        yearMin: {settings.trade_year}
        yearMax: {settings.trade_year}
      ) {{
        productId
        year
        exportValue
        exportRca
        globalMarketShare
        distance
        cog
        normalizedPci
      }}
    }}
    """
    data = _graphql(query, settings.request_timeout_seconds)
    return pd.DataFrame(data.get("country") or []), pd.DataFrame(data.get("products") or [])

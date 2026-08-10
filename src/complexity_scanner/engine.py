from __future__ import annotations

import time
import numpy as np
import pandas as pd

from .config import SETTINGS, Settings
from .providers import ProviderError, atlas_country_history, atlas_product_opportunities, world_bank_country_metadata, world_bank_indicators
from .scoring import build_country_scores, rank_product_opportunities, current_advantages

_CACHE: dict[str, tuple[float, object]] = {}

def _clean(value):
    if value is None: return None
    if isinstance(value, (np.floating, float)):
        if np.isnan(value) or np.isinf(value): return None
        return round(float(value), 4)
    if isinstance(value, (np.integer, int)): return int(value)
    if isinstance(value, list): return [_clean(x) for x in value]
    return value

def _record(row: pd.Series) -> dict:
    fields = [
        "rank","iso3","country","country_id","year","eci","eci_change_5y",
        "structural_score","classification","investment_lens","region","income_level",
        "gdp_growth","inflation","fdi_gdp","debt_gdp","exports_gdp","market_cap_gdp",
        "eci_percentile","momentum_percentile","macro_percentile","exportValue","gdppc",
        "risk_flags"
    ]
    return {k:_clean(row.get(k)) for k in fields}

def run_scanner(settings: Settings = SETTINGS, force: bool = False) -> dict:
    key = f"scanner:{settings.trade_year}"
    now = time.time()
    cached = _CACHE.get(key)
    if cached and not force and now-cached[0] < settings.cache_ttl_seconds:
        return cached[1]

    errors = {}
    try: history = atlas_country_history(settings)
    except Exception as exc:
        errors["atlas"] = str(exc); history = pd.DataFrame()
    try: macro = world_bank_indicators(settings)
    except Exception as exc:
        errors["world_bank_indicators"] = str(exc); macro = pd.DataFrame()
    try: meta = world_bank_country_metadata(settings)
    except Exception as exc:
        errors["world_bank_metadata"] = str(exc); meta = pd.DataFrame()

    if history.empty:
        raise ProviderError("Economic complexity data are unavailable. Atlas provider returned no usable country history.")

    scored = build_country_scores(history, macro, meta, settings.trade_year)
    records = [_record(row) for _, row in scored.iterrows()]
    result = {
        "status":"ok",
        "trade_year":settings.trade_year,
        "universe_size":len(records),
        "methodology_version":"0.1",
        "score_semantics":"Cross-sectional structural investment ranking heuristic. It is not a return forecast, valuation signal, or probability of investment success.",
        "countries":records,
        "top_five":records[:5],
        "regions":sorted({r.get("region") for r in records if r.get("region")}),
        "provider_errors":errors,
        "data_notes":{
            "complexity_source":"Harvard Growth Lab Atlas of Economic Complexity GraphQL API",
            "macro_source":"World Bank Indicators API",
            "trade_classification":"HS92 / country economic complexity",
            "score_components":{"ECI level":.30,"ECI momentum":.20,"GDP growth":.15,"FDI / GDP":.12,"inflation stability":.10,"market depth":.08,"export scale":.05}
        }
    }
    _CACHE[key] = (now, result)
    return result

def country_detail(iso3: str, settings: Settings = SETTINGS, force: bool = False) -> dict:
    iso3 = iso3.upper()
    scanner = run_scanner(settings, force=force)
    base = next((x for x in scanner["countries"] if x["iso3"] == iso3), None)
    if not base: raise KeyError(f"Country {iso3} is not in the scanner universe")
    cache_key = f"country:{iso3}:{settings.trade_year}"
    now = time.time()
    cached = _CACHE.get(cache_key)
    if cached and not force and now-cached[0] < settings.cache_ttl_seconds:
        return cached[1]
    errors = {}
    try:
        country, products = atlas_product_opportunities(int(base["country_id"]), settings)
        opportunities = rank_product_opportunities(country, products)
        advantages = current_advantages(country, products)
    except Exception as exc:
        errors["atlas_products"] = str(exc)
        opportunities, advantages = pd.DataFrame(), pd.DataFrame()

    def recs(df):
        return [{k:_clean(v) for k,v in rec.items()} for rec in df.to_dict(orient="records")]

    detail = {
        "country":base,
        "adjacent_opportunities":recs(opportunities),
        "revealed_advantages":recs(advantages),
        "product_methodology":"Adjacent opportunities are products where RCA is below 1, then ranked by product complexity, capability proximity (lower distance), and complexity outlook gain. This is a structural capability heuristic, not an expected-return forecast.",
        "provider_errors":errors,
    }
    _CACHE[cache_key] = (now, detail)
    return detail

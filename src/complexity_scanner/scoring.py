from __future__ import annotations

import math
import numpy as np
import pandas as pd

def percentile(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    out = pd.Series(np.nan, index=s.index, dtype=float)
    valid = s.dropna()
    if valid.empty:
        return out
    ranked = valid.rank(method="average", pct=True)
    if not higher_is_better:
        ranked = 1.0 - ranked + (1.0 / len(valid))
    out.loc[valid.index] = ranked.clip(0, 1) * 100
    return out

def inflation_stability(inflation: pd.Series, target: float = 3.0) -> pd.Series:
    x = pd.to_numeric(inflation, errors="coerce")
    return percentile((x - target).abs(), higher_is_better=False)

def _weighted_available(frame: pd.DataFrame, components: dict[str, float]) -> pd.Series:
    score = pd.Series(0.0, index=frame.index)
    weight = pd.Series(0.0, index=frame.index)
    for col, w in components.items():
        vals = pd.to_numeric(frame[col], errors="coerce")
        mask = vals.notna()
        score.loc[mask] += vals.loc[mask] * w
        weight.loc[mask] += w
    return (score / weight.replace(0, np.nan)).clip(0, 100)

def classify_score(score: float | None) -> str:
    if score is None or not math.isfinite(float(score)):
        return "Unscored"
    score = float(score)
    if score >= 80: return "Structural Leader"
    if score >= 65: return "Emerging Compounder"
    if score >= 50: return "Watchlist"
    return "Early / Fragile"

def risk_flags(row: pd.Series) -> list[str]:
    flags = []
    if pd.notna(row.get("inflation")) and float(row["inflation"]) > 12:
        flags.append("High inflation")
    if pd.notna(row.get("gdp_growth")) and float(row["gdp_growth"]) < 0:
        flags.append("Economic contraction")
    if pd.notna(row.get("eci_change_5y")) and float(row["eci_change_5y"]) < -0.25:
        flags.append("Complexity deterioration")
    if pd.notna(row.get("debt_gdp")) and float(row["debt_gdp"]) > 90:
        flags.append("High public debt")
    return flags

def investment_lens(row: pd.Series) -> str:
    eci, mom, macro = row.get("eci_percentile"), row.get("momentum_percentile"), row.get("macro_percentile")
    if pd.notna(eci) and eci >= 80 and pd.notna(mom) and mom >= 55:
        return "High-complexity compounder"
    if pd.notna(mom) and mom >= 75:
        return "Capability acceleration"
    if pd.notna(eci) and eci >= 70:
        return "Established productive base"
    if pd.notna(macro) and macro >= 70:
        return "Macro-supported transition"
    return "Selective structural watch"

def build_country_scores(history: pd.DataFrame, macro: pd.DataFrame, metadata: pd.DataFrame, trade_year: int) -> pd.DataFrame:
    if history.empty:
        return pd.DataFrame()
    h = history.copy()
    h["year"] = pd.to_numeric(h["year"], errors="coerce")
    h["eci"] = pd.to_numeric(h["eci"], errors="coerce")
    h["exportValue"] = pd.to_numeric(h["exportValue"], errors="coerce")
    latest = h[h["year"] <= trade_year].sort_values(["iso3","year"]).groupby("iso3", as_index=False).tail(1)
    first = h.sort_values(["iso3","year"]).groupby("iso3", as_index=False).head(1)[["iso3","eci","year"]]
    first = first.rename(columns={"eci":"eci_start","year":"eci_start_year"})
    df = latest.merge(first, on="iso3", how="left")
    df["eci_change_5y"] = df["eci"] - df["eci_start"]
    df["export_log"] = np.log1p(df["exportValue"].clip(lower=0))
    if not macro.empty: df = df.merge(macro, on="iso3", how="left")
    if not metadata.empty: df = df.merge(metadata, on="iso3", how="left")

    for col in ["gdp_growth","inflation","fdi_gdp","debt_gdp","exports_gdp","market_cap_gdp"]:
        if col not in df: df[col] = np.nan

    df["eci_percentile"] = percentile(df["eci"])
    df["momentum_percentile"] = percentile(df["eci_change_5y"])
    df["growth_percentile"] = percentile(df["gdp_growth"])
    df["fdi_percentile"] = percentile(df["fdi_gdp"])
    df["inflation_stability"] = inflation_stability(df["inflation"])
    df["export_scale_percentile"] = percentile(df["export_log"])
    df["market_depth_percentile"] = percentile(df["market_cap_gdp"])
    df["macro_percentile"] = _weighted_available(df, {
        "growth_percentile": .40,
        "fdi_percentile": .25,
        "inflation_stability": .20,
        "market_depth_percentile": .15,
    })
    df["structural_score"] = _weighted_available(df, {
        "eci_percentile": .30,
        "momentum_percentile": .20,
        "growth_percentile": .15,
        "fdi_percentile": .12,
        "inflation_stability": .10,
        "market_depth_percentile": .08,
        "export_scale_percentile": .05,
    })
    df["classification"] = df["structural_score"].map(classify_score)
    df["risk_flags"] = df.apply(risk_flags, axis=1)
    df["investment_lens"] = df.apply(investment_lens, axis=1)
    df = df.sort_values(["structural_score","eci"], ascending=False).reset_index(drop=True)
    df["rank"] = np.arange(1, len(df)+1)
    return df

def rank_product_opportunities(country: pd.DataFrame, products: pd.DataFrame, limit: int = 12) -> pd.DataFrame:
    if country.empty or products.empty: return pd.DataFrame()
    df = country.merge(products, on="productId", how="left")
    for col in ["exportRca","distance","cog","normalizedPci","exportValue","globalMarketShare"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    candidates = df[
        df["exportRca"].fillna(0).lt(1.0)
        & df["distance"].notna()
        & df["normalizedPci"].notna()
    ].copy()
    if candidates.empty: return candidates
    candidates["complexity_pct"] = percentile(candidates["normalizedPci"])
    candidates["proximity_pct"] = percentile(candidates["distance"], higher_is_better=False)
    candidates["cog_pct"] = percentile(candidates["cog"])
    candidates["opportunity_score"] = _weighted_available(candidates, {
        "complexity_pct": .50,
        "proximity_pct": .35,
        "cog_pct": .15,
    })
    candidates["opportunity_type"] = np.where(
        candidates["greenProduct"].fillna(False).astype(bool),
        "Green adjacency",
        "Capability adjacency",
    )
    keep = ["productId","code","nameEn","clusterId","naturalResource","greenProduct",
            "exportRca","distance","cog","normalizedPci","exportValue","globalMarketShare",
            "opportunity_score","opportunity_type"]
    return candidates.sort_values(["opportunity_score","normalizedPci"], ascending=False)[keep].head(limit).reset_index(drop=True)

def current_advantages(country: pd.DataFrame, products: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    if country.empty or products.empty: return pd.DataFrame()
    df = country.merge(products, on="productId", how="left")
    df["exportRca"] = pd.to_numeric(df["exportRca"], errors="coerce")
    df["exportValue"] = pd.to_numeric(df["exportValue"], errors="coerce")
    strong = df[df["exportRca"].fillna(0).ge(1.0)].copy()
    keep = ["productId","code","nameEn","exportRca","exportValue","greenProduct","naturalResource"]
    return strong.sort_values(["exportValue","exportRca"], ascending=False)[keep].head(limit).reset_index(drop=True)

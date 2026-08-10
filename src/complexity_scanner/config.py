from __future__ import annotations
from dataclasses import dataclass

ATLAS_GRAPHQL_URL = "https://atlas.hks.harvard.edu/api/graphql"
WORLD_BANK_API = "https://api.worldbank.org/v2"

DEFAULT_UNIVERSE = (
    "ARG","AUS","AUT","BEL","BGD","BRA","BGR","CAN","CHL","CHN","COL","CRI","CZE",
    "DNK","DOM","EGY","EST","FIN","FRA","DEU","GRC","HUN","IND","IDN","IRL","ISR",
    "ITA","JPN","KAZ","KEN","KOR","LVA","LTU","MYS","MEX","MAR","NLD","NZL","NGA",
    "NOR","PAK","PER","PHL","POL","PRT","ROU","SAU","SGP","SVK","SVN","ZAF","ESP",
    "SWE","CHE","THA","TUR","UKR","ARE","GBR","USA","URY","VNM"
)

WB_INDICATORS = {
    "gdp_growth": "NY.GDP.MKTP.KD.ZG",
    "inflation": "FP.CPI.TOTL.ZG",
    "fdi_gdp": "BX.KLT.DINV.WD.GD.ZS",
    "debt_gdp": "GC.DOD.TOTL.GD.ZS",
    "exports_gdp": "NE.EXP.GNFS.ZS",
    "market_cap_gdp": "CM.MKT.LCAP.GD.ZS",
}

@dataclass(frozen=True)
class Settings:
    trade_year: int = 2024
    history_years: int = 5
    product_level: int = 4
    cache_ttl_seconds: int = 6 * 60 * 60
    request_timeout_seconds: int = 25
    atlas_batch_size: int = 24
    universe: tuple[str, ...] = DEFAULT_UNIVERSE

SETTINGS = Settings()

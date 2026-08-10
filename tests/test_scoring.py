import pandas as pd
from complexity_scanner.scoring import percentile, classify_score, risk_flags, build_country_scores, rank_product_opportunities

def test_percentile_direction():
    s = pd.Series([1,2,3])
    assert percentile(s).iloc[-1] == 100
    assert percentile(s, higher_is_better=False).iloc[0] == 100

def test_classification_boundaries():
    assert classify_score(80) == "Structural Leader"
    assert classify_score(65) == "Emerging Compounder"
    assert classify_score(50) == "Watchlist"
    assert classify_score(49.9) == "Early / Fragile"

def test_risk_flags():
    flags = risk_flags(pd.Series({"inflation":18,"gdp_growth":-1,"eci_change_5y":-0.4,"debt_gdp":110}))
    assert set(["High inflation","Economic contraction","Complexity deterioration","High public debt"]).issubset(flags)

def test_country_score_bounded():
    history = pd.DataFrame([
        {"iso3":"AAA","country":"A","country_id":1,"year":2019,"eci":0.1,"exportValue":10},
        {"iso3":"AAA","country":"A","country_id":1,"year":2024,"eci":0.8,"exportValue":100},
        {"iso3":"BBB","country":"B","country_id":2,"year":2019,"eci":0.7,"exportValue":100},
        {"iso3":"BBB","country":"B","country_id":2,"year":2024,"eci":0.6,"exportValue":110},
        {"iso3":"CCC","country":"C","country_id":3,"year":2019,"eci":-0.5,"exportValue":20},
        {"iso3":"CCC","country":"C","country_id":3,"year":2024,"eci":-0.2,"exportValue":30},
    ])
    macro = pd.DataFrame([
        {"iso3":"AAA","gdp_growth":6,"inflation":3,"fdi_gdp":5,"market_cap_gdp":80},
        {"iso3":"BBB","gdp_growth":2,"inflation":7,"fdi_gdp":1,"market_cap_gdp":50},
        {"iso3":"CCC","gdp_growth":4,"inflation":5,"fdi_gdp":2,"market_cap_gdp":20},
    ])
    meta = pd.DataFrame([{"iso3":"AAA","region":"X"},{"iso3":"BBB","region":"X"},{"iso3":"CCC","region":"Y"}])
    out = build_country_scores(history, macro, meta, 2024)
    assert out["structural_score"].between(0,100).all()
    assert out.iloc[0]["iso3"] == "AAA"

def test_product_adjacency():
    country = pd.DataFrame([
        {"productId":1,"exportRca":0.2,"distance":0.1,"cog":0.8,"normalizedPci":2.0,"exportValue":10,"globalMarketShare":0},
        {"productId":2,"exportRca":0.3,"distance":0.6,"cog":0.2,"normalizedPci":0.5,"exportValue":5,"globalMarketShare":0},
        {"productId":3,"exportRca":1.5,"distance":0.1,"cog":1.0,"normalizedPci":3.0,"exportValue":100,"globalMarketShare":0.1},
    ])
    products = pd.DataFrame([
        {"productId":1,"code":"1001","nameEn":"Advanced A","clusterId":1,"naturalResource":False,"greenProduct":True},
        {"productId":2,"code":"1002","nameEn":"Basic B","clusterId":1,"naturalResource":False,"greenProduct":False},
        {"productId":3,"code":"1003","nameEn":"Existing C","clusterId":1,"naturalResource":False,"greenProduct":False},
    ])
    out = rank_product_opportunities(country, products)
    assert out.iloc[0]["productId"] == 1
    assert 3 not in out["productId"].tolist()

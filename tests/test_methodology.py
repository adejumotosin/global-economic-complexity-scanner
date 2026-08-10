from complexity_scanner.methodology import METHODOLOGY

def test_probability_guardrail_present():
    text = str(METHODOLOGY).lower()
    assert "no output" in text and "probability" in text

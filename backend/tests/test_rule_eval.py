"""Tests for app.agents.rule_eval — the generic evaluator for the "computed_draft"
tier (plan §B2). One test per ExtractedRule `kind`, plus proof that an unsafe
`formula` expression is rejected rather than executed, and that a malformed rule
never raises (always downgrades to NOT_CHECKABLE).
"""
from __future__ import annotations

from app.agents import rule_eval
from app.schemas import ExtractedRule


def _rule(**kwargs) -> ExtractedRule:
    kwargs.setdefault("clause_key", "TEST_CLAUSE")
    kwargs.setdefault("clause_phrase", "test clause phrase")
    return ExtractedRule(**kwargs)


# --------------------------------------------------------------------------- #
# compare — mirrors checks.py's WC_RATIO_SEVERE (value <= threshold)
# --------------------------------------------------------------------------- #
def test_compare_pass():
    rule = _rule(kind="compare", operator="<=", threshold=0.45, unit="")
    verdict, detail = rule_eval.evaluate(rule, {"value": 0.40})
    assert verdict == "PASS"
    assert "0.4" in detail


def test_compare_fail():
    rule = _rule(kind="compare", operator="<=", threshold=0.45)
    verdict, _ = rule_eval.evaluate(rule, {"value": 0.55})
    assert verdict == "FAIL"


# --------------------------------------------------------------------------- #
# range — mirrors checks.py's COLUMN_STEEL (0.8 <= value <= 6.0)
# --------------------------------------------------------------------------- #
def test_range_pass():
    rule = _rule(kind="range", inputs={"min": 0.8, "max": 6.0}, unit="%")
    verdict, _ = rule_eval.evaluate(rule, {"value": 2.0})
    assert verdict == "PASS"


def test_range_fail_below_min():
    rule = _rule(kind="range", inputs={"min": 0.8, "max": 6.0})
    verdict, _ = rule_eval.evaluate(rule, {"value": 0.5})
    assert verdict == "FAIL"


# --------------------------------------------------------------------------- #
# min_of — mirrors checks.py's TIE_PITCH (value <= min of several limits)
# --------------------------------------------------------------------------- #
def test_min_of_pass():
    rule = _rule(
        kind="min_of",
        threshold=300,
        inputs={"least_lateral_dim": "least_lateral_dim", "sixteen_bar_dia": 256},
    )
    param = {"value": 250, "least_lateral_dim": 400}
    verdict, detail = rule_eval.evaluate(rule, param)
    assert verdict == "PASS"
    assert "256" in detail


def test_min_of_fail():
    rule = _rule(kind="min_of", threshold=300, inputs={"a": 256})
    verdict, _ = rule_eval.evaluate(rule, {"value": 280})
    assert verdict == "FAIL"


# --------------------------------------------------------------------------- #
# max_of — mirrors checks.py's WIND_SPEED-style floor
# --------------------------------------------------------------------------- #
def test_max_of_pass():
    rule = _rule(kind="max_of", inputs={"city_basic_vb": "city_basic_vb"})
    verdict, _ = rule_eval.evaluate(rule, {"value": 55, "city_basic_vb": 50})
    assert verdict == "PASS"


def test_max_of_fail():
    rule = _rule(kind="max_of", inputs={"city_basic_vb": "city_basic_vb"})
    verdict, _ = rule_eval.evaluate(rule, {"value": 39, "city_basic_vb": 50})
    assert verdict == "FAIL"


# --------------------------------------------------------------------------- #
# table_lookup — mirrors checks.py's INSULATION_RESISTANCE_TABLE15
# --------------------------------------------------------------------------- #
def test_table_lookup_pass():
    rule = _rule(
        kind="table_lookup",
        operator=">",
        table={"selv_pelv": 0.5, "up_to_500v": 1.0},
        inputs={"key": "voltage_class"},
    )
    verdict, _ = rule_eval.evaluate(rule, {"value": 0.6, "voltage_class": "selv_pelv"})
    assert verdict == "PASS"


def test_table_lookup_missing_category_is_not_checkable():
    rule = _rule(kind="table_lookup", table={"selv_pelv": 0.5}, inputs={"key": "voltage_class"})
    verdict, _ = rule_eval.evaluate(rule, {"value": 0.6, "voltage_class": "unknown_class"})
    assert verdict == "NOT_CHECKABLE"


# --------------------------------------------------------------------------- #
# formula — mirrors checks.py's WIND_PRESSURE (pz >= 0.6 * Vz^2)
# --------------------------------------------------------------------------- #
def test_formula_pass():
    rule = _rule(
        kind="formula",
        operator=">=",
        expression="0.6 * Vz ** 2",
        inputs={"Vz": "design_wind_speed_vz"},
    )
    param = {"value": 700, "design_wind_speed_vz": 33}
    verdict, detail = rule_eval.evaluate(rule, param)
    assert verdict == "PASS"
    assert "653.4" in detail


def test_formula_fail():
    rule = _rule(kind="formula", operator=">=", expression="0.6 * Vz ** 2", inputs={"Vz": "design_wind_speed_vz"})
    param = {"value": 500, "design_wind_speed_vz": 33}
    verdict, _ = rule_eval.evaluate(rule, param)
    assert verdict == "FAIL"


def test_formula_rejects_unsafe_expression():
    """The whitelisted AST walker must reject anything beyond numbers/names/
    + - * / ** ()/min/max — never fall through to eval()/exec()."""
    rule = _rule(kind="formula", operator=">=", expression="__import__('os').system('echo pwned')", inputs={})
    verdict, detail = rule_eval.evaluate(rule, {"value": 1})
    assert verdict == "NOT_CHECKABLE"
    assert "disallowed" in detail or "unparsable" in detail


def test_formula_rejects_attribute_access():
    rule = _rule(kind="formula", operator=">=", expression="os.getcwd", inputs={})
    verdict, _ = rule_eval.evaluate(rule, {"value": 1})
    assert verdict == "NOT_CHECKABLE"


def test_formula_allows_min_max_builtins():
    rule = _rule(kind="formula", operator="<=", expression="min(a, b)", inputs={"a": 10, "b": 20})
    verdict, _ = rule_eval.evaluate(rule, {"value": 5})
    assert verdict == "PASS"


# --------------------------------------------------------------------------- #
# none — the LLM read the clause but found no checkable numeric rule
# --------------------------------------------------------------------------- #
def test_none_kind_is_not_checkable():
    rule = _rule(kind="none")
    verdict, _ = rule_eval.evaluate(rule, {"value": 42})
    assert verdict == "NOT_CHECKABLE"


# --------------------------------------------------------------------------- #
# never raises — malformed rules downgrade to NOT_CHECKABLE, never crash
# --------------------------------------------------------------------------- #
def test_missing_value_never_raises():
    rule = _rule(kind="compare", operator=">=", threshold=50)
    verdict, _ = rule_eval.evaluate(rule, {})
    assert verdict == "NOT_CHECKABLE"


def test_compare_missing_operator_never_raises():
    rule = _rule(kind="compare", threshold=50)
    verdict, _ = rule_eval.evaluate(rule, {"value": 60})
    assert verdict == "NOT_CHECKABLE"


def test_range_missing_bounds_never_raises():
    rule = _rule(kind="range", inputs={})
    verdict, _ = rule_eval.evaluate(rule, {"value": 60})
    assert verdict == "NOT_CHECKABLE"


def test_table_lookup_missing_field_never_raises():
    rule = _rule(kind="table_lookup", table={"a": 1}, inputs={"key": "not_present"})
    verdict, _ = rule_eval.evaluate(rule, {"value": 1})
    assert verdict == "NOT_CHECKABLE"

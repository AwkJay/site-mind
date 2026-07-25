"""The GENERIC RULE EVALUATOR — computes the "computed_draft" tier (plan §B2).

`checks.py` is the certified tier: ~17 hand-vetted Python rules, one per clause,
written by a human. That doesn't scale to thousands of IS clauses. This module
is the other half of the scaling story: an LLM *reads* a rule out of one real,
retrieved clause into an `ExtractedRule` (schemas.py) — a structured description
of the requirement, never a verdict — and `evaluate()` below is the ONLY thing
that turns that description into PASS/FAIL/NOT_CHECKABLE. The LLM never computes
anything; this module never calls the LLM. No `eval()`/`exec()` anywhere —
`formula` expressions run through `_safe_eval_expr`, a whitelisted AST walker.

Each `ExtractedRule.inputs`/`table` entry is either a literal number (a constant
the LLM read straight out of the clause text, e.g. the "300 mm" in a tie-spacing
clause) or a string naming a field to look up on the submitted `param` dict at
evaluate-time (e.g. "least_lateral_dim") — `_resolve()` handles both uniformly.

Kind semantics (mirrors the shapes already hand-written in checks.py):
  compare      value {operator} threshold                         (WC_RATIO_SEVERE)
  range        inputs.min <= value <= inputs.max                  (COLUMN_STEEL)
  min_of       value <= min(*inputs.values(), threshold)          (TIE_PITCH)
  max_of       value >= max(*inputs.values(), threshold)          (WIND_SPEED)
  table_lookup value {operator} table[param[inputs.key]]          (INSULATION_RESISTANCE_TABLE15)
  formula      value {operator} safe_eval(expression, inputs)     (WIND_PRESSURE)
  none         the LLM found no checkable numeric rule in the clause -> NOT_CHECKABLE

`evaluate()` never raises: any malformed or unsafe rule downgrades to
NOT_CHECKABLE with an explanatory detail string, never a fabricated verdict.
"""
from __future__ import annotations

import ast
import operator as _op

from ..schemas import ExtractedRule

_OPERATORS = {
    ">=": _op.ge,
    "<=": _op.le,
    ">": _op.gt,
    "<": _op.lt,
    "==": _op.eq,
    "!=": _op.ne,
}

_BINOPS = {ast.Add: _op.add, ast.Sub: _op.sub, ast.Mult: _op.mul, ast.Div: _op.truediv, ast.Pow: _op.pow}
_UNARYOPS = {ast.USub: _op.neg, ast.UAdd: _op.pos}


class RuleEvalError(Exception):
    """Internal only — evaluate() always catches this and downgrades to
    NOT_CHECKABLE. Never propagates to the caller."""


def _num(x) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise RuleEvalError(f"not a number: {x!r}")
    return float(x)


def _resolve(entry, param: dict) -> float:
    if isinstance(entry, str):
        if entry not in param:
            raise RuleEvalError(f"param has no field {entry!r}")
        return _num(param[entry])
    return _num(entry)


def _safe_eval_expr(expression: str, names: dict[str, float]) -> float:
    """Whitelisted AST evaluator: numbers, named inputs, + - * / ** ( ), and
    min()/max() only. Never `eval()`/`exec()` — anything else raises RuleEvalError."""
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise RuleEvalError(f"unparsable expression: {exc}") from exc

    def _walk(node):
        if isinstance(node, ast.Expression):
            return _walk(node.body)
        if isinstance(node, ast.Constant):
            return _num(node.value)
        if isinstance(node, ast.Name):
            if node.id not in names:
                raise RuleEvalError(f"unknown name in expression: {node.id}")
            return _num(names[node.id])
        if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
            return _BINOPS[type(node.op)](_walk(node.left), _walk(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARYOPS:
            return _UNARYOPS[type(node.op)](_walk(node.operand))
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in ("min", "max")
            and not node.keywords
        ):
            args = [_walk(a) for a in node.args]
            return (min if node.func.id == "min" else max)(args)
        raise RuleEvalError(f"disallowed expression element: {ast.dump(node)}")

    return _walk(tree)


def evaluate(rule: ExtractedRule, param: dict) -> tuple[str, str]:
    """Compute PASS / FAIL / NOT_CHECKABLE from an ExtractedRule the LLM only
    *read* out of a real clause. Never raises."""
    try:
        return _evaluate(rule, param)
    except RuleEvalError as exc:
        return "NOT_CHECKABLE", str(exc)
    except Exception as exc:  # belt-and-braces: a malformed rule must never crash the caller
        return "NOT_CHECKABLE", f"rule evaluation error: {exc}"


def _evaluate(rule: ExtractedRule, param: dict) -> tuple[str, str]:
    unit = f" {rule.unit}" if rule.unit else ""

    if rule.kind == "none":
        return "NOT_CHECKABLE", "the source clause states no checkable numeric rule"

    value = _num(param["value"]) if "value" in param else None
    if value is None and rule.kind != "table_lookup":
        raise RuleEvalError("param has no numeric 'value' to check")

    if rule.kind == "compare":
        if not rule.operator or rule.threshold is None:
            raise RuleEvalError("compare rule needs operator + threshold")
        ok = _OPERATORS[rule.operator](value, rule.threshold)
        verdict = "PASS" if ok else "FAIL"
        return verdict, f"value {value}{unit} {rule.operator} {rule.threshold}{unit} -> {verdict}"

    if rule.kind == "range":
        if "min" not in rule.inputs or "max" not in rule.inputs:
            raise RuleEvalError("range rule needs inputs.min and inputs.max")
        lo = _resolve(rule.inputs["min"], param)
        hi = _resolve(rule.inputs["max"], param)
        ok = lo <= value <= hi
        verdict = "PASS" if ok else "FAIL"
        return verdict, f"value {value}{unit} within [{lo}, {hi}]{unit} -> {verdict}"

    if rule.kind in ("min_of", "max_of"):
        if not rule.inputs:
            raise RuleEvalError(f"{rule.kind} rule needs at least one input")
        candidates = [_resolve(v, param) for v in rule.inputs.values()]
        if rule.threshold is not None:
            candidates.append(rule.threshold)
        if rule.kind == "min_of":
            limit = min(candidates)
            ok = value <= limit
            verdict = "PASS" if ok else "FAIL"
            return verdict, f"value {value}{unit} <= min{tuple(candidates)} = {limit}{unit} -> {verdict}"
        limit = max(candidates)
        ok = value >= limit
        verdict = "PASS" if ok else "FAIL"
        return verdict, f"value {value}{unit} >= max{tuple(candidates)} = {limit}{unit} -> {verdict}"

    if rule.kind == "table_lookup":
        if not rule.table or "key" not in rule.inputs:
            raise RuleEvalError("table_lookup rule needs a table + inputs.key")
        key_field = rule.inputs["key"]
        if not isinstance(key_field, str) or key_field not in param:
            raise RuleEvalError(f"table_lookup key field {key_field!r} not found on param")
        category = param[key_field]
        if category not in rule.table:
            return "NOT_CHECKABLE", f"no table row for {key_field}={category!r}"
        if value is None:
            raise RuleEvalError("param has no numeric 'value' to check")
        threshold = _num(rule.table[category])
        ok = _OPERATORS[rule.operator or ">="](value, threshold)
        verdict = "PASS" if ok else "FAIL"
        return verdict, f"value {value}{unit} {rule.operator or '>='} {threshold}{unit} (table[{category}]) -> {verdict}"

    if rule.kind == "formula":
        if not rule.expression:
            raise RuleEvalError("formula rule needs an expression")
        names = {name: _resolve(ref, param) for name, ref in rule.inputs.items()}
        result = _safe_eval_expr(rule.expression, names)
        ok = _OPERATORS[rule.operator or ">="](value, result)
        verdict = "PASS" if ok else "FAIL"
        return verdict, f"value {value}{unit} {rule.operator or '>='} ({rule.expression})={result}{unit} -> {verdict}"

    raise RuleEvalError(f"unknown rule kind: {rule.kind}")

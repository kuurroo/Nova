# nova/core/skills/mathx.py
from __future__ import annotations
import ast, math, operator
from typing import Optional

NAME = "mathx"

# Allowed names and functions
_ALLOWED_NAMES = {
    "pi": math.pi, "e": math.e, "tau": math.tau,
}
_ALLOWED_FUNCS = {
    "abs": abs, "round": round,
    "sqrt": math.sqrt, "log": math.log, "log10": math.log10, "log2": math.log2,
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
    "floor": math.floor, "ceil": math.ceil,
    "exp": math.exp, "pow": math.pow,
    "deg": math.degrees, "rad": math.radians,
    "factorial": math.factorial,
}
_ALLOWED_BINOPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_ALLOWED_UNARY = {
    ast.UAdd: lambda x: +x, ast.USub: lambda x: -x,
}

def _safe_eval(node):
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARY:
        return _ALLOWED_UNARY[type(node.op)](_safe_eval(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        return _ALLOWED_BINOPS[type(node.op)](left, right)
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in _ALLOWED_FUNCS:
            args = [_safe_eval(a) for a in node.args]
            if any(not isinstance(a, (int, float)) for a in args):
                raise ValueError("non-numeric arg")
            return _ALLOWED_FUNCS[node.func.id](*args)
    if isinstance(node, ast.Name) and node.id in _ALLOWED_NAMES:
        return _ALLOWED_NAMES[node.id]
    raise ValueError("disallowed expression")

def _looks_math(q: str) -> bool:
    # very small filter: contains digits and math-ish chars; short prompt
    ql = (q or "").strip().lower()
    if not ql: return False
    if len(ql) > 120: return False
    return any(c.isdigit() for c in ql) and any(c in "+-*/^()." for c in ql)

def _try_calc(q: str) -> Optional[str]:
    if not _looks_math(q):
        return None
    expr = q.strip()
    # allow "what is 2+2" → "2+2"
    for lead in ("what is", "calc", "calculate", "compute"):
        if expr.lower().startswith(lead):
            expr = expr[len(lead):].strip(": ,")
            break
    expr = expr.replace("^", "**")  # caret as power
    try:
        node = ast.parse(expr, mode="eval")
        val = _safe_eval(node)
    except Exception:
        return None
    # pretty output
    if isinstance(val, float):
        s = f"{val:.10g}"
    else:
        s = str(val)
    return f"- {expr} = {s}"

def try_handle(q: str) -> Optional[str]:
    return _try_calc(q)

def handle(q: str) -> Optional[str]:
    return try_handle(q)

def skill(q: str) -> Optional[str]:
    return try_handle(q)

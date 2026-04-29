"""Safe evaluation of assembly formulas (arithmetic, parentheses, whitelisted calls).

Variables are supplied by the caller (e.g. ``length``, ``area``, custom properties).
Supports ``^`` as exponentiation (converted to Python ``**`` before parse).
"""

from __future__ import annotations

import ast
import math
import operator
from functools import lru_cache
from typing import Any, Callable


class FormulaError(Exception):
    """Raised when a formula cannot be parsed or evaluated."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


_ALLOWED_FUNCS: dict[str, Callable[..., Any]] = {
    "round": round,
    "ceil": math.ceil,
    "floor": math.floor,
    "min": min,
    "max": max,
    "abs": abs,
}

_BINOPS: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}

_UNARYOPS: dict[type[ast.unaryop], Callable[[Any], Any]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _preprocess(source: str) -> str:
    s = source.strip()
    if not s:
        raise FormulaError("EMPTY", "Formula is empty")
    return s.replace("^", "**")


@lru_cache(maxsize=512)
def _compile_formula(source: str) -> ast.Expression:
    """Parse + cache the AST so derived-quantity loops over many measurements
    don't reparse the same formula string per row.
    """
    src = _preprocess(source)
    try:
        return ast.parse(src, mode="eval")
    except SyntaxError as e:
        raise FormulaError("SYNTAX_ERROR", e.msg or "Invalid syntax") from e


class _SafeEval(ast.NodeVisitor):
    def __init__(self, variables: dict[str, float]) -> None:
        self.variables = variables

    def visit(self, node: ast.AST) -> Any:  # type: ignore[override]
        if isinstance(
            node,
            (
                ast.Expression,
                ast.BinOp,
                ast.UnaryOp,
                ast.Call,
                ast.Name,
                ast.Constant,
                ast.Load,
            ),
        ):
            return super().visit(node)
        raise FormulaError("UNSUPPORTED_SYNTAX", f"Unsupported syntax: {type(node).__name__}")

    def visit_Expression(self, node: ast.Expression) -> Any:
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> Any:
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return float(node.value)
        raise FormulaError("INVALID_CONSTANT", "Only numeric constants are allowed")

    def visit_Name(self, node: ast.Name) -> Any:
        if node.id not in self.variables:
            raise FormulaError("UNKNOWN_VARIABLE", f"Unknown variable: {node.id}")
        return float(self.variables[node.id])

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        op = type(node.op)
        if op not in _BINOPS:
            raise FormulaError("UNSUPPORTED_OPERATOR", f"Operator not allowed: {op.__name__}")
        left = self.visit(node.left)
        right = self.visit(node.right)
        try:
            return _BINOPS[op](left, right)
        except ZeroDivisionError as e:
            raise FormulaError("DIVISION_BY_ZERO", "Division by zero") from e

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        op = type(node.op)
        if op not in _UNARYOPS:
            raise FormulaError("UNSUPPORTED_OPERATOR", f"Unary operator not allowed: {op.__name__}")
        return _UNARYOPS[op](self.visit(node.operand))

    def visit_Call(self, node: ast.Call) -> Any:
        if node.keywords:
            raise FormulaError("INVALID_CALL", "Keyword arguments are not supported")
        if not isinstance(node.func, ast.Name):
            raise FormulaError("INVALID_CALL", "Only simple function names are allowed")
        fname = node.func.id
        if fname not in _ALLOWED_FUNCS:
            raise FormulaError("UNKNOWN_FUNCTION", f"Unknown or disallowed function: {fname}")
        args = [self.visit(a) for a in node.args]
        try:
            return float(_ALLOWED_FUNCS[fname](*args))
        except (TypeError, ValueError) as e:
            raise FormulaError("CALL_ERROR", str(e)) from e


def evaluate_formula(expression: str, variables: dict[str, float]) -> float:
    """Evaluate ``expression`` using ``variables`` (all values must be numeric)."""
    tree = _compile_formula(expression)
    ev = _SafeEval(variables)
    result = ev.visit(tree)
    if not isinstance(result, (int, float)) or isinstance(result, bool):
        raise FormulaError("INVALID_RESULT", "Formula did not evaluate to a number")
    return float(result)


def validate_formula(expression: str, variable_names: set[str]) -> str | None:
    """Return an error message if invalid, else ``None``. Uses dummy values for variables."""
    dummy = {n: 1.0 for n in variable_names}
    try:
        evaluate_formula(expression, dummy)
    except FormulaError as e:
        return e.message
    return None

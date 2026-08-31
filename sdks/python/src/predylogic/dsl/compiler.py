"""
Compile .pdyl source into a RuleSetManifest.

A ``.pdyl`` file is a sequence of ``name = expression`` statements:

- **Value bindings** (``LIMIT = 50_000``; scalars, lists, string-keyed dicts)
  are named constants, substituted where used at compile time.
- **Predicate bindings** compose registry rule_defs with ``&`` / ``|`` / ``~``
  and reference other bindings by bare name. References are inlined, so every
  exported rule is a self-contained tree and traces reach the atoms.
- Names starting with ``_`` are private: usable in the file, absent from the
  manifest and from traces.
"""

from __future__ import annotations

import ast
import difflib
import inspect
from typing import TYPE_CHECKING, TypeAlias

from pydantic import ValidationError

from predylogic.dsl.errs import PdylError
from predylogic.rule_engine.schema import SchemaGenerator

if TYPE_CHECKING:
    from collections.abc import Collection
    from typing import NoReturn

    from predylogic.register.registry import Registry
    from predylogic.rule_engine.base import RuleSetManifest

Value: TypeAlias = "int | float | str | bool | list[Value] | dict[str, Value] | None"
_Node: TypeAlias = "dict[str, object]"


def compile_pdyl(src: str, registry: Registry, *, filename: str = "<pdyl>") -> RuleSetManifest:
    """
    Compile .pdyl source text into a validated manifest for registry.

    Args:
        src: DSL source ``name = expression`` statements in Python syntax;
            see the module docstring for the accepted subset.
        registry: The registry whose ``@rule_def`` atoms the source may call.
            Its signatures drive argument binding; its generated Pydantic
            models validate parameter values.
        filename: Label attached to error positions, as in :func:`ast.parse`.
            The compiler performs no I/O — ``src`` is the only input; the
            caller decides whether it came from a file, a database, or
            elsewhere.

    Returns:
        A ``RuleSetManifest`` (the model generated for ``registry``) with one
        rule per exported binding, ready for ``RuleEngine.update_manifests``.

    Raises:
        PdylError: On the first syntax or semantic error, positioned like any
            ``SyntaxError``.
    """
    return _Compiler(src, registry, filename).run()


class _Compiler:
    """Single-use walker: one instance compiles one source unit."""

    def __init__(self, src: str, registry: Registry, filename: str):
        self._src = src
        self._lines = src.splitlines()
        self._registry = registry
        self._generator = SchemaGenerator(registry)
        self._filename = filename
        self._bindings: dict[str, ast.expr] = {}
        self._resolving: list[str] = []

    def run(self) -> RuleSetManifest:
        """Parse, check every binding, and emit the validated manifest."""
        try:
            module = ast.parse(self._src, self._filename)
        except SyntaxError as e:
            err = PdylError(e.msg or "invalid syntax", (e.filename, e.lineno, e.offset, e.text))
            err.end_lineno, err.end_offset = e.end_lineno, e.end_offset
            raise err from e
        self._collect(module)
        rules: dict[str, _Node] = {}
        for name, expr in self._bindings.items():
            if not self._is_predicate(expr):
                self._value(expr)  # eager: value bindings are checked even when unused
            elif name.startswith("_"):
                self._pred(expr)  # eager: private predicates are checked even when unused
            else:
                rules[name] = self._pred(expr)
        return self._generator.generate().model_validate({"rules": rules})

    def _collect(self, module: ast.Module) -> None:
        """Whitelist the statement layer: ``name = expression`` lines only."""
        body = module.body[1:] if ast.get_docstring(module) is not None else module.body
        for stmt in body:
            match stmt:
                case ast.Assign(targets=[ast.Name(id=name)], value=value):
                    if name in self._bindings:
                        self._fail(stmt, f"'{name}' is already defined on line {self._bindings[name].lineno}")
                    self._bindings[name] = value
                case ast.Assign():
                    self._fail(stmt, "only single-name assignment is pdyl: name = expression")
                case _:
                    self._fail(
                        stmt,
                        f"{type(stmt).__name__} is not pdyl: a .pdyl file is 'name = expression' lines only",
                    )

    def _is_predicate(self, expr: ast.expr, seen: tuple[str, ...] = ()) -> bool:
        """Classify a binding's shape; follows aliases without resolving them."""
        match expr:
            case ast.Call() | ast.BinOp() | ast.BoolOp() | ast.Compare() | ast.UnaryOp(op=ast.Invert() | ast.Not()):
                return True
            case ast.Name(id=name) if name in self._bindings and name not in seen:
                return self._is_predicate(self._bindings[name], (*seen, name))
            case _:
                return False

    def _pred(self, expr: ast.expr) -> _Node:
        """Whitelist the predicate layer: calls, names, ``&`` ``|`` ``~``."""
        match expr:
            case ast.BinOp(op=ast.BitAnd()):
                return {"node_type": "and", "rules": self._flatten(expr, ast.BitAnd)}
            case ast.BinOp(op=ast.BitOr()):
                return {"node_type": "or", "rules": self._flatten(expr, ast.BitOr)}
            case ast.UnaryOp(op=ast.Invert(), operand=operand):
                return {"node_type": "not", "rule": self._pred(operand)}
            case ast.Call():
                return self._leaf(expr)
            case ast.Name():
                return self._inline(expr)
            case ast.BoolOp(op=ast.And()):
                self._fail(expr, "'and' is not pdyl; use '&'")
            case ast.BoolOp(op=ast.Or()):
                self._fail(expr, "'or' is not pdyl; use '|'")
            case ast.UnaryOp(op=ast.Not()):
                self._fail(expr, "'not' is not pdyl; use '~'")
            case ast.Compare():
                self._fail(expr, "comparisons are not pdyl; put them inside a @rule_def atom")
            case _:
                self._fail(expr, f"{type(expr).__name__} is not pdyl; predicates are calls, names, '&', '|', '~'")

    def _flatten(self, expr: ast.expr, op: type[ast.operator]) -> list[_Node]:
        """``a & b & c`` parses left-nested; emit one flat N-ary node instead."""
        if isinstance(expr, ast.BinOp) and isinstance(expr.op, op):
            return [*self._flatten(expr.left, op), *self._flatten(expr.right, op)]
        return [self._pred(expr)]

    def _leaf(self, call: ast.Call) -> _Node:
        """A rule_def call: bind arguments by signature, validate params by model."""
        if not isinstance(call.func, ast.Name):
            self._fail(call.func, "only registry rule_defs can be called")
        name = call.func.id
        if name not in self._registry:
            self._fail(call.func, _unknown_rule_def(name, self._registry))
        rule = {"rule_def_name": name, "params": self._bind(call, name)}
        try:
            self._generator.rule_config_models[name].model_validate(rule)
        except ValidationError as e:
            first = e.errors()[0]
            loc = ".".join(str(part) for part in first["loc"])
            self._fail(call, f"{name}(): {loc}: {first['msg']}")
        return {"node_type": "leaf", "rule": rule}

    def _bind(self, call: ast.Call, name: str) -> dict[str, Value]:
        """Map the call's arguments onto parameter names via the rule_def's signature."""
        args = [item for arg in call.args for item in self._spread(arg)]
        kwargs: dict[str, Value] = {}
        for kw in call.keywords:
            if kw.arg is None:
                self._fail(kw.value, "'**' unpacking is not pdyl; pass keywords directly")
            kwargs[kw.arg] = self._value(kw.value)
        try:
            bound = inspect.signature(self._registry[name]).bind(*args, **kwargs)
        except TypeError as e:
            self._fail(call, f"{name}(): {e}")
        else:
            return dict(bound.arguments)

    def _spread(self, arg: ast.expr) -> list[Value]:
        """One positional argument site: a single value, or a ``*``-unpacked list."""
        if not isinstance(arg, ast.Starred):
            return [self._value(arg)]
        items = self._value(arg.value)
        if not isinstance(items, list):
            self._fail(arg, "'*' can only unpack a list")
        return items

    def _value(self, expr: ast.expr) -> Value:
        """Whitelist the value layer: scalars, lists, string-keyed dicts, names."""
        match expr:
            case ast.Constant(value=None | bool() | int() | float() | str() as v):
                return v
            case ast.UnaryOp(op=ast.USub(), operand=ast.Constant(value=int() | float() as v)) if not isinstance(
                v,
                bool,
            ):
                return -v
            case ast.List(elts=elts) | ast.Tuple(elts=elts):
                return [self._value(item) for item in elts]
            case ast.Dict(keys=keys, values=values):
                out: dict[str, Value] = {}
                for key, val in zip(keys, values, strict=True):
                    if key is None or not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
                        self._fail(key or val, "pdyl dict keys must be string literals")
                    out[key.value] = self._value(val)
                return out
            case ast.Name():
                return self._substitute(expr)
            case ast.Call() | ast.BinOp() | ast.UnaryOp(op=ast.Invert()):
                self._fail(expr, "a predicate cannot be a parameter value; params are pure data")
            case ast.Constant():
                self._fail(expr, "this literal type is not pdyl; use int, float, str, bool, None")
            case _:
                self._fail(expr, f"{type(expr).__name__} is not a pdyl value; use scalars, lists, dicts")

    def _deref(self, expr: ast.Name) -> ast.expr:
        """Look up a bare name, failing on undefined names and reference cycles."""
        name = expr.id
        target = self._bindings.get(name)
        if target is None:
            if name in self._registry:
                self._fail(expr, f"'{name}' is a rule_def and must be called: {name}(...)")
            self._fail(expr, f"undefined name '{name}'")
        if name in self._resolving:
            chain = [*self._resolving[self._resolving.index(name) :], name]
            self._fail(expr, f"circular reference: {' -> '.join(chain)}")
        return target

    def _inline(self, expr: ast.Name) -> _Node:
        """A bare name in predicate position: substitute the bound tree."""
        target = self._deref(expr)
        if not self._is_predicate(target):
            self._fail(expr, f"'{expr.id}' is a value binding, not a predicate")
        self._resolving.append(expr.id)
        try:
            return self._pred(target)
        finally:
            self._resolving.pop()

    def _substitute(self, expr: ast.Name) -> Value:
        """A bare name in value position: substitute the bound constant."""
        target = self._deref(expr)
        if self._is_predicate(target):
            self._fail(expr, f"'{expr.id}' is a predicate and cannot be a parameter value")
        self._resolving.append(expr.id)
        try:
            return self._value(target)
        finally:
            self._resolving.pop()

    def _fail(self, node: ast.AST, msg: str) -> NoReturn:
        """Raise a positioned ``PdylError`` for ``node``."""
        lineno = getattr(node, "lineno", 1)
        col = getattr(node, "col_offset", 0)
        text = self._lines[lineno - 1] if 0 < lineno <= len(self._lines) else None
        err = PdylError(msg, (self._filename, lineno, _char_col(text, col), text))
        end_lineno = getattr(node, "end_lineno", None)
        end_col = getattr(node, "end_col_offset", None)
        if end_lineno == lineno and end_col is not None:
            err.end_lineno = end_lineno
            err.end_offset = _char_col(text, end_col)
        raise err


def _unknown_rule_def(name: str, known: Collection[str]) -> str:
    """Error text for an unknown rule_def, with a did-you-mean when one is close."""
    hint = difflib.get_close_matches(name, known, n=1)
    if hint:
        return f"unknown rule_def '{name}'; did you mean '{hint[0]}'?"
    listing = ", ".join(sorted(known)[:8]) or "<empty registry>"
    return f"unknown rule_def '{name}' (available: {listing})"


def _char_col(text: str | None, byte_offset: int) -> int:
    """Convert an ast UTF-8 byte offset to the 1-based character column SyntaxError expects."""
    if text is None:
        return byte_offset + 1
    return len(text.encode("utf-8")[:byte_offset].decode("utf-8", errors="ignore")) + 1

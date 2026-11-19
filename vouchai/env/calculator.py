"""Arithmetic-only calculator for the agent.

    expr   := term (("+" | "-") term)*
    term   := factor (("*" | "/") factor)*
    factor := ("+" | "-") factor | NUMBER | "(" expr ")"
    NUMBER := [0-9]+ ("." [0-9]+)?        ASCII digits only

No eval, no names, no power operator, no exponent notation, no underscores,
no non-ASCII digits, no NaN or Infinity. Decimal arithmetic in a local
context; the global decimal context is never touched.
"""

from __future__ import annotations

from decimal import Context, Decimal, DivisionByZero, InvalidOperation, Overflow

from .errors import ActionError

MAX_CHARS = 256
MAX_TOKENS = 128
MAX_NESTING = 32
MAX_NUMBER_DIGITS = 30
MAX_RESULT_EXPONENT = 60  # |result| < 10^61, otherwise rejected
PRECISION = 34

_DIGITS = "0123456789"
_OPERATORS = "+-*/()"
_SPACE = " \t"


def _context() -> Context:
    ctx = Context(prec=PRECISION, Emax=999, Emin=-999)
    ctx.traps[InvalidOperation] = True
    ctx.traps[DivisionByZero] = True
    ctx.traps[Overflow] = True
    return ctx


def _tokenize(expression: str) -> list[str]:
    tokens: list[str] = []
    i, n = 0, len(expression)
    while i < n:
        ch = expression[i]
        if ch in _SPACE:
            i += 1
            continue
        if ch in _OPERATORS:
            tokens.append(ch)
            i += 1
            continue
        if ch in _DIGITS:
            j = i
            while j < n and expression[j] in _DIGITS:
                j += 1
            if j < n and expression[j] == ".":
                k = j + 1
                while k < n and expression[k] in _DIGITS:
                    k += 1
                if k == j + 1:
                    raise ActionError("CALC_ERROR")  # "1." is not a number
                j = k
            number = expression[i:j]
            if sum(1 for c in number if c in _DIGITS) > MAX_NUMBER_DIGITS:
                raise ActionError("CALC_ERROR")
            tokens.append(number)
            i = j
            continue
        raise ActionError("CALC_ERROR")
    if len(tokens) > MAX_TOKENS:
        raise ActionError("CALC_ERROR")
    return tokens


class _Parser:
    def __init__(self, tokens: list[str], ctx: Context):
        self.tokens = tokens
        self.pos = 0
        self.ctx = ctx
        self.depth = 0

    def peek(self) -> str | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def take(self) -> str:
        tok = self.peek()
        if tok is None:
            raise ActionError("CALC_ERROR")
        self.pos += 1
        return tok

    def expr(self) -> Decimal:
        value = self.term()
        while self.peek() in ("+", "-"):
            op = self.take()
            rhs = self.term()
            value = self.ctx.add(value, rhs) if op == "+" else self.ctx.subtract(value, rhs)
        return value

    def term(self) -> Decimal:
        value = self.factor()
        while self.peek() in ("*", "/"):
            op = self.take()
            rhs = self.factor()
            if op == "*":
                value = self.ctx.multiply(value, rhs)
            else:
                if rhs.is_zero():
                    raise ActionError("CALC_ERROR")
                value = self.ctx.divide(value, rhs)
        return value

    def factor(self) -> Decimal:
        tok = self.take()
        if tok in ("+", "-"):
            self.depth += 1
            if self.depth > MAX_NESTING:
                raise ActionError("CALC_ERROR")
            inner = self.factor()
            self.depth -= 1
            return inner if tok == "+" else self.ctx.minus(inner)
        if tok == "(":
            self.depth += 1
            if self.depth > MAX_NESTING:
                raise ActionError("CALC_ERROR")
            inner = self.expr()
            if self.take() != ")":
                raise ActionError("CALC_ERROR")
            self.depth -= 1
            return inner
        if tok[0] in _DIGITS:
            return Decimal(tok)
        raise ActionError("CALC_ERROR")


def format_decimal(value: Decimal, ctx: Context | None = None) -> str:
    """Plain decimal string: no exponent, no trailing zeros, no negative zero."""
    ctx = ctx or _context()
    if value.is_zero():
        return "0"
    normalized = value.normalize(ctx)
    text = format(normalized, "f")
    return text


def evaluate(expression: object) -> str:
    """Evaluate an expression and return a decimal string, or raise CALC_ERROR."""
    if not isinstance(expression, str) or not expression or len(expression) > MAX_CHARS:
        raise ActionError("CALC_ERROR")
    tokens = _tokenize(expression)
    if not tokens:
        raise ActionError("CALC_ERROR")
    ctx = _context()
    parser = _Parser(tokens, ctx)
    try:
        value = parser.expr()
    except (InvalidOperation, DivisionByZero, Overflow, ArithmeticError):
        raise ActionError("CALC_ERROR") from None
    if parser.pos != len(tokens):
        raise ActionError("CALC_ERROR")
    if not value.is_finite():
        raise ActionError("CALC_ERROR")
    if not value.is_zero() and value.adjusted() > MAX_RESULT_EXPONENT:
        raise ActionError("CALC_ERROR")
    return format_decimal(value, ctx)

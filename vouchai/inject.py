"""Error plugins. Each one changes a posting decision (or adds a document copy)
and describes the resulting issue: affected objects, how its amount is read
from the books, evidence slots and absence checks. The engine re-posts.

  E1 duplicate_invoice   double_posting | duplicate_document
  E2 payment_allocation  missing | partial            (two-step receipts)
  E3 fx_conversion       wrong_date | wrong_pair | stale_rate
  E4 period_cutoff       right_early | right_late | left_early | left_late
  X1 partial_fx_boundary   E3 (UTC date) + E2 partial on one edge payment
  X2 duplicate_with_partial E1 double_posting + E2 partial on one invoice
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from fractions import Fraction

from .books import doc_rate
from .events import Clock, legit_posting
from .model import Decisions, Invoice, Payment, World
from .money import conv, exponent, round_fraction
from .rng import Stream
from .timeutil import format_date, format_ts, local_date, utc_seconds
from .world import rate_date

MAX_SHIFT_S = 3 * 86_400        # the same bound as the slowest legitimate delay
EDGE_MARGIN_S = 300             # shifted postings keep clear of the edge they cross
MATERIAL_TOLERANCES = 20


class NoTarget(Exception):
    """No admissible target for this plugin in the current books."""


# A reference inside an evidence slot:
#   ("invoice", key) | ("payment", key)      -> doc_id or business ID
#   ("rows", entry_key, accounts|None, invoice_key|None) -> matching rows of an entry
#   ("fx", date_text, currency)               -> fx id date:currency:base
Ref = tuple


@dataclass
class IssueSpec:
    type: str
    variant: str
    affected: list[tuple[str, str]]
    # how the amount is read: ("rows", entry, accounts) | ("relief_delta", pay, inv)
    #                         | ("fx_delta", kind, key, entry, account)
    amount_rule: tuple
    slots: list[list[Ref]]
    absence_checks: list[dict]
    mutation: dict
    derivation: dict
    objects: set[str] = field(default_factory=set)
    group: str | None = None
    amount: int = 0
    carrier_rows: list[str] = field(default_factory=list)


@dataclass
class Context:
    world: World
    invoices: list[Invoice]
    payments: list[Payment]
    decisions: Decisions
    clock: Clock
    taken: set[str] = field(default_factory=set)

    def in_period(self, ts: datetime) -> bool:
        return self.world.period_start <= ts < self.world.period_end

    def payments_of(self, inv_key: str) -> list[Payment]:
        return list(self._paid_by.get(inv_key, []))

    def __post_init__(self) -> None:
        self._cancelled = {i.credit_for for i in self.invoices if i.credit_for}
        self._paid_by: dict[str, list[Payment]] = {}
        for p in self.payments:
            for k, _ in p.allocations:
                self._paid_by.setdefault(k, []).append(p)

    def cancelled(self) -> set[str]:
        return self._cancelled

    def invoice(self, key: str) -> Invoice:
        for inv in self.invoices:
            if inv.key == key:
                return inv
        raise KeyError(key)

    def plain_invoice(self, inv: Invoice) -> bool:
        return (not inv.is_credit_note and inv.copy_of is None and inv.key not in self.taken
                and inv.key not in self.cancelled() and inv.key not in self.decisions.invoice_storno
                and len(self.decisions.invoice_postings[inv.key]) == 1)

    def last_relief_event(self, pay: Payment, inv_key: str) -> bool:
        t = utc_seconds(pay.timestamp)
        later = [p for p in self.payments_of(inv_key)
                 if p.key != pay.key and utc_seconds(p.timestamp) >= t]
        return not later

    def unit(self) -> int:
        return 10 ** exponent(self.world.base_currency)


def _rows(entry: str, accounts: tuple[str, ...] | None = None, invoice: str | None = None) -> Ref:
    return ("rows", entry, accounts, invoice)


def _material(ctx: Context, amount: int, tolerance: int) -> bool:
    return amount >= ctx.unit() and amount >= MATERIAL_TOLERANCES * max(tolerance, 1)


# ------------------------------------------------------------------- E1

def _e1_candidates(ctx: Context) -> list[Invoice]:
    return [inv for inv in ctx.invoices if ctx.plain_invoice(inv)
            and ctx.in_period(inv.issued_at)
            and ctx.in_period(ctx.decisions.invoice_postings[inv.key][0])]


def double_posting(ctx: Context, s: Stream, inv: Invoice | None = None) -> IssueSpec:
    if inv is None:
        candidates = _e1_candidates(ctx)
        if not candidates:
            raise NoTarget
        inv = s.choice(candidates)
    first = ctx.decisions.invoice_postings[inv.key][0]
    extra = ctx.clock.take(legit_posting(ctx.world, s, inv.issued_at))
    if not ctx.in_period(extra):
        ctx.clock.release(extra)
        raise NoTarget
    ctx.decisions.invoice_postings[inv.key].append(extra)
    ctx.taken.add(inv.key)
    return IssueSpec(
        type="duplicate_invoice", variant="double_posting",
        affected=[("invoice", inv.key)],
        amount_rule=("rows", f"{inv.key}/post1", ("1200",)),
        slots=[[("invoice", inv.key)],
               [_rows(f"{inv.key}/post0", ("1200", "4000"))],
               [_rows(f"{inv.key}/post1", ("1200", "4000"))]],
        absence_checks=[{"query": "no_reversal_of_invoice", "invoice": inv.key},
                        {"query": "no_credit_note_for", "invoice": inv.key}],
        mutation={"decision": "invoice_postings", "object": inv.key,
                  "before": [format_ts(first)], "after": [format_ts(first), format_ts(extra)]},
        derivation={"expected": "one issuing entry per invoice",
                    "amount": "Dr 1200 of the second issuing entry"},
        objects={inv.key},
    )


def duplicate_document(ctx: Context, s: Stream) -> IssueSpec:
    candidates = _e1_candidates(ctx)
    if not candidates:
        raise NoTarget
    inv = s.choice(candidates)
    twins = [o for o in ctx.invoices if o.key != inv.key and o.customer == inv.customer
             and o.lines == inv.lines and o.issued_at == inv.issued_at]
    if twins:
        raise NoTarget
    copy = Invoice(key=f"{inv.key}x", customer=inv.customer, currency=inv.currency,
                   issued_at=inv.issued_at, due_at=inv.due_at, lines=list(inv.lines),
                   total=inv.total, copy_of=inv.key)
    posting = ctx.clock.take(legit_posting(ctx.world, s, copy.issued_at))
    if not ctx.in_period(posting):
        ctx.clock.release(posting)
        raise NoTarget
    ctx.invoices.append(copy)
    ctx.invoices.sort(key=lambda i: (utc_seconds(i.issued_at), i.key))
    ctx.decisions.invoice_postings[copy.key] = [posting]
    ctx.taken.update({inv.key, copy.key})
    return IssueSpec(
        type="duplicate_invoice", variant="duplicate_document",
        affected=[("invoice", inv.key), ("invoice", copy.key)],
        amount_rule=("rows", f"{copy.key}/post0", ("1200",)),
        slots=[[("invoice", inv.key)], [("invoice", copy.key)],
               [_rows(f"{inv.key}/post0", ("1200", "4000"))],
               [_rows(f"{copy.key}/post0", ("1200", "4000"))]],
        absence_checks=[{"query": "no_credit_note_for", "invoice": inv.key},
                        {"query": "no_credit_note_for", "invoice": copy.key}],
        mutation={"decision": "add_document_copy", "object": copy.key, "copy_of": inv.key,
                  "posting": format_ts(posting)},
        derivation={"expected": "no two live invoices with equal customer, lines and issue time",
                    "amount": "Dr 1200 of the entry of one copy"},
        objects={inv.key, copy.key},
    )


# ------------------------------------------------------------------- E2

def _e2_candidates(ctx: Context) -> list[tuple[Payment, str, int]]:
    out = []
    for p in ctx.payments:
        if (p.mode != "two_step" or not p.public_refs or p.amount <= 0 or p.key in ctx.taken
                or not ctx.in_period(p.timestamp)):
            continue
        for inv_key, amount in p.allocations:
            inv = ctx.invoice(inv_key)
            if ctx.plain_invoice(inv) and ctx.last_relief_event(p, inv_key):
                out.append((p, inv_key, amount))
    return out


def _partial_amount(ctx: Context, s: Stream, currency: str, amount: int) -> int | None:
    step = 10 ** exponent(currency)
    for _ in range(5):
        k = Fraction(s.randint(20, 80), 100)
        new = round_fraction(amount * k / step, "half_even") * step  # exact
        if 0 < new < amount:
            return new
    return None


def payment_allocation(ctx: Context, s: Stream, variant: str,
                       target: tuple[Payment, str, int] | None = None) -> IssueSpec:
    if target is None:
        candidates = _e2_candidates(ctx)
        if not candidates:
            raise NoTarget
        target = s.choice(candidates)
    pay, inv_key, amount = target
    current = list(ctx.decisions.applied.get(pay.key, pay.allocations))
    if variant == "missing":
        applied = [(k, a) for k, a in current if k != inv_key]
        new_amount = 0
    else:
        new_amount = _partial_amount(ctx, s, pay.currency, amount)
        if new_amount is None:
            raise NoTarget
        applied = [(k, new_amount if k == inv_key else a) for k, a in current]
    ctx.decisions.applied[pay.key] = applied
    ctx.taken.update({pay.key, inv_key})
    prior = [p for p in ctx.payments_of(inv_key)
             if p.key != pay.key and utc_seconds(p.timestamp) < utc_seconds(pay.timestamp)]
    # any issuing entry of the invoice carries A (X2: it is posted twice, same amount)
    issuing = [_rows(f"{inv_key}/post{n}", ("1200", "4000"))
               for n in range(len(ctx.decisions.invoice_postings[inv_key]))]
    slots = [[("payment", pay.key)], [("invoice", inv_key)], issuing]
    if variant == "missing":
        slots.append([_rows(f"{pay.key}/recv", ("2150",))])
        checks = [{"query": "no_relief_by_payment", "payment": pay.key, "invoice": inv_key}]
    else:
        slots.append([_rows(f"{pay.key}/reclass", ("1200",), inv_key)])
        checks = [{"query": "single_reclassification", "payment": pay.key}]
    closing = sum(a for p in ctx.payments_of(inv_key) for k, a in p.allocations if k == inv_key)
    inv = ctx.invoice(inv_key)
    if closing == inv.total:                   # expected relief = remainder: cite priors
        for p in prior:
            entry = f"{p.key}/reclass" if p.mode == "two_step" else f"{p.key}/recv"
            slots.append([("payment", p.key)])
            slots.append([_rows(entry, ("1200",), inv_key)])
    return IssueSpec(
        type="payment_allocation", variant=variant,
        affected=[("payment", pay.key), ("invoice", inv_key)],
        amount_rule=("relief_delta", pay.key, inv_key),
        slots=slots, absence_checks=checks,
        mutation={"decision": "applied_amount", "object": pay.key, "invoice": inv_key,
                  "before": amount, "after": new_amount},
        derivation={"expected": "round(allocation * A / T), or A - prior reliefs when closing",
                    "actual": "Cr 1200 by this payment for this invoice (0 if none)",
                    "amount": "expected - actual"},
        objects={pay.key, inv_key},
    )


# ------------------------------------------------------------------- E3

def _event(doc) -> datetime:
    return doc.issued_at if isinstance(doc, Invoice) else doc.timestamp


def _fx_amount(ctx: Context, doc, override: tuple[date, str]) -> int:
    world = ctx.world
    correct = doc_rate(world, None, doc.key, doc.currency, _event(doc))
    wrong = world.fx.rates[(override[0], override[1], world.base_currency)]
    value = doc.total if isinstance(doc, Invoice) else doc.amount
    return abs(conv(value, wrong, doc.currency, world.base_currency, world.rounding)
               - conv(value, correct, doc.currency, world.base_currency, world.rounding))


def _wrong_rates(ctx: Context, doc, variant: str) -> list[tuple[date, str]]:
    world = ctx.world
    event = _event(doc)
    local = local_date(event, world.offset)
    right = rate_date(world, doc.currency, local)
    options: list[tuple[date, str]] = []
    if variant == "wrong_date":
        alternatives = [local_date(event, 0), local + timedelta(days=1)]
        if isinstance(doc, Invoice):
            alternatives.append(local_date(doc.due_at, world.offset))
        for alt in alternatives:
            d = rate_date(world, doc.currency, alt)
            if d is not None and d != right:
                options.append((d, doc.currency))
    elif variant == "wrong_pair":
        for (d, src, _t) in sorted(world.fx.rates):
            if d == right and src not in (doc.currency, world.base_currency):
                options.append((d, src))
    elif variant == "stale_rate":
        d = rate_date(world, doc.currency, local.replace(day=1))
        if d is not None and d != right:
            options.append((d, doc.currency))
    return [o for o in options if _material(ctx, _fx_amount(ctx, doc, o), 1)]


def _e3_candidates(ctx: Context) -> list:
    base = ctx.world.base_currency
    out: list = []
    for inv in ctx.invoices:
        if (inv.currency != base and ctx.plain_invoice(inv) and ctx.in_period(inv.issued_at)
                and ctx.in_period(ctx.decisions.invoice_postings[inv.key][0])):
            out.append(inv)
    for p in ctx.payments:
        if (p.currency != base and p.fee == 0 and p.amount > 0 and p.key not in ctx.taken
                and ctx.in_period(p.timestamp)
                and ctx.in_period(ctx.decisions.payment_posting[p.key])):
            out.append(p)
    return out


def fx_conversion(ctx: Context, s: Stream, variants: list[str], doc=None) -> IssueSpec:
    candidates = [doc] if doc is not None else _e3_candidates(ctx)
    s.shuffle(candidates)
    for d in candidates:
        for variant in variants:
            options = _wrong_rates(ctx, d, variant)
            if options:
                return _apply_fx(ctx, s, d, variant, s.choice(options))
    raise NoTarget


def _apply_fx(ctx: Context, s: Stream, doc, variant: str, override: tuple[date, str]) -> IssueSpec:
    world = ctx.world
    is_invoice = isinstance(doc, Invoice)
    kind = "invoice" if is_invoice else "payment"
    entry = f"{doc.key}/post0" if is_invoice else f"{doc.key}/recv"
    account = "1200" if is_invoice else "1010"
    local = local_date(_event(doc), world.offset)
    right = rate_date(world, doc.currency, local)
    ctx.decisions.rate_override[doc.key] = override
    ctx.taken.add(doc.key)
    checks = []
    first_allowed = (local if world.rate_rule == "same_day_or_previous"
                     else local - timedelta(days=1))
    if right != first_allowed:
        checks.append({"query": "no_rate_between", "currency": doc.currency,
                       "after": format_date(right), "until": format_date(first_allowed)})
    return IssueSpec(
        type="fx_conversion", variant=variant,
        affected=[(kind, doc.key)],
        amount_rule=("fx_delta", kind, doc.key, entry, account),
        slots=[[(kind, doc.key)], [_rows(entry, (account,))],
               [("fx", format_date(right), doc.currency)]],
        absence_checks=checks,
        mutation={"decision": "rate_used", "object": doc.key,
                  "before": [format_date(right), doc.currency],
                  "after": [format_date(override[0]), override[1]]},
        derivation={"expected": f"conv({'total' if is_invoice else 'amount'}, rate of "
                                "the company-local event date per policy)",
                    "actual": f"Dr {account} of the {'issuing' if is_invoice else 'receipt'} entry",
                    "amount": "|actual - expected|"},
        objects={doc.key},
    )


# ------------------------------------------------------------------- E4

def _shift_window(variant: str, world: World, event: datetime) -> tuple[int, int] | None:
    """Admissible signed shift (seconds from the event) of the posting, or None."""
    e = utc_seconds(event)
    ps, pe = utc_seconds(world.period_start), utc_seconds(world.period_end)
    ws, we = utc_seconds(world.window_start), utc_seconds(world.window_end)
    m = EDGE_MARGIN_S
    if variant == "right_late" and ps <= e < pe:
        lo, hi = pe + m - e, min(MAX_SHIFT_S, we - m - e)
    elif variant == "left_late" and ws <= e < ps:
        lo, hi = ps + m - e, min(MAX_SHIFT_S, pe - m - e)
    elif variant == "right_early" and pe <= e < we:
        lo, hi = -min(MAX_SHIFT_S, e - (ps + m)), pe - m - e
    elif variant == "left_early" and ps <= e < pe:
        lo, hi = -min(MAX_SHIFT_S, e - (ws + m)), ps - m - e
    else:
        return None
    return (lo, hi) if lo <= hi else None


def period_cutoff(ctx: Context, s: Stream, variants: list[str]) -> IssueSpec:
    options = []
    for variant in variants:
        for inv in ctx.invoices:
            if not ctx.plain_invoice(inv):
                continue
            window = _shift_window(variant, ctx.world, inv.issued_at)
            if window:
                options.append((variant, "invoice", inv.key, inv.issued_at, window))
        for pay in ctx.payments:
            if pay.key in ctx.taken or pay.amount <= 0:
                continue
            window = _shift_window(variant, ctx.world, pay.timestamp)
            if window:
                options.append((variant, "payment", pay.key, pay.timestamp, window))
    s.shuffle(options)
    for variant, kind, key, event, (lo, hi) in options:
        new = event + timedelta(seconds=s.randint(lo, hi))
        if kind == "payment":
            pay = next(p for p in ctx.payments if p.key == key)
            # every invoice it relieves must already be posted before the shifted receipt
            inv_posts = [ctx.decisions.invoice_postings[k][0] for k, _ in pay.allocations]
            if any(utc_seconds(p) >= utc_seconds(min(new, event)) for p in inv_posts):
                continue
            reclass = ctx.decisions.reclass_posting.get(key)
            if reclass is not None and utc_seconds(reclass) <= utc_seconds(max(new, event)):
                continue
            old = ctx.decisions.payment_posting[key]
        else:
            # its receipts must come after the shifted posting
            if any(utc_seconds(ctx.decisions.payment_posting[p.key]) <= utc_seconds(max(new, event))
                   for p in ctx.payments_of(key)):
                continue
            old = ctx.decisions.invoice_postings[key][0]
        # The old moment stays reserved: the clean books still use it.
        new = ctx.clock.take(new)
        if kind == "payment":
            ctx.decisions.payment_posting[key] = new
            entry, accounts = f"{key}/recv", ("1010", "6100")
        else:
            ctx.decisions.invoice_postings[key] = [new]
            entry, accounts = f"{key}/post0", ("1200",)
        ctx.taken.add(key)
        return IssueSpec(
            type="period_cutoff", variant=variant,
            affected=[(kind, key)],
            amount_rule=("rows", entry, accounts),
            slots=[[(kind, key)], [_rows(entry)]],
            absence_checks=[{"query": "no_posting_in_event_period", kind: key}],
            mutation={"decision": "posting_moment", "object": key,
                      "before": format_ts(old), "after": format_ts(new)},
            derivation={"expected": "posting in the period of the event (company time)",
                        "amount": "Dr 1200 of the shifted invoice entry, or Dr 1010 + Dr 6100 "
                                  "of the shifted receipt"},
            objects={key},
        )
    raise NoTarget


# ------------------------------------------------------------ interactions

def partial_fx_boundary(ctx: Context, s: Stream) -> list[IssueSpec]:
    """X1: a partial foreign payment at the period edge, booked at the UTC-date
    rate and applied only in part."""
    world = ctx.world
    options = []
    for pay, inv_key, amount in _e2_candidates(ctx):
        if pay.currency == world.base_currency or pay.fee or len(pay.allocations) != 1:
            continue
        inv = ctx.invoice(inv_key)
        if amount >= inv.total:
            continue
        local = local_date(pay.timestamp, world.offset)
        utc = local_date(pay.timestamp, 0)
        if local == utc:
            continue
        right, wrong = rate_date(world, pay.currency, local), rate_date(world, pay.currency, utc)
        if wrong is None or wrong == right:
            continue
        if not _material(ctx, _fx_amount(ctx, pay, (wrong, pay.currency)), 1):
            continue
        options.append((pay, inv_key, amount, wrong))
    if not options:
        raise NoTarget
    pay, inv_key, amount, wrong = s.choice(options)
    fx = _apply_fx(ctx, s, pay, "wrong_date", (wrong, pay.currency))
    ctx.taken.discard(pay.key)
    alloc = payment_allocation(ctx, s, "partial", (pay, inv_key, amount))
    fx.group = alloc.group = "X1"
    return [fx, alloc]


def duplicate_with_partial(ctx: Context, s: Stream) -> list[IssueSpec]:
    """X2: an invoice posted twice whose payment is applied only in part."""
    options = [(p, k, a) for p, k, a in _e2_candidates(ctx)
               if any(k == inv.key for inv in _e1_candidates(ctx))]
    if not options:
        raise NoTarget
    pay, inv_key, amount = s.choice(options)
    inv = ctx.invoice(inv_key)
    dup = double_posting(ctx, s, inv)
    ctx.taken.discard(inv_key)
    alloc = payment_allocation(ctx, s, "partial", (pay, inv_key, amount))
    dup.group = alloc.group = "X2"
    return [dup, alloc]


def inject(ctx: Context, stream: Stream, errors_cfg: dict, interactions: dict,
           lenient: bool = False, unplaced: list | None = None) -> list[IssueSpec]:
    """Apply interactions first, then every configured error type; each draws
    from its own sub-stream."""
    specs: list[IssueSpec] = []
    # Each interaction falls back to the other one when the books offer no target
    # (X1 needs an edge payment whose UTC-date rate differs from the local one).
    plan = (["X1"] * interactions.get("partial_fx_boundary", 0)
            + ["X2"] * interactions.get("duplicate_with_partial", 0))
    for i, name in enumerate(plan):
        s = stream.child(f"interaction/{i}")
        order = [name, "X2" if name == "X1" else "X1"]
        for which in order:
            try:
                specs += (partial_fx_boundary(ctx, s) if which == "X1"
                          else duplicate_with_partial(ctx, s))
                break
            except NoTarget:
                continue
        else:
            if not lenient:
                raise NoTarget
            if unplaced is not None:
                unplaced.append(name)

    def attempt(etype: str, run) -> None:
        cfg = errors_cfg[etype]
        base = stream.child(etype)
        for i in range(cfg["count"]):
            s = base.child(str(i))
            variants = list(cfg["variants"])
            s.shuffle(variants)
            try:
                specs.append(run(s, variants))
            except NoTarget:
                if not lenient:
                    raise
                if unplaced is not None:
                    unplaced.append(etype)

    def e1(s, variants):
        for v in variants:
            try:
                if v == "double_posting":
                    return double_posting(ctx, s)
                return duplicate_document(ctx, s)
            except NoTarget:
                continue
        raise NoTarget

    def e2(s, variants):
        for v in variants:
            try:
                return payment_allocation(ctx, s, v)
            except NoTarget:
                continue
        raise NoTarget

    attempt("duplicate_invoice", e1)
    attempt("payment_allocation", e2)
    attempt("fx_conversion", lambda s, v: fx_conversion(ctx, s, v))
    attempt("period_cutoff", lambda s, v: period_cutoff(ctx, s, v))
    return specs

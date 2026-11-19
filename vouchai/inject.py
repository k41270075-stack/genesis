"""Error plugins. Each one changes a posting decision (or adds a document copy)
and describes the resulting issue: affected objects, carrier row, evidence
slots and absence checks. The engine re-posts the books afterwards.

Implemented: E1 duplicate_invoice (double_posting, duplicate_document) and
E4 period_cutoff (right_early, right_late, left_early, left_late).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .events import Clock, legit_posting
from .model import Decisions, Invoice, Payment, World
from .rng import Stream
from .timeutil import format_ts, utc_seconds

MAX_SHIFT_S = 3 * 86_400        # the same bound as the slowest legitimate delay
EDGE_MARGIN_S = 300             # shifted postings keep clear of the edge they cross


class NoTarget(Exception):
    """No admissible target for this plugin in the current books."""


# A reference inside an evidence slot:
#   ("invoice", key) -> doc_id or invoice_id of that invoice
#   ("payment", key) -> doc_id or payment_id of that payment
#   ("rows", entry_key, accounts or None) -> any matching row of that entry
Ref = tuple


@dataclass
class IssueSpec:
    type: str
    variant: str
    affected: list[tuple[str, str]]
    carrier: tuple[str, tuple[str, ...]]      # entry key, debit accounts summed
    slots: list[list[Ref]]
    absence_checks: list[dict]
    mutation: dict
    objects: set[str] = field(default_factory=set)


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
        return [p for p in self.payments if any(k == inv_key for k, _ in p.allocations)]


def _rows(entry: str, accounts: tuple[str, ...] | None = None) -> Ref:
    return ("rows", entry, accounts)


def _period_invoices(ctx: Context) -> list[Invoice]:
    out = []
    for inv in ctx.invoices:
        posts = ctx.decisions.invoice_postings[inv.key]
        if (inv.key in ctx.taken or inv.copy_of or len(posts) != 1
                or not ctx.in_period(inv.issued_at) or not ctx.in_period(posts[0])):
            continue
        out.append(inv)
    return out


def double_posting(ctx: Context, s: Stream) -> IssueSpec:
    candidates = _period_invoices(ctx)
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
        carrier=(f"{inv.key}/post1", ("1200",)),
        slots=[[("invoice", inv.key)],
               [_rows(f"{inv.key}/post0", ("1200", "4000"))],
               [_rows(f"{inv.key}/post1", ("1200", "4000"))]],
        absence_checks=[{"query": "no_reversal_of_invoice_posting", "invoice": inv.key},
                        {"query": "no_credit_note_for", "invoice": inv.key}],
        mutation={"decision": "invoice_postings", "object": inv.key,
                  "before": [format_ts(first)], "after": [format_ts(first), format_ts(extra)]},
        objects={inv.key},
    )


def duplicate_document(ctx: Context, s: Stream) -> IssueSpec:
    candidates = _period_invoices(ctx)
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
        carrier=(f"{copy.key}/post0", ("1200",)),
        slots=[[("invoice", inv.key)], [("invoice", copy.key)],
               [_rows(f"{inv.key}/post0", ("1200", "4000"))],
               [_rows(f"{copy.key}/post0", ("1200", "4000"))]],
        absence_checks=[{"query": "no_credit_note_for", "invoice": inv.key},
                        {"query": "no_credit_note_for", "invoice": copy.key}],
        mutation={"decision": "add_document_copy", "object": copy.key, "copy_of": inv.key,
                  "posting": format_ts(posting)},
        objects={inv.key, copy.key},
    )


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
            posts = ctx.decisions.invoice_postings[inv.key]
            if inv.key in ctx.taken or inv.copy_of or len(posts) != 1:
                continue
            window = _shift_window(variant, ctx.world, inv.issued_at)
            if window:
                options.append((variant, "invoice", inv.key, inv.issued_at, window))
        for pay in ctx.payments:
            if pay.key in ctx.taken:
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
            carrier=(entry, accounts),
            slots=[[(kind, key)], [_rows(entry)]],
            absence_checks=[{"query": "no_posting_in_event_period", kind: key}],
            mutation={"decision": "posting_moment", "object": key,
                      "before": format_ts(old), "after": format_ts(new)},
            objects={key},
        )
    raise NoTarget


def inject(ctx: Context, stream: Stream, errors_cfg: dict) -> list[IssueSpec]:
    """Apply every configured error; each type draws from its own sub-stream."""
    specs: list[IssueSpec] = []
    e1 = errors_cfg["duplicate_invoice"]
    s1 = stream.child("duplicate_invoice")
    for i in range(e1["count"]):
        s = s1.child(str(i))
        variant = s.choice(e1["variants"])
        order = [variant] + [v for v in e1["variants"] if v != variant]
        for v in order:
            try:
                specs.append(double_posting(ctx, s) if v == "double_posting"
                             else duplicate_document(ctx, s))
                break
            except NoTarget:
                continue
        else:
            raise NoTarget
    e4 = errors_cfg["period_cutoff"]
    s4 = stream.child("period_cutoff")
    for i in range(e4["count"]):
        s = s4.child(str(i))
        variants = list(e4["variants"])
        s.shuffle(variants)
        specs.append(period_cutoff(ctx, s, variants))
    return specs

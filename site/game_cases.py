"""Cases of the site's game «Ошибка или двойник?» from the open dev episode.

    python site/game_cases.py        # from the root of the repository

Errors come from the episode truth (what was planted, on which records).
Look-alikes come from a scan of the public tables with the published
legitimate-case rules; a look-alike is kept only if none of its records is
touched by any truth issue. Output: site/data/game.json. Standard library only.
"""

from __future__ import annotations

import json
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "site" / "data"
OUT = DATA / "game.json"


def rows(table: dict) -> list[dict]:
    return [dict(zip(table["columns"], r)) for r in table["rows"]]


def main() -> int:
    ep = json.loads((DATA / "episode.json").read_text(encoding="utf-8"))
    exp = ep["manifest"]["currency_exponents"]
    base = ep["manifest"]["base_currency"]
    tz = ep["manifest"]["timezone"]
    ledger, invoices, payments = rows(ep["tables"]["ledger"]), rows(ep["tables"]["invoices"]), rows(ep["tables"]["payments"])
    fxs = rows(ep["tables"]["fx"])
    issues = ep["truth"]["issues"]
    touched = {x for i in issues for x in [*i["affected_ids"], *i.get("evidence_ids", []), *i.get("carrier_row_ids", [])]}

    def money(minor: int, cur: str) -> str:
        e = exp.get(cur, 2)
        s = f"{abs(minor) / 10 ** e:,.{e}f}".replace(",", " ").replace(".", ",")
        return ("−" if minor < 0 else "") + s + (" ₸" if cur == "KZT" else f" {cur}")

    def when(ts: str) -> str:
        return ts[:16].replace("T", " ") + " " + ts[19:]

    inv_by = {i["invoice_id"]: i for i in invoices}
    pay_by = {p["payment_id"]: p for p in payments}

    def inv_card(i: dict) -> dict:
        li = i["line_items"][0]
        return {"label": f"счёт {i['invoice_id']}", "lines": [
            ["клиент", i["entity_id"]], ["выставлен", when(i["issued_at"])], ["услуга", li["description"]],
            ["период услуги", f"{li['service_period_start']} … {li['service_period_end']}"],
            ["сумма", money(i["total_minor"], i["currency"])]] + ([["сторно для", i["credit_for"]]] if i.get("credit_for") else [])}

    def pay_card(p: dict) -> dict:
        al = "; ".join(f"{a['invoice_id']}: {money(a['amount_minor'], p['currency'])}" for a in p["allocations"]) or "—"
        return {"label": f"платёж {p['payment_id']}", "lines": [
            ["время банка", when(p["timestamp"])], ["сумма", money(p["amount_minor"], p["currency"])],
            ["разнесено", al], ["комиссия", money(p.get("fee_minor") or 0, p["currency"])]]}

    def row_card(r: dict, label: str | None = None) -> dict:
        amt = r["debit_minor"] or 0
        side = "Дт" if amt else "Кт"
        return {"label": label or f"проводка {r['row_id']}", "lines": [
            ["время", when(r["timestamp"])], ["счёт", r["account"]],
            [side, money(amt or (r["credit_minor"] or 0), r["currency"])],
            ["ссылка", r["invoice_id"] or r["payment_id"] or "—"]]}

    cases: list[dict] = []
    # ---------------------------------------------------------------- errors from the truth
    for iss in issues:
        t, a = iss["type"], iss["affected_ids"]
        diff = money(iss["expected_amount_minor"], iss["currency"])
        if t == "duplicate_invoice":
            inv = inv_by[a[0]]
            posts = [r for r in ledger if r["invoice_id"] == a[0] and r["account"] == "1200" and (r["debit_minor"] or 0) > 0]
            cases.append({"kind": "error", "type": t, "claim": f"У счёта {a[0]} в книге две проводки на одну сумму",
                          "cards": [inv_card(inv)] + [row_card(r, f"проводка выставления №{k + 1}") for k, r in enumerate(posts[:2])],
                          "explain": f"Один документ — одна проводка выставления. Вторая живая проводка завышает долг клиента на {diff}."})
        elif t == "period_cutoff":
            obj = pay_by.get(a[0]) or inv_by.get(a[0])
            rws = [r for r in ledger if r["row_id"] in set(iss.get("evidence_ids", [])) | set(iss.get("carrier_row_ids", []))]
            card = pay_card(obj) if a[0] in pay_by else inv_card(obj)
            cases.append({"kind": "error", "type": t, "claim": f"{a[0]}: операция на стыке месяцев",
                          "cards": [card] + [row_card(r) for r in rws[:1]],
                          "explain": f"Операция произошла до конца периода по времени компании ({tz}), а проведена в следующем месяце. Сдвинуто {diff}."})
        elif t == "fx_conversion":
            obj = pay_by.get(a[0]) or inv_by.get(a[0])
            fx = next((x for x in iss.get("evidence_ids", []) if ":" in x), "")
            rate = next((r["rate"] for r in fxs if r["id"] == fx), None)
            rws = [r for r in ledger if r["row_id"] in iss.get("evidence_ids", [])]
            card = pay_card(obj) if a[0] in pay_by else inv_card(obj)
            amount = obj.get("amount_minor", obj.get("total_minor"))
            src = obj["currency"]
            conv = (Decimal(amount) / (10 ** exp.get(src, 2)) * Decimal(str(rate)) * (10 ** exp.get(base, 2))).quantize(Decimal(1), ROUND_HALF_UP) if rate else None
            cases.append({"kind": "error", "type": t, "claim": f"{a[0]}: валютная сумма пересчитана в {base}",
                          "cards": [card] + [row_card(r, "проведено в книге") for r in rws[:1]] + [{"label": "курс по политике", "lines": [
                              ["дата и пара", fx], ["курс", str(rate)], ["по этому курсу", money(int(conv), base) if conv is not None else "—"]]}],
                          "explain": f"Курс взят не той даты: по политике сумма в {base} отличается на {diff}."})
        elif t == "payment_allocation":
            p = pay_by[a[0]]
            rws = [r for r in ledger if r["payment_id"] == a[0] and r["account"] == "1200" and (r["credit_minor"] or 0) > 0]
            cases.append({"kind": "error", "type": t, "claim": f"Платёж {a[0]} и погашение счёта {a[1]}",
                          "cards": [pay_card(p)] + [row_card(r, "погашение в книге") for r in rws[:1]],
                          "explain": f"В документе платёж разнесён на счёт целиком, а в книге долг уменьшен меньше: не хватает {diff}."})

    # ---------------------------------------------------------------- look-alikes from the public tables
    def clean(*ids: str) -> bool:
        return not (set(ids) & touched)

    twins: list[dict] = []
    seen = defaultdict(list)
    for i in invoices:
        if i.get("credit_for"):
            continue
        seen[(i["entity_id"], i["currency"], i["total_minor"])].append(i)
    for group in seen.values():
        if len(group) >= 2:
            x, y = group[0], group[1]
            px, py = x["line_items"][0]["service_period_start"], y["line_items"][0]["service_period_start"]
            if px != py and clean(x["invoice_id"], y["invoice_id"], x["doc_id"], y["doc_id"]):
                twins.append({"kind": "twin", "type": "subscription", "claim": f"Два счёта клиенту {x['entity_id']} на одну сумму",
                              "cards": [inv_card(x), inv_card(y)],
                              "explain": "Разные периоды услуги: это подписка за два месяца, а не дубль. Дубль — тот же документ, выставленный дважды."})
                break
    for i in invoices:
        if i.get("credit_for") and i["credit_for"] in inv_by and clean(i["invoice_id"], i["credit_for"]):
            twins.append({"kind": "twin", "type": "credit_note", "claim": f"Копия счёта {i['credit_for']}",
                          "cards": [inv_card(inv_by[i["credit_for"]]), inv_card(i)],
                          "explain": "Копия отменена кредит-нотой в том же периоде, это не ошибка."})
            break
    paid = defaultdict(list)
    for p in payments:
        for al in p["allocations"]:
            paid[al["invoice_id"]].append(p)
    for inv_id, ps in paid.items():
        if len(ps) >= 2 and clean(inv_id, *[p["payment_id"] for p in ps]):
            twins.append({"kind": "twin", "type": "split", "claim": f"Счёт {inv_id} получил два платежа",
                          "cards": [inv_card(inv_by[inv_id]), pay_card(ps[0]), pay_card(ps[1])],
                          "explain": "Счёт оплачен частями: сумма частей равна счёту. Переплаты нет."})
            break
    for p in payments:
        if len(p["allocations"]) >= 2 and clean(p["payment_id"], *[x["invoice_id"] for x in p["allocations"]]):
            twins.append({"kind": "twin", "type": "multi", "claim": f"Один платёж {p['payment_id']} закрывает несколько счетов",
                          "cards": [pay_card(p)] + [inv_card(inv_by[x["invoice_id"]]) for x in p["allocations"][:2] if x["invoice_id"] in inv_by],
                          "explain": "Один перевод на несколько счетов — обычная практика; разнесение совпадает с документом."})
            break
    for p in payments:
        if (p.get("fee_minor") or 0) > 0 and clean(p["payment_id"]):
            twins.append({"kind": "twin", "type": "fee", "claim": f"Из платежа {p['payment_id']} банк удержал комиссию",
                          "cards": [pay_card(p)],
                          "explain": "Комиссия банка проведена на расходы, долг клиента закрыт полностью. Это не недоплата."})
            break
    two = defaultdict(list)
    for r in ledger:
        if r["payment_id"]:
            two[r["payment_id"]].append(r)
    for pid, rs in two.items():
        accs = {r["account"] for r in rs}
        if "2150" in accs and "1200" in accs and clean(pid):
            r2150 = next(r for r in rs if r["account"] == "2150" and (r["credit_minor"] or 0) > 0)
            r1200 = next(r for r in rs if r["account"] == "1200" and (r["credit_minor"] or 0) > 0)
            twins.append({"kind": "twin", "type": "two_step", "claim": f"Платёж {pid} сначала лёг не на тот счёт",
                          "cards": [pay_card(pay_by[pid]), row_card(r2150, "сначала: 2150"), row_card(r1200, "потом: 1200")],
                          "explain": "Двухшаговое зачисление: деньги сначала на 2150, через день-два перенесены на 1200. Так разрешено политикой."})
            break

    # interleave errors and look-alikes so neither answer is predictable
    order: list[dict] = []
    for k in range(max(len(cases), len(twins))):
        if k < len(cases):
            order.append(cases[k])
        if k < len(twins):
            order.append(twins[k])
    order = order[:12]
    doc = {"episode_id": ep["episode_id"], "company": ep["manifest"]["company"], "cases": order}
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(order)} cases: {sum(c['kind'] == 'error' for c in order)} errors, {sum(c['kind'] == 'twin' for c in order)} look-alikes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

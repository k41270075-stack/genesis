"""Episode configuration: presets, overrides, bounds and seed-driven choices.

reset(seed, config) accepts:
  None                                  -> preset "default"
  "jury_like"                           -> a preset name
  {"preset": "...", "overrides": {...}} -> a preset plus nested overrides
  {...any other dict...}                -> overrides of the "default" preset

A preset value written as {"choice": [...]} or {"range": [lo, hi]} is resolved
from the episode seed (stream "config"), so one preset covers many companies:
currencies, offsets, periods, sizes and error mixes vary with the seed.
Fractions are given as decimal strings ("0.4"); JSON numbers are accepted and
converted exactly from their decimal text. Invalid configs fail loudly.
"""

from __future__ import annotations

import copy
from fractions import Fraction
from typing import Any

from .money import CURRENCY_EXPONENTS
from .rng import Stream
from .timeutil import PERIOD_KINDS, TimeFormatError, parse_date, parse_offset
from .version import CONFIG_VERSION

ERROR_TYPES = ("duplicate_invoice", "payment_allocation", "fx_conversion", "period_cutoff")
ERROR_VARIANTS = {
    "duplicate_invoice": ("double_posting", "duplicate_document"),
    "payment_allocation": ("missing", "partial"),
    "fx_conversion": ("wrong_date", "wrong_pair", "stale_rate"),
    "period_cutoff": ("right_early", "right_late", "left_early", "left_late"),
}
# Types whose plugins exist in this generator version.
IMPLEMENTED_TYPES = ERROR_TYPES
INTERACTIONS = ("partial_fx_boundary", "duplicate_with_partial")
MIXES = ("regular", "clean", "interaction")
MAX_ERRORS = 12
OFFSETS = ("+05:00", "+06:00", "+03:00", "+00:00", "-05:00", "+09:00", "-03:00", "+05:30")
MONTHS_2027 = tuple(f"2027-{m:02d}-01" for m in range(1, 13))


class ConfigError(ValueError):
    """The configuration is invalid; the message says which field and why."""


def _errors(counts: dict[str, Any]) -> dict[str, Any]:
    return {t: {"count": counts.get(t, 0), "variants": list(ERROR_VARIANTS[t])}
            for t in ERROR_TYPES}


_BASE: dict[str, Any] = {
    "config_version": CONFIG_VERSION,
    "company": {
        "base_currency": {"choice": ["KZT", "USD", "EUR"]},
        "timezone": {"choice": list(OFFSETS)},
        "bank_timezone": "+00:00",
        "period": "month",
        "period_start": {"choice": list(MONTHS_2027)},
    },
    "size": {
        "customers": {"range": [6, 18]},
        "invoices": {"range": [30, 70]},
        "target_ledger_rows": {"range": [250, 600]},
        "foreign_share": "0.4",
        "currencies": {"choice": [["USD", "EUR", "JPY"], ["EUR", "GBP"], ["USD", "CNY", "KWD"],
                                  ["KZT", "USD"], ["EUR", "JPY", "KZT"]]},
    },
    "policy": {
        "fx_rate_date": {"choice": ["same_day_or_previous", "previous_day_or_earlier"]},
        "rounding": {"choice": ["half_even", "half_up"]},
    },
    "mix": "regular",
    "errors": _errors({t: {"range": [0, 2]} for t in ERROR_TYPES}),
    "interactions": {"partial_fx_boundary": 0, "duplicate_with_partial": 0},
    "distractors": {"density": "0.3", "phantom_targets": True},
    "render": {"id_seed": 0, "order_seed": 0},
}


def _preset(**changes: Any) -> dict[str, Any]:
    cfg = copy.deepcopy(_BASE)
    for dotted, value in changes.items():
        node = cfg
        parts = dotted.split("__")
        for part in parts[:-1]:
            node = node[part]
        node[parts[-1]] = value
    return cfg


PRESETS: dict[str, dict[str, Any]] = {
    "default": _preset(),
    "smoke": _preset(size__customers=4, size__invoices=20, size__target_ledger_rows=200,
                     errors=_errors({"duplicate_invoice": 1, "period_cutoff": 1})),
    "clean": _preset(errors=_errors({})),
    "train": _preset(mix={"choice": ["regular", "regular", "clean", "interaction"]}),
    "dev": _preset(mix={"choice": ["regular", "regular", "clean", "interaction"]}),
    # 25 % clean companies, 25 % with an interaction scenario, like the jury's sample.
    "jury_like": _preset(mix={"choice": ["regular", "regular", "clean", "interaction"]},
                         errors=_errors({t: {"range": [0, 3]} for t in ERROR_TYPES})),
    "L1": _preset(errors=_errors({"duplicate_invoice": 1})),
    "L2": _preset(errors=_errors({"duplicate_invoice": 1, "period_cutoff": 1})),
    "L3": _preset(errors=_errors({t: 1 for t in ERROR_TYPES})),
    "L4": _preset(size__invoices={"range": [60, 120]},
                  size__target_ledger_rows={"range": [500, 1200]},
                  mix="interaction",
                  errors=_errors({t: 2 for t in ERROR_TYPES})),
    "L5": _preset(size__invoices={"range": [120, 180]},
                  size__target_ledger_rows={"range": [1200, 2000]},
                  interactions={"partial_fx_boundary": 1, "duplicate_with_partial": 1},
                  errors=_errors({t: 2 for t in ERROR_TYPES})),
    "corners_small": _preset(size__customers=3, size__invoices=40, size__target_ledger_rows=200,
                             errors=_errors({t: 3 for t in ERROR_TYPES})),
    "corners_large": _preset(size__invoices=200, size__target_ledger_rows=2000,
                             errors=_errors({})),
}

BOUNDS = {
    "customers": (3, 60),
    "invoices": (15, 200),
    "target_ledger_rows": (200, 2000),
}


def _merge(base: dict[str, Any], overrides: dict[str, Any], path: str = "") -> None:
    for key, value in overrides.items():
        where = f"{path}.{key}" if path else key
        if key not in base:
            raise ConfigError(f"unknown config field: {where}")
        special = {"choice", "range"}
        if (isinstance(base[key], dict) and isinstance(value, dict)
                and not special & set(base[key]) and not special & set(value)):
            _merge(base[key], value, where)
        else:
            base[key] = copy.deepcopy(value)


def _resolve(node: Any, stream: Stream) -> Any:
    if isinstance(node, dict):
        if set(node) == {"choice"}:
            options = node["choice"]
            if not isinstance(options, list) or not options:
                raise ConfigError("choice needs a non-empty list")
            return copy.deepcopy(stream.choice(options))
        if set(node) == {"range"}:
            lo, hi = node["range"]
            if type(lo) is not int or type(hi) is not int or lo > hi:
                raise ConfigError("range needs two ints lo <= hi")
            return stream.randint(lo, hi)
        return {k: _resolve(v, stream) for k, v in node.items()}
    if isinstance(node, list):
        return [_resolve(v, stream) for v in node]
    return node


def _fraction(value: Any, where: str) -> Fraction:
    if type(value) is int:
        return Fraction(value)
    if isinstance(value, str) or (isinstance(value, (int, float)) and type(value) is not bool):
        try:
            return Fraction(str(value))
        except (ValueError, ZeroDivisionError):
            pass
    raise ConfigError(f"{where} must be a decimal number")


def _int(value: Any, where: str, lo: int, hi: int) -> int:
    if type(value) is not int or not lo <= value <= hi:
        raise ConfigError(f"{where} must be an int from {lo} to {hi}")
    return value


def split_config(config: Any) -> tuple[str, dict[str, Any]]:
    if config is None:
        return "default", {}
    if isinstance(config, str):
        return config, {}
    if not isinstance(config, dict):
        raise ConfigError("config must be null, a preset name or an object")
    if set(config) <= {"preset", "overrides"}:
        preset = config.get("preset", "default")
        overrides = config.get("overrides") or {}
        if not isinstance(preset, str) or not isinstance(overrides, dict):
            raise ConfigError("config.preset must be a string and config.overrides an object")
        return preset, overrides
    return "default", config


def resolve_config(config: Any, seed: int) -> dict[str, Any]:
    """Return a fully concrete, validated config for one episode."""
    preset, overrides = split_config(config)
    if preset not in PRESETS:
        raise ConfigError(f"unknown preset {preset!r}; known: {', '.join(sorted(PRESETS))}")
    raw = copy.deepcopy(PRESETS[preset])
    _merge(raw, overrides)
    stream = Stream.root(seed, "config")
    cfg = _resolve(raw, stream)
    cfg["preset"] = preset
    # Only seed-drawn counts are trimmed; explicit overrides fail loudly instead.
    _apply_mix(cfg, stream.child("mix"),
               trim="errors" not in overrides and "interactions" not in overrides)
    validate(cfg)
    return cfg


def _apply_mix(cfg: dict[str, Any], stream: Stream, trim: bool) -> None:
    mix = cfg.get("mix", "regular")
    if mix not in MIXES:
        raise ConfigError(f"mix must be one of {list(MIXES)}")
    if mix == "clean":
        for etype in ERROR_TYPES:
            cfg["errors"][etype]["count"] = 0
        cfg["interactions"] = {name: 0 for name in INTERACTIONS}
    elif mix == "interaction" and not any(cfg["interactions"].values()):
        # X1 needs a non-zero company offset (local and UTC dates must differ).
        options = (list(INTERACTIONS) if cfg["company"]["timezone"] != "+00:00"
                   else ["duplicate_with_partial"])
        cfg["interactions"][stream.choice(options)] = 1
    # Seed-drawn counts never exceed the episode limit: trim the largest first.
    if trim and mix != "clean" and all(type(v) is int for v in cfg["interactions"].values()):
        def total() -> int:
            return (sum(cfg["errors"][t]["count"] for t in ERROR_TYPES
                        if type(cfg["errors"][t]["count"]) is int)
                    + 2 * sum(cfg["interactions"].values()))
        while total() > MAX_ERRORS:
            largest = max(ERROR_TYPES, key=lambda t: (cfg["errors"][t]["count"], t))
            if cfg["errors"][largest]["count"] == 0:
                break
            cfg["errors"][largest]["count"] -= 1


def validate(cfg: dict[str, Any]) -> None:
    if cfg.get("config_version") != CONFIG_VERSION:
        raise ConfigError(f"config_version must be {CONFIG_VERSION!r}")
    company = cfg["company"]
    base = company["base_currency"]
    if base not in CURRENCY_EXPONENTS:
        raise ConfigError("company.base_currency is not a supported currency")
    try:
        parse_offset(company["timezone"])
        parse_offset(company["bank_timezone"])
        start = parse_date(company["period_start"])
    except TimeFormatError as exc:
        raise ConfigError(f"company: {exc}") from None
    if company["period"] not in PERIOD_KINDS:
        raise ConfigError("company.period must be month or quarter")
    if start.day != 1 or (company["period"] == "quarter" and (start.month - 1) % 3):
        raise ConfigError("company.period_start must start a month (or a quarter)")

    size = cfg["size"]
    for field, (lo, hi) in BOUNDS.items():
        _int(size[field], f"size.{field}", lo, hi)
    share = _fraction(size["foreign_share"], "size.foreign_share")
    if not 0 <= share <= 1:
        raise ConfigError("size.foreign_share must be within [0, 1]")
    size["foreign_share"] = str(share.numerator) + "/" + str(share.denominator)
    currencies = size["currencies"]
    if not isinstance(currencies, list) or any(c not in CURRENCY_EXPONENTS for c in currencies):
        raise ConfigError("size.currencies must list supported currencies")
    size["currencies"] = [c for c in dict.fromkeys(currencies) if c != base]
    if share > 0 and not size["currencies"]:
        size["foreign_share"] = "0/1"

    policy = cfg["policy"]
    if policy["fx_rate_date"] not in ("same_day_or_previous", "previous_day_or_earlier"):
        raise ConfigError("policy.fx_rate_date is invalid")
    if policy["rounding"] not in ("half_even", "half_up"):
        raise ConfigError("policy.rounding is invalid")

    total = 0
    for etype in ERROR_TYPES:
        spec = cfg["errors"].get(etype)
        if not isinstance(spec, dict):
            raise ConfigError(f"errors.{etype} must be an object")
        count = _int(spec.get("count"), f"errors.{etype}.count", 0, MAX_ERRORS)
        variants = spec.get("variants")
        if not isinstance(variants, list) or not variants or \
                any(v not in ERROR_VARIANTS[etype] for v in variants):
            raise ConfigError(f"errors.{etype}.variants must be a non-empty subset of "
                              f"{list(ERROR_VARIANTS[etype])}")
        if count and etype not in IMPLEMENTED_TYPES:
            raise ConfigError(f"errors.{etype}: not implemented in this generator version")
        total += count
    if set(cfg["interactions"]) != set(INTERACTIONS):
        raise ConfigError(f"interactions must have exactly {list(INTERACTIONS)}")
    for name, value in cfg["interactions"].items():
        total += 2 * _int(value, f"interactions.{name}", 0, MAX_ERRORS // 2)
    if total > MAX_ERRORS:
        raise ConfigError(f"at most {MAX_ERRORS} errors per episode (an interaction counts 2)")

    density = _fraction(cfg["distractors"]["density"], "distractors.density")
    if not 0 <= density <= Fraction(6, 10):
        raise ConfigError("distractors.density must be within [0, 0.6]")
    cfg["distractors"]["density"] = f"{density.numerator}/{density.denominator}"
    for field in ("id_seed", "order_seed"):
        value = cfg["render"][field]
        if type(value) is not int or value < 0:
            raise ConfigError(f"render.{field} must be a non-negative int")

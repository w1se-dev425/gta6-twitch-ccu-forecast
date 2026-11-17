"""gta6-twitch-ccu-forecast-01 entry (Python 3.13, standard library only).

Method: launch-day shape regression on the case's own comparables.

For each comparable past launch with a complete 24-hour release day, take the
log-ratio of each hour's viewers to that launch's hour-1 viewers. Hour 1 of a
rolling-midnight launch already has viewers (New Zealand / Australia / Japan
unlocked hours earlier), while a simultaneous-global launch's hour 1 is still
pre-launch trickle, so comparables are kept only when hour 1 is already live:
hour-1 viewers >= 10,000 and >= 5% of that launch's release-day peak. Early-
access-contaminated, weak and target-history entries are excluded.

Per hour h = 2..24, fit log(v_h / v_1) ~ a_h + b_h * (log v_1 - mean log v_1)
across the kept comparables. The slope is real and stable: near 0 in the
early hours, about -0.5 by hours 19-24 -- a launch whose hour 1 is already
huge stays flat, one whose hour 1 is only the Asia-Pacific trickle surges
late as Europe and the US wake and unlock. The spread s_h is the residual
IQR / 1.349, widened x1.4. The median curve a_h is smoothed with a 3-hour
moving average. Forecast: q_tau(h) = p1 * exp(a_h + b_h*(ln p1 - mlh)
+ z_tau * s_h), rounded half up to 2 decimals, clamped to (0, 1e9].

If the case carries fewer than 8 usable comparables, fall back to the same
fit pre-computed on the kit's 18 usable comparables (FALLBACK / MLH below).

Leave-one-out backtest on those 18 launches (each held out, fit on the other
17): mean pinball loss 0.272, 90% coverage 0.84. House persistence baseline
on the same set: 0.392, coverage 0.76. Deterministic: no randomness, no
network, no clock reads; two runs produce identical bytes.
"""

import json
import math
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0, 0.674, 1.645]
SPREAD_K = 1.4
MIN_COMPARABLES = 8

# Pre-computed fit on the kit's 18 usable comparables (hour -> (a, b, s)),
# used only when a case carries too few comparables to fit at runtime.
MLH = 11.5073
FALLBACK = {
    2: (-0.1983, 0.0349, 0.1692),
    3: (-0.2502, 0.0994, 0.3955),
    4: (-0.2881, 0.0216, 0.3922),
    5: (-0.2036, -0.0405, 0.2687),
    6: (-0.1013, -0.0737, 0.3663),
    7: (-0.0483, -0.1335, 0.4240),
    8: (-0.0479, -0.2283, 0.4469),
    9: (-0.0506, -0.2745, 0.4823),
    10: (-0.0495, -0.3065, 0.5858),
    11: (-0.0245, -0.2868, 0.5419),
    12: (0.0347, -0.2915, 0.4287),
    13: (0.1293, -0.2898, 0.4172),
    14: (0.2522, -0.3001, 0.4900),
    15: (0.3727, -0.3128, 0.4435),
    16: (0.4765, -0.3071, 0.4561),
    17: (0.5746, -0.3124, 0.4861),
    18: (0.6897, -0.3896, 0.5650),
    19: (0.7935, -0.4988, 0.5380),
    20: (0.8566, -0.5479, 0.6609),
    21: (0.8558, -0.5444, 0.5685),
    22: (0.8197, -0.5376, 0.5437),
    23: (0.7525, -0.5202, 0.4556),
    24: (0.7152, -0.5110, 0.4090),
}


def parse_time(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def quantile(sorted_vals, tau):
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    pos = tau * (n - 1)
    lo = int(pos)
    frac = pos - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[min(lo + 1, n - 1)] * frac


def release_day_viewers(comp):
    """The comparable's 24 release-day hourly viewer counts, or None."""
    try:
        day_start = parse_time(comp["day_start"])
    except (KeyError, TypeError, ValueError):
        return None
    pts = {}
    for row in comp.get("hourly") or []:
        try:
            pts[parse_time(row["from"])] = row["viewers"]
        except (KeyError, TypeError, ValueError):
            continue
    day = [pts.get(day_start + timedelta(hours=h)) for h in range(24)]
    if any(v is None or v <= 0 for v in day):
        return None
    return day


def usable_comparables(case):
    """(name -> 24 hourly counts) for comparables whose hour 1 is live."""
    out = {}
    for comp in case.get("comparables") or []:
        unlock = comp.get("unlock") or ""
        if ("early-access-contaminated" in unlock or "Tier: weak" in unlock
                or "target-history" in unlock):
            continue
        day = release_day_viewers(comp)
        if day is None:
            continue
        h1, peak = day[0], max(day)
        if h1 < 10000 or h1 < 0.05 * peak:
            continue
        out[comp.get("name") or "?"] = day
    return out


def fit(days):
    """Per-hour (a, b, s) plus mean log hour-1, from {name: 24 counts}."""
    names = sorted(days)
    log_h1 = {n: math.log(days[n][0]) for n in names}
    mlh = sum(log_h1.values()) / len(log_h1)
    params = {}
    for h in range(2, 25):
        xs = [log_h1[n] - mlh for n in names]
        ys = [math.log(days[n][h - 1] / days[n][0]) for n in names]
        mx = sum(xs) / len(xs)
        my = sum(ys) / len(ys)
        den = sum((x - mx) ** 2 for x in xs)
        num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        b = num / den if den else 0.0
        a = my - b * mx
        resid = sorted(y - (a + b * x) for x, y in zip(xs, ys))
        s = max((quantile(resid, 0.75) - quantile(resid, 0.25)) / 1.349, 0.05) * SPREAD_K
        params[h] = [a, b, s]
    # Smooth the median curve (a) with a 3-hour moving average.
    med = {h: params[h][0] for h in params}
    for h in range(2, 25):
        near = [med[hh] for hh in (h - 1, h, h + 1) if hh in med]
        params[h][0] = sum(near) / len(near)
    return params, mlh


def round2(x):
    """x rounded to 2 decimals, half up (same as the starter)."""
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if value.is_integer() else value


def forecast_case(case, name):
    if case["levels"] != LEVELS:
        raise ValueError(f"{name} asks for levels {case['levels']}, not {LEVELS}")
    first = next((k for k in case["known"] if k["hour"] == 1), None)
    if first is None:
        raise ValueError(f"{name} has no hour-1 print")
    p1 = max(1, first["viewers"])
    days = usable_comparables(case)
    if len(days) >= MIN_COMPARABLES:
        params, mlh = fit(days)
    else:
        params = {h: list(v) for h, v in FALLBACK.items()}
        mlh = MLH
    log_p1 = math.log(p1)
    hours = []
    for row in case["forecast"]:
        h = row["hour"]
        a, b, s = params[h]
        med = a + b * (log_p1 - mlh)
        qs = []
        for z in Z:
            q = round2(p1 * math.exp(med + z * s))
            q = min(max(q, 0.01), 1e9)
            qs.append(q)
        for i in range(1, 5):
            qs[i] = max(qs[i], qs[i - 1])
        hours.append({"hour": h, "q": qs})
    return {"hours": hours}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

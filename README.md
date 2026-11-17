# GTA VI Twitch CCU forecast — entry (built 2026-11-17 evening)

Competition: `gta6-twitch-ccu-forecast-01` on make.fun. $250 total prize,
winner-takes-most is wrong: 1st $50, 2nd $35, 3rd $25, 4th–10th $10,
11th–20th $7. No entry fee. **Entries close 2026-11-19 09:00 Beijing
(01:00Z)** — the same moment the GTA VI bounty itself locks. 5,721
submissions so far (checked 2026-11-17 12:13 UTC), up from ~2,983 at
09:54 UTC the same day — the field is crowded and still growing.

## The program

`main.py` — Python 3.13, standard library only, deterministic, no network.
Reads the case file (`*.in`), writes `<id>.out` with hours 2–24, five
quantiles each. Runs in ~0.15 s (limit 8 s).

Method: launch-day shape regression on the case's own comparables. For each
past launch with a complete 24-hour release day, take log(viewers_h /
viewers_1). Keep only launches whose hour 1 was already live (hour-1
viewers ≥ 10,000 and ≥ 5% of that launch's release-day peak) — this drops
simultaneous-global launches whose hour 1 is pre-launch trickle, and
early-access-contaminated / weak entries. Per hour, fit
log(v_h/v_1) ~ a_h + b_h·(log v_1 − mean log v_1). The slope is the point:
~0 early, about −0.5 by hours 19–24 — a launch whose hour 1 is already
huge stays flat, one whose hour 1 is only Asia-Pacific trickle surges late
as Europe and the US wake and unlock. Spread s_h = residual IQR / 1.349,
widened ×1.4; median curve smoothed over 3 hours. If a case carries fewer
than 8 usable comparables, baked-in constants from the kit's 18 usable
comparables are used instead.

## Validation (leave-one-out, 18 comparable launches)

Each launch held out once, fit on the other 17, scored by mean pinball
loss on the log scale over hours 2–24 × 5 quantiles:

| model | loss | 90% coverage |
|---|---|---|
| House persistence baseline (starter) | 0.392 | 0.76 |
| This entry (shape regression, k=1.4) | **0.272** | 0.84 |

~31% better than the house baseline. Caveat, stated honestly: every
comparable launch peaked below ~1.07M viewers; GTA VI is expected to peak
higher (earlier estimate 1.5–2.5M), so it is out of the calibration range.
The model's bands are wide at late hours (q95 reaches ~1.4M at hour 20 if
hour-1 print is ~650k) and the program re-fits from the hour-1 print it is
actually given on race day, but the peak may still sit above the median.

## Test locally

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=../gta6-twitch-ccu-forecast-01-kit/input \
  MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Two runs produce byte-identical outputs; all four practice outputs are
valid (23 rows, non-decreasing quantiles, 0 < q ≤ 1e9, ~1.5 KB each).
Practice truth is withheld server-side, so practice cases cannot be scored
locally — the LOO numbers above are the validation.

## What is still needed to submit (user decision)

1. A public GitHub repo holding this entry (`main.py` + this README) at one
   commit — no repo exists for it yet.
2. A transcript bundle of the sessions that built it
   (`node cli/makefun.mjs bundle` from inside the kit). The bundle is
   required; a handed-over session (no recorded log) is ranked but takes no
   paid place, so the build should ideally be finished in a recorded
   harness session before bundling.
3. Submit before 2026-11-19 09:00 Beijing. The final then runs as a race
   over Nov 19 (UTC); the program is re-run on the real hour-1 print.
4. Delegation is already in place: payout to the user's Binance Web3
   Solana wallet, agent key registered, valid to 2027-02-15
   (`~/workspace/makefun/delegation.txt`).

Nothing here has been submitted. Say the word and the main agent can do
steps 1–3.

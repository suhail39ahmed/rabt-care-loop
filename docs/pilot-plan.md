# Pilot plan — 12 weeks (#65)

**Programme:** HbA1c follow-up at one primary-care network (illustrative).  
**Safety path:** deterministic rules + HITL; LLM optional and kill-switched.

## Phases

| Weeks | Mode | Exit criteria |
|---|---|---|
| 1–3 | Shadow | Rules signed off; no patient messaging |
| 4–7 | Assisted | Coordinators act on queue; dual close live |
| 8–12 | Live (limited) | Verified closure ≥ target; false closures = 0 |

## KPI targets (pilot)

| KPI | Target | Assumption |
|---|---|---|
| Median time-to-owner | ≤ 4 h business | Staffed board hours |
| Verified closure rate | ≥ 90% | Attend + outcome or 4-eyes |
| Critical recall | 100% | Ladder + expert call logged |
| Teach-back first-pass | ≥ 70% | AR/EN templates |
| False closures | 0 | Hard gate in verifier |

## Cost / scale (order-of-magnitude)

Assumptions: SQLite→Postgres, 2 small containers, SMS optional, LLM off on safety path.

| Volume / month | Compute | Storage | Messaging | Optional LLM |
|---|---|---|---|---|
| 10k results | ~$80–150 | <$20 | ~$50 if SMS | $0–40 |
| 100k results | ~$400–700 | <$50 | scales linearly | $0–300 |

Every figure is an estimate for planning — not a quote.

## Governance

- Thresholds require clinician / DoH sign-off before live.
- Data protection: demo personas ≠ production auth (see threat model).
- Exit: any false closure or critical miss stops live mode.

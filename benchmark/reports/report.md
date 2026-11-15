# Benchmark report (simulated, synthetic)

**Label:** simulated, synthetic — not real-world outcomes
**Seed:** 42 · **N:** 1000

| Metric | Rabt | Baseline |
| --- | --- | --- |
| Closure rate | 100.0% | 100.0% |
| Median time to next step (min) | 104 | 331 |
| Critical recall | 100.0% | 53.1% |
| False closures | 0 | 129 |

## Fairness slices

### age_band
| Value | N | Rabt critical recall | Rabt false closures |
| --- | --- | --- | --- |
| 18-39 | 383 | 100.0% | 0 |
| 40-59 | 332 | 100.0% | 0 |
| 60+ | 285 | 100.0% | 0 |

### sex
| Value | N | Rabt critical recall | Rabt false closures |
| --- | --- | --- | --- |
| female | 506 | 100.0% | 0 |
| male | 494 | 100.0% | 0 |

### nationality_group
| Value | N | Rabt critical recall | Rabt false closures |
| --- | --- | --- | --- |
| GCC | 323 | 100.0% | 0 |
| Other | 336 | 100.0% | 0 |
| UAE | 341 | 100.0% | 0 |

### insurance
| Value | N | Rabt critical recall | Rabt false closures |
| --- | --- | --- | --- |
| plan-a | 239 | 100.0% | 0 |
| plan-b | 214 | 100.0% | 0 |
| plan-c | 239 | 100.0% | 0 |
| self-pay | 308 | 100.0% | 0 |

Rabt scores **0 false closures** and **100% critical recall** on this synthetic run.

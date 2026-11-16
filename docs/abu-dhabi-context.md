# Abu Dhabi context (sourced vs assumed)

**Disclaimer:** Rabt is an independent prototype for the Future Health Digital Innovation Challenge. **Nothing in this repository implies affiliation with, endorsement by, or integration into** the Department of Health – Abu Dhabi (DoH), Abu Dhabi Public Health Center (ADPHC), Malaffi, or Sahatna / Sehatna. Product names appear only to describe the public care landscape we are designing *against*.

Access dates for all links below: **16 Nov 2026**.

## Public programmes the seeded cases illustrate

Abu Dhabi’s adult periodic screening (often branded **IFHAS** — Periodic Comprehensive Screening Program for Adults) covers cardiovascular risk factors and selected cancers, among other packages.

| Seeded demo case | Clinical motif | Programme fit (public) |
|---|---|---|
| Fatima HbA1c (`case-gc01-fatima`) | Diabetes / glycaemic follow-up | CVD risk factors include diabetes; adult PCSP includes blood sugar + HbA1c on a scheduled cadence |
| Critical BP (`case-gc02-bp`) | Hypertension / critical vitals | BP measurement is part of adult screening packages |
| FIT (`case-gc05-fit`) | Colorectal screening | FIT / colonoscopy pathways in adult cancer screening |
| Cervical (`case-gc08-consent`) | Cervical cytology | Pap ± HPV in the adult cancer package |
| Mammography (awaiting-owner seed when present) | Breast imaging motif | Mammogram schedules in DoH adult screening specs |

**Sources (programme scope):**

1. ADPHC — IFHAS overview (eligibility Thiqa holders 18–75; chronic disease and cancer screening framing): https://www.adphc.gov.ae/en/Public-Health-Programs/IFHAS  
2. DoH — Service requirements / PCSP for adults (CVD risk factors incl. diabetes & hypertension; cancers incl. breast, cervical, colorectal; FIT cadence described in tables): https://www.doh.gov.ae/-/media/5ADAFA38E88748A6B0A9E6E2E241AD49.ashx  
3. DoH — IFHAS / PCSP reporting template (results reporting; tracking via Malaffi; results tag in Sahatna): https://www.doh.gov.ae/-/media/EE758C3B77314BC394F2479AEF803AA2.ashx  

## Where results flow today (public description)

| System | Public role | Rabt stance |
|---|---|---|
| **Malaffi** | Abu Dhabi HIE — providers share records across the emirate | **Mocked** in the demo. Target intake is FHIR `Observation` (and related) from an HIE / AHDS-style feed — not a live Malaffi connection. |
| **Sahatna / Sehatna** | DoH patient app — appointments, Malaffi-backed records, screening visibility | **Mocked**. Patient card is a Rabt web surface standing in for “patient receives an explanation + next step”. |

**Sources:**

4. Sahatna FAQ — “What is Malaffi?” and screening-result access framing: https://sahatna-app.doh.gov.ae/en/faqs/  
5. Malaffi news — DoH launch of Sahatna (records + screening/vaccine context): https://www.malaffi.ae/the-department-of-health-abu-dhabi-launches-sahatna-the-revolutionary-all-in-one-healthcare-mobile-app/  

## Where Rabt sits

```
Lab / screening facility → (today) e-claims / Malaffi / clinic follow-up
                         ↘
                           Rabt care-loop (proposed): ownership → explain → navigate → evidence close
                         ↗
Patient app (Sahatna-like) · clinician board · optional Foundry wording only
```

Rabt does **not** replace Malaffi or Sahatna. It proposes a deterministic ownership + navigation + evidence-closure layer for actionable screening results so the loop does not leak between “abnormal result” and “care happened”.

## Assumed vs sourced

| Claim | Status |
|---|---|
| IFHAS / PCSP screens for diabetes risk, BP, colorectal (FIT), cervical, breast | **Sourced** (1–3) |
| Malaffi is the Abu Dhabi HIE; Sahatna surfaces records / screening context | **Sourced** (4–5) |
| Providers tag IFHAS participants for Malaffi tracking / Sahatna results | **Sourced** (3) |
| Numeric triage thresholds (e.g. HbA1c 7.2 %, BP 190) | **Assumed / illustrative** — pending clinician / DoH sign-off |
| SLA hours, ladder delays, navigator weights | **Assumed / illustrative** |
| Synthetic cohort mix and personas | **Assumed** — demo only |
| Live Malaffi or Sahatna API integration | **Not claimed** — out of scope for this prototype |

## Integration path (pilot direction)

**FHIR resources (illustrative):**

| Resource | Direction | Use |
|---|---|---|
| `Observation` | Read (ingest) | Triggering screening result |
| `Task` | Write / update | Case workflow status (maps from state machine) |
| `Communication` | Write | Patient-facing notice (no result values over SMS) |
| `Provenance` | Write | Who/what decided each transition |

**Identity:**

- Clinicians / coordinators → Microsoft Entra ID (pilot)
- Patients / consent → UAE PASS or programme IdP (pilot)
- Demo today → `X-Rabt-Persona` only (not production IAM)

**Language:** Arabic-first patient messaging with English twin templates; teach-back in both languages.

## README / deck claims map

| Surface claim | Cite here |
|---|---|
| “Abu Dhabi screening programmes” / Population Health challenge framing | This doc §programmes + sources 1–3 |
| Malaffi / Sehatna as ecosystem context | §results flow + sources 4–5 |
| Thresholds / SLAs illustrative | §assumed vs sourced |
| No affiliation | Top disclaimer |

Deck problem/solution slides should point to this file rather than inventing new Abu Dhabi facts.

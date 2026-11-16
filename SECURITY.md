# Security Policy

## Scope

Rabt is a **synthetic-data demo**. Do not send real patient data, PHI, or production credentials into any deployed instance.

## Reporting

Email the maintainer listed on the GitHub profile, or open a private security advisory on this repository.

Please include:

- Affected URL or component
- Steps to reproduce
- Impact assessment

## Supported versions

Only the `main` branch of this repository is maintained for the hackathon demo window.

## Practice

- Demo writes require `X-Rabt-Persona` from a fixed allow-list.
- Ingest / webhooks require `X-Rabt-Ingest-Secret` when that env var is set.
- No real PHI is accepted; reports that include PHI will be deleted.

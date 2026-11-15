"""Synthetic labs feed — posts Observations to the orchestrator ingest API."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "orchestrator"))
from app.demo_seed import obs_bp_critical, obs_fit_positive, obs_hba1c


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://localhost:8000")
    p.add_argument("--kind", choices=["hba1c", "bp", "fit"], default="hba1c")
    args = p.parse_args()
    patient_id = "pat-demo"
    if args.kind == "hba1c":
        obs = obs_hba1c(patient_id)
    elif args.kind == "bp":
        obs = obs_bp_critical(patient_id)
    else:
        obs = obs_fit_positive(patient_id)
    payload = {
        "patient_id": patient_id,
        "patient": {"id": patient_id, "language": "en", "plan_id": "plan-b"},
        "observation": obs,
        "idempotency_key": f"labs-mock/{obs['id']}",
    }
    r = httpx.post(f"{args.base}/cases/ingest", json=payload, timeout=30)
    r.raise_for_status()
    print(r.json())


if __name__ == "__main__":
    main()

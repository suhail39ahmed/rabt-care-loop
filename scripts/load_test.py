#!/usr/bin/env python3
"""Local ingest load test (#66). Do NOT point at the shared live demo."""

from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import time

import httpx


async def one(client: httpx.AsyncClient, url: str, secret: str, i: int) -> float:
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["X-Rabt-Ingest-Secret"] = secret
    payload = {
        "patient_id": f"load-{i}",
        "idempotency_key": f"load-{time.time_ns()}-{i}",
        "observation": {
            "id": f"obs-load-{i}",
            "code": {"text": "HbA1c"},
            "valueQuantity": {"value": 7.0 + (i % 5) * 0.1, "unit": "%"},
        },
        "patient": {"id": f"load-{i}", "name": f"Load {i}", "language": "en"},
    }
    t0 = time.perf_counter()
    r = await client.post(f"{url}/cases/ingest", json=payload, headers=headers)
    dt = time.perf_counter() - t0
    if r.status_code >= 400:
        raise RuntimeError(f"ingest failed {r.status_code}: {r.text[:200]}")
    return dt


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.environ.get("LOAD_BASE_URL", "http://127.0.0.1:8000"))
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--concurrency", type=int, default=5)
    args = ap.parse_args()
    if "azurecontainerapps.io" in args.base_url and os.environ.get("LOAD_ALLOW_REMOTE") != "1":
        raise SystemExit("Refusing to load-test the hosted demo (set LOAD_ALLOW_REMOTE=1 to override).")
    secret = os.environ.get("RABT_INGEST_SECRET", "")
    latencies: list[float] = []
    sem = asyncio.Semaphore(args.concurrency)

    async with httpx.AsyncClient(timeout=30.0) as client:
        async def bound(i: int) -> None:
            async with sem:
                latencies.append(await one(client, args.base_url.rstrip("/"), secret, i))

        t0 = time.perf_counter()
        await asyncio.gather(*(bound(i) for i in range(args.n)))
        elapsed = time.perf_counter() - t0

    latencies.sort()
    p50 = statistics.median(latencies)
    p95 = latencies[max(0, int(len(latencies) * 0.95) - 1)]
    print(f"n={args.n} concurrency={args.concurrency} elapsed_s={elapsed:.2f}")
    print(f"throughput_rps={args.n / elapsed:.2f}")
    print(f"p50_s={p50:.4f} p95_s={p95:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

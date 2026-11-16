"""Azure Monitor (Application Insights) via OpenTelemetry, only when configured.

APPLICATIONINSIGHTS_CONNECTION_STRING is set by Terraform on the API container app. Requests, outgoing
HTTP calls (APIM, Content Safety, Search) and the `rabt.ai` log events (tokens, cache hit/miss, PII
redaction counts, safety blocks, failovers) are exported. No prompt text is logged anywhere.
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger("rabt.monitoring")
_configured = False


def configure() -> bool:
    global _configured
    if _configured:
        return True
    conn = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip()
    if not conn:
        return False
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
    except ImportError:
        log.warning("azure-monitor-opentelemetry not installed; telemetry off")
        return False
    configure_azure_monitor(
        connection_string=conn,
        logger_name="rabt",
        enable_live_metrics=True,
    )
    logging.getLogger("rabt").setLevel(logging.INFO)
    _configured = True
    return True

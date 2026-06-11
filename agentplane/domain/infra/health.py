"""Infrastructure health check - structured health summary from 1Panel evidence."""

from __future__ import annotations

from typing import Any

from agentplane.providers import get_provider
from agentplane.providers.gateway import default_provider_gateway


def _severity_from_usage(percent: float) -> str:
    """Classify resource usage severity."""
    if percent >= 90:
        return "critical"
    if percent >= 80:
        return "warning"
    if percent >= 60:
        return "elevated"
    return "normal"


def _disk_summary(disks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Summarize disk usage with severity."""
    summaries = []
    for disk in disks:
        if not isinstance(disk, dict):
            continue
        used_percent = disk.get("usedPercent", 0)
        summaries.append({
            "path": disk.get("path", ""),
            "device": disk.get("device", ""),
            "total_bytes": disk.get("total", 0),
            "free_bytes": disk.get("free", 0),
            "used_percent": used_percent,
            "severity": _severity_from_usage(used_percent),
        })
    return summaries


def _process_summary(processes: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    """Summarize top processes."""
    summaries = []
    for proc in processes[:limit]:
        if not isinstance(proc, dict):
            continue
        summaries.append({
            "name": proc.get("name", ""),
            "pid": proc.get("pid", 0),
            "cpu_percent": proc.get("percent", 0),
            "memory_bytes": proc.get("memory", 0),
            "user": proc.get("user", ""),
        })
    return summaries


def _alert_summary(alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Summarize recent alerts."""
    summaries = []
    for alert in alerts:
        if not isinstance(alert, dict):
            continue
        summaries.append({
            "id": alert.get("id", 0),
            "type": alert.get("type", ""),
            "title": alert.get("title", ""),
            "status": alert.get("status", ""),
            "created_at": str(alert.get("createdAt", "")),
        })
    return summaries


def _overall_health_status(
    cpu_percent: float,
    memory_percent: float,
    load_usage: float,
    disks: list[dict[str, Any]],
    recent_alerts: list[dict[str, Any]],
) -> str:
    """Determine overall health status."""
    # Check for critical conditions
    if cpu_percent >= 95 or memory_percent >= 95:
        return "critical"
    if load_usage >= 90:
        return "critical"
    for disk in disks:
        if isinstance(disk, dict) and disk.get("usedPercent", 0) >= 95:
            return "critical"

    # Check for warning conditions
    if cpu_percent >= 80 or memory_percent >= 80:
        return "warning"
    if load_usage >= 80:
        return "warning"
    for disk in disks:
        if isinstance(disk, dict) and disk.get("usedPercent", 0) >= 80:
            return "warning"

    # Check for firing alerts
    firing_alerts = [a for a in recent_alerts if isinstance(a, dict) and a.get("status") == "firing"]
    if firing_alerts:
        return "warning"

    return "healthy"


def check_infra_health(target: str) -> dict[str, Any]:
    """Perform infrastructure health check and return structured summary.

    This is a read-only evidence collection that queries 1Panel dashboard,
    alerts, and monitor APIs to produce a structured health summary.
    """
    provider = get_provider()
    executor = provider.get_target(target)

    # Collect dashboard metrics
    dashboard_current = provider.get_dashboard(executor)
    # TODO: Migrate to ProviderProtocol when health methods are added
    dashboard_base = default_provider_gateway().get_onepanel_dashboard_base(executor)

    # Collect top processes
    # TODO: Migrate to ProviderProtocol when health methods are added
    _gw = default_provider_gateway()
    try:
        top_cpu = _gw.get_onepanel_dashboard_top_cpu(executor)
    except Exception:
        top_cpu = []
    try:
        top_mem = _gw.get_onepanel_dashboard_top_mem(executor)
    except Exception:
        top_mem = []

    # Collect alerts
    try:
        alerts_payload = _gw.search_onepanel_alerts(executor, status="enable")
        active_alerts = alerts_payload.get("items", []) if isinstance(alerts_payload, dict) else []
    except Exception:
        active_alerts = []

    try:
        alert_logs_payload = _gw.search_onepanel_alert_logs(executor, status="firing")
        firing_alerts = alert_logs_payload.get("items", []) if isinstance(alert_logs_payload, dict) else []
    except Exception:
        firing_alerts = []

    # Collect monitor settings
    try:
        monitor_setting = _gw.get_onepanel_monitor_setting(executor)
    except Exception:
        monitor_setting = {}

    # Extract key metrics
    cpu_percent = dashboard_current.get("cpuUsedPercent", 0)
    memory_percent = dashboard_current.get("memoryUsedPercent", 0)
    load1 = dashboard_current.get("load1", 0)
    load5 = dashboard_current.get("load5", 0)
    load15 = dashboard_current.get("load15", 0)
    load_usage = dashboard_current.get("loadUsagePercent", 0)
    uptime = dashboard_current.get("uptime", 0)
    procs = dashboard_current.get("procs", 0)

    # Build structured summary
    disks = dashboard_current.get("diskData", [])
    disk_summaries = _disk_summary(disks if isinstance(disks, list) else [])

    overall_status = _overall_health_status(
        cpu_percent, memory_percent, load_usage, disks if isinstance(disks, list) else [], firing_alerts
    )

    return {
        "target": target,
        "status": overall_status,
        "hostname": dashboard_base.get("hostname", ""),
        "os": dashboard_base.get("prettyDistro", dashboard_base.get("os", "")),
        "kernel": dashboard_base.get("kernelVersion", ""),
        "uptime_seconds": uptime,
        "process_count": procs,
        "cpu": {
            "cores": dashboard_base.get("cpuLogicalCores", dashboard_base.get("cpuCores", 0)),
            "model": dashboard_base.get("cpuModelName", ""),
            "used_percent": cpu_percent,
            "severity": _severity_from_usage(cpu_percent),
        },
        "memory": {
            "total_bytes": dashboard_current.get("memoryTotal", 0),
            "used_bytes": dashboard_current.get("memoryUsed", 0),
            "available_bytes": dashboard_current.get("memoryAvailable", 0),
            "used_percent": memory_percent,
            "severity": _severity_from_usage(memory_percent),
        },
        "load": {
            "load1": load1,
            "load5": load5,
            "load15": load15,
            "usage_percent": load_usage,
            "severity": _severity_from_usage(load_usage),
        },
        "disks": disk_summaries,
        "network": {
            "bytes_sent": dashboard_current.get("netBytesSent", 0),
            "bytes_recv": dashboard_current.get("netBytesRecv", 0),
        },
        "top_cpu_processes": _process_summary(top_cpu),
        "top_mem_processes": _process_summary(top_mem),
        "alerts": {
            "active_rules": len(active_alerts),
            "firing_count": len(firing_alerts),
            "firing": _alert_summary(firing_alerts[:5]),
        },
        "monitor": {
            "status": monitor_setting.get("monitorStatus", "unknown"),
            "store_days": monitor_setting.get("monitorStoreDays", ""),
            "interval_minutes": monitor_setting.get("monitorInterval", ""),
        },
        "resource_counts": {
            "websites": dashboard_base.get("websiteNumber", 0),
            "databases": dashboard_base.get("databaseNumber", 0),
            "cronjobs": dashboard_base.get("cronjobNumber", 0),
            "apps_installed": dashboard_base.get("appInstalledNumber", 0),
        },
    }

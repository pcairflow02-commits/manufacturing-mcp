"""
Manufacturing MCP Server

Exposes work orders, machine status, inventory, quality logs,
on-time dispatch, and vehicle tracking as tools an AI assistant can call.

Currently backed by mock data (see mock_data.py / data_access.py).
Swap data_access.py for real ERP/MES queries later — this file won't
need to change.

AUTH:
- Local mode (stdio, for Claude Desktop's old `command` config): no auth,
  not needed since it never leaves your machine.
- Remote mode (MCP_TRANSPORT=http): protected by WorkOS AuthKit OAuth.
  Every user must log in with an invited email before they can use any tool.

Required environment variables for remote/http mode:
    MCP_TRANSPORT=http
    AUTHKIT_DOMAIN=https://your-project-xxxx.authkit.app   (from WorkOS)
    BASE_URL=https://your-server.onrender.com               (your Render URL, no trailing slash)

Run:
    python3 server.py                       # stdio transport (local, for Claude Desktop)
    MCP_TRANSPORT=http python3 server.py    # http transport (remote, WorkOS-authenticated)
"""

import os
from fastmcp import FastMCP
import data_access as db

_transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()

if _transport == "http":
    from fastmcp.server.auth.providers.workos import AuthKitProvider

    authkit_domain = os.environ["AUTHKIT_DOMAIN"]   # e.g. https://xxxx.authkit.app
    base_url = os.environ["BASE_URL"]               # e.g. https://manufacturing-mcp.onrender.com

    auth_provider = AuthKitProvider(
        authkit_domain=authkit_domain,
        base_url=base_url,
    )
    mcp = FastMCP(name="Manufacturing MCP", auth=auth_provider)
else:
    # Local stdio mode — no auth needed, never leaves this machine.
    mcp = FastMCP(name="Manufacturing MCP")


# ---------------------------------------------------------------------
# MACHINE STATUS
# ---------------------------------------------------------------------
@mcp.tool()
def get_machine_status(machine_id: str = "", line_id: str = "") -> list[dict]:
    """
    Get status of shop-floor machines (running / idle / down), including
    uptime today and maintenance dates. Optionally filter by machine_id
    (e.g. 'M-101') or line_id (e.g. 'LINE-A'). Leave blank to get all machines.
    """
    return db.get_machine_status(machine_id or None, line_id or None)


# ---------------------------------------------------------------------
# WORK ORDERS
# ---------------------------------------------------------------------
@mcp.tool()
def get_work_orders(status: str = "", line_id: str = "") -> list[dict]:
    """
    List work orders. Optionally filter by status ('open', 'in_progress',
    'completed') and/or line_id (e.g. 'LINE-A'). Leave blank to get all.
    """
    return db.get_work_orders(status or None, line_id or None)


@mcp.tool()
def get_work_order_by_id(order_id: str) -> dict:
    """Get full details of a single work order by its ID (e.g. 'WO-5001')."""
    result = db.get_work_order_by_id(order_id)
    return result if result else {"error": f"No work order found with ID {order_id}"}


# ---------------------------------------------------------------------
# INVENTORY
# ---------------------------------------------------------------------
@mcp.tool()
def get_inventory(sku: str = "", below_reorder_only: bool = False) -> list[dict]:
    """
    Check inventory levels for raw materials and finished goods.
    Optionally filter by sku (e.g. 'RAW-STL-01'), or set
    below_reorder_only=True to see only items that need reordering.
    """
    return db.get_inventory(sku or None, below_reorder_only)


# ---------------------------------------------------------------------
# QUALITY LOGS
# ---------------------------------------------------------------------
@mcp.tool()
def get_quality_logs(product_id: str = "", min_defect_rate_pct: float = -1) -> list[dict]:
    """
    Get quality inspection logs, including defect rates and inspector notes.
    Optionally filter by product_id (partial match, e.g. 'Housing') or
    min_defect_rate_pct to find batches at or above a defect threshold.
    """
    return db.get_quality_logs(
        product_id or None,
        min_defect_rate_pct if min_defect_rate_pct >= 0 else None,
    )


# ---------------------------------------------------------------------
# DISPATCH / ON-TIME DELIVERY
# ---------------------------------------------------------------------
@mcp.tool()
def get_dispatches(status: str = "", order_id: str = "") -> list[dict]:
    """
    List dispatch records (shipments to customers). Optionally filter by
    status ('on_time', 'late', 'pending') or order_id. Leave blank for all.
    """
    return db.get_dispatches(status or None, order_id or None)


@mcp.tool()
def get_on_time_dispatch_rate() -> dict:
    """
    Get the overall on-time dispatch rate: percentage of completed
    dispatches that went out on schedule, with counts of on-time vs late.
    """
    return db.get_on_time_dispatch_rate()


# ---------------------------------------------------------------------
# VEHICLE TRACKING
# ---------------------------------------------------------------------
@mcp.tool()
def get_vehicle_status(vehicle_id: str = "") -> list[dict]:
    """
    Track delivery vehicles: current location, destination, ETA, and status
    (in_transit / delivered). Optionally filter by vehicle_id (e.g. 'VH-03').
    Leave blank to get all vehicles.
    """
    return db.get_vehicle_status(vehicle_id or None)


@mcp.tool()
def get_vehicle_by_dispatch(dispatch_id: str) -> dict:
    """Find which vehicle is carrying a given dispatch (e.g. 'DSP-7003')."""
    result = db.get_vehicle_by_dispatch(dispatch_id)
    return result if result else {"error": f"No vehicle found for dispatch {dispatch_id}"}


if __name__ == "__main__":
    if _transport == "http":
        port = int(os.environ.get("PORT", 8000))
        # Your public domain(s) must be listed here, or fastmcp's built-in
        # DNS-rebinding protection will reject requests with "421 Misdirected
        # Request" / "Invalid Host header", even with valid OAuth.
        # BASE_URL already carries this, so we derive it automatically.
        from urllib.parse import urlparse
        _base_host = urlparse(os.environ["BASE_URL"]).netloc
        mcp.run(
            transport="http",
            host="0.0.0.0",
            port=port,
            allowed_hosts=[_base_host, "127.0.0.1", "localhost"],
            allowed_origins=[f"https://{_base_host}", "http://127.0.0.1*", "http://localhost*"],
        )
    else:
        mcp.run(transport="stdio")

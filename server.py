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


def _not_connected(topic: str) -> dict:
    """
    Standard response for tools whose data source isn't wired up yet.
    Used instead of returning old placeholder/mock data, so it's always
    clear to whoever's testing which tools are backed by real data right
    now and which aren't.
    """
    return {
        "error": (
            f"{topic} information is not in the current data sheet yet. "
            "Only production order data (get_orders, get_order_by_id, "
            "get_order_summary) is connected to real data right now."
        )
    }


# ---------------------------------------------------------------------
# MACHINE STATUS
# ---------------------------------------------------------------------
@mcp.tool()
def get_machine_status(machine_id: str = "", line_id: str = "") -> list[dict] | dict:
    """
    Get status of shop-floor machines (running / idle / down), including
    uptime today and maintenance dates. Optionally filter by machine_id
    (e.g. 'M-101') or line_id (e.g. 'LINE-A'). Leave blank to get all machines.
    NOTE: not yet connected to real data — currently returns a not-available message.
    """
    return _not_connected("Machine status")


# ---------------------------------------------------------------------
# WORK ORDERS
# ---------------------------------------------------------------------
@mcp.tool()
def get_work_orders(status: str = "", line_id: str = "") -> list[dict] | dict:
    """
    List work orders (old schema: line_id, open/in_progress/completed).
    NOTE: not yet connected to real data. For real order tracking, use
    get_orders / get_order_by_id / get_order_summary instead.
    """
    return _not_connected("Work order (old schema)")


@mcp.tool()
def get_work_order_by_id(order_id: str) -> dict:
    """
    Get a single work order by ID (old schema, e.g. 'WO-5001').
    NOTE: not yet connected to real data. For real orders, use get_order_by_id instead.
    """
    return _not_connected("Work order (old schema)")


# ---------------------------------------------------------------------
# INVENTORY
# ---------------------------------------------------------------------
@mcp.tool()
def get_inventory(sku: str = "", below_reorder_only: bool = False) -> list[dict] | dict:
    """
    Check inventory levels for raw materials and finished goods.
    NOTE: not yet connected to real data — currently returns a not-available message.
    """
    return _not_connected("Inventory")


# ---------------------------------------------------------------------
# QUALITY LOGS
# ---------------------------------------------------------------------
@mcp.tool()
def get_quality_logs(product_id: str = "", min_defect_rate_pct: float = -1) -> list[dict] | dict:
    """
    Get quality inspection logs, including defect rates and inspector notes.
    NOTE: not yet connected to real data — currently returns a not-available message.
    (QC_Remarks does exist per-order in get_orders/get_order_by_id, but there's
    no separate structured quality log sheet yet.)
    """
    return _not_connected("Quality log")


# ---------------------------------------------------------------------
# DISPATCH / ON-TIME DELIVERY
# ---------------------------------------------------------------------
@mcp.tool()
def get_dispatches(status: str = "", order_id: str = "") -> list[dict] | dict:
    """
    List dispatch records (old schema: on_time/late/pending shipments).
    NOTE: not yet connected to real data. get_orders/get_order_by_id do
    include Dispatch_Date and Qty_Dispatched per order, which may cover
    what you need already.
    """
    return _not_connected("Dispatch record (old schema)")


@mcp.tool()
def get_on_time_dispatch_rate() -> dict:
    """
    Get the overall on-time dispatch rate.
    NOTE: not yet connected to real data — currently returns a not-available message.
    """
    return _not_connected("On-time dispatch rate")


# ---------------------------------------------------------------------
# VEHICLE TRACKING
# ---------------------------------------------------------------------
@mcp.tool()
def get_vehicle_status(vehicle_id: str = "") -> list[dict] | dict:
    """
    Track delivery vehicles: current location, destination, ETA, and status.
    NOTE: not yet connected to real data — currently returns a not-available message.
    """
    return _not_connected("Vehicle tracking")


@mcp.tool()
def get_vehicle_by_dispatch(dispatch_id: str) -> dict:
    """
    Find which vehicle is carrying a given dispatch.
    NOTE: not yet connected to real data — currently returns a not-available message.
    """
    return _not_connected("Vehicle tracking")


# ---------------------------------------------------------------------
# REAL PRODUCTION ORDERS (from production_data.xlsx, sheet "Master_Data")
# ---------------------------------------------------------------------
@mcp.tool()
def get_orders(order_id: str = "", client: str = "", status: str = "", priority: int = -1, month: str = "") -> list[dict]:
    """
    List real production orders from the master tracking sheet. Optionally
    filter by order_id (e.g. 'ORD-0001'), client (partial match), status
    ('AWAITING MATERIAL', 'IN-PRODUCTION', 'READY - PENDING DISPATCH'),
    priority (0-4), or month (e.g. 'June-2026'). Leave blank/omit to get all.
    """
    return db.get_orders(
        order_id or None,
        client or None,
        status or None,
        priority if priority >= 0 else None,
        month or None,
    )


@mcp.tool()
def get_order_by_id(order_id: str) -> dict:
    """Get full details of a single real production order by its ID (e.g. 'ORD-0001')."""
    result = db.get_order_by_id(order_id)
    return result if result else {"error": f"No order found with ID {order_id}"}


@mcp.tool()
def get_order_summary() -> dict:
    """
    Get an overview of all real production orders: counts by status
    (awaiting material / in-production / ready for dispatch), total
    quantity ordered vs dispatched, and average pending/turnaround days.
    """
    return db.get_order_summary()


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

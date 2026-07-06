"""
Manufacturing MCP Server

Exposes work orders, machine status, inventory, quality logs,
on-time dispatch, and vehicle tracking as tools an AI assistant can call.

Currently backed by mock data (see mock_data.py / data_access.py).
Swap data_access.py for real ERP/MES queries later — this file won't
need to change.

Run:
    uv run server.py                # stdio transport (for Claude Desktop)
    uv run mcp dev server.py        # test with MCP Inspector
"""

import os
from mcp.server.fastmcp import FastMCP
import data_access as db

mcp = FastMCP("Manufacturing MCP")


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


# ---------------------------------------------------------------------
# API KEY AUTH (for remote/HTTP mode only — not used for local stdio)
# ---------------------------------------------------------------------
# Set MCP_API_KEY as an environment variable on your host (never hardcode
# it here). Every request must send: Authorization: Bearer <key>
def build_authenticated_app():
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse

    api_key = os.environ.get("MCP_API_KEY")
    if not api_key:
        raise RuntimeError(
            "MCP_API_KEY environment variable is not set. "
            "Set it before running in HTTP mode."
        )

    class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            auth_header = request.headers.get("authorization", "")
            expected = f"Bearer {api_key}"
            if auth_header != expected:
                return JSONResponse(
                    {"error": "Unauthorized"}, status_code=401
                )
            return await call_next(request)

    inner_app = mcp.streamable_http_app()
    inner_app.add_middleware(ApiKeyAuthMiddleware)
    return inner_app


# This module-level `app` is what uvicorn will serve in HTTP mode.
# (Only built when run via uvicorn, e.g. `uvicorn server:app`.)
app = None
if os.environ.get("MCP_TRANSPORT", "").lower() == "http":
    app = build_authenticated_app()


if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()
    if transport == "http":
        import uvicorn
        port = int(os.environ.get("PORT", 8000))
        uvicorn.run(build_authenticated_app(), host="0.0.0.0", port=port)
    else:
        # Local mode for Claude Desktop (unauthenticated, stdio transport)
        mcp.run(transport="stdio")

"""
Data access layer.

Every function here currently reads from mock_data.py.

WHEN YOU CONNECT THE REAL ERP LATER:
Replace the body of each function with a real SQL query / API call,
but keep the function name, arguments, and return shape (list of dicts /
dict) the same. server.py never needs to change.

Example of what a real version will look like (SQL Server):

    def get_machine_status(machine_id: str | None = None):
        with get_connection() as conn:
            cur = conn.cursor()
            if machine_id:
                cur.execute("SELECT * FROM machines WHERE machine_id = ?", machine_id)
            else:
                cur.execute("SELECT * FROM machines")
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
"""

from mock_data import MACHINES, WORK_ORDERS, INVENTORY, QUALITY_LOGS, DISPATCHES, VEHICLES


# ---------------------------------------------------------------------
# MACHINE STATUS
# ---------------------------------------------------------------------
def get_machine_status(machine_id: str | None = None, line_id: str | None = None):
    results = MACHINES
    if machine_id:
        results = [m for m in results if m["machine_id"].lower() == machine_id.lower()]
    if line_id:
        results = [m for m in results if m["line_id"].lower() == line_id.lower()]
    return results


# ---------------------------------------------------------------------
# WORK ORDERS
# ---------------------------------------------------------------------
def get_work_orders(status: str | None = None, line_id: str | None = None):
    results = WORK_ORDERS
    if status:
        results = [w for w in results if w["status"].lower() == status.lower()]
    if line_id:
        results = [w for w in results if w["line_id"].lower() == line_id.lower()]
    return results


def get_work_order_by_id(order_id: str):
    for w in WORK_ORDERS:
        if w["order_id"].lower() == order_id.lower():
            return w
    return None


# ---------------------------------------------------------------------
# INVENTORY
# ---------------------------------------------------------------------
def get_inventory(sku: str | None = None, below_reorder_only: bool = False):
    results = INVENTORY
    if sku:
        results = [i for i in results if i["sku"].lower() == sku.lower()]
    if below_reorder_only:
        results = [i for i in results if i["quantity"] < i["reorder_level"]]
    return results


# ---------------------------------------------------------------------
# QUALITY LOGS
# ---------------------------------------------------------------------
def get_quality_logs(product_id: str | None = None, min_defect_rate_pct: float | None = None):
    results = QUALITY_LOGS
    if product_id:
        results = [q for q in results if product_id.lower() in q["product_id"].lower()]
    if min_defect_rate_pct is not None:
        results = [q for q in results if q["defect_rate_pct"] >= min_defect_rate_pct]
    return results


# ---------------------------------------------------------------------
# DISPATCH / ON-TIME DELIVERY
# ---------------------------------------------------------------------
def get_dispatches(status: str | None = None, order_id: str | None = None):
    results = DISPATCHES
    if status:
        results = [d for d in results if d["status"].lower() == status.lower()]
    if order_id:
        results = [d for d in results if d["order_id"].lower() == order_id.lower()]
    return results


def get_on_time_dispatch_rate():
    completed = [d for d in DISPATCHES if d["status"] in ("on_time", "late")]
    if not completed:
        return {"on_time_pct": None, "total_completed": 0}
    on_time = [d for d in completed if d["status"] == "on_time"]
    return {
        "on_time_pct": round(len(on_time) / len(completed) * 100, 1),
        "total_completed": len(completed),
        "on_time_count": len(on_time),
        "late_count": len(completed) - len(on_time),
    }


# ---------------------------------------------------------------------
# VEHICLE TRACKING
# ---------------------------------------------------------------------
def get_vehicle_status(vehicle_id: str | None = None):
    results = VEHICLES
    if vehicle_id:
        results = [v for v in results if v["vehicle_id"].lower() == vehicle_id.lower()]
    return results


def get_vehicle_by_dispatch(dispatch_id: str):
    for v in VEHICLES:
        if v["dispatch_id"].lower() == dispatch_id.lower():
            return v
    return None
"""
Data access layer.

Every function here currently reads from mock_data.py.

WHEN YOU CONNECT THE REAL ERP LATER:
Replace the body of each function with a real SQL query / API call,
but keep the function name, arguments, and return shape (list of dicts /
dict) the same. server.py never needs to change.

Example of what a real version will look like (SQL Server):

    def get_machine_status(machine_id: str | None = None):
        with get_connection() as conn:
            cur = conn.cursor()
            if machine_id:
                cur.execute("SELECT * FROM machines WHERE machine_id = ?", machine_id)
            else:
                cur.execute("SELECT * FROM machines")
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
"""

from mock_data import MACHINES, WORK_ORDERS, INVENTORY, QUALITY_LOGS, DISPATCHES, VEHICLES

import os
import csv
import io
import datetime
import urllib.request

# ---------------------------------------------------------------------
# REAL PRODUCTION ORDER DATA — auto-synced from a published Google Sheet
# ---------------------------------------------------------------------
# Set PRODUCTION_SHEET_CSV_URL to your sheet's published CSV link
# (Google Sheets -> File -> Share -> Publish to web -> pick the Master_Data
# sheet -> CSV -> Publish -> copy the URL). Every tool call fetches the
# latest version, so editing the Google Sheet updates Claude's answers
# immediately, with no redeploy needed.
#
# If PRODUCTION_SHEET_CSV_URL is not set (e.g. local/offline testing),
# falls back to the bundled production_data.xlsx file in this folder.
_CSV_URL = os.environ.get("PRODUCTION_SHEET_CSV_URL", "").strip()
_LOCAL_XLSX_FALLBACK = os.path.join(os.path.dirname(__file__), "production_data.xlsx")

# Columns that should be parsed as numbers rather than left as text.
_NUMERIC_COLUMNS = {
    "Priority", "ERP_Sales_Order", "Job_No", "Qty_Ordered", "Qty_Ready",
    "Qty_Dispatched", "Balance", "Amount", "Score", "Pending_Days",
    "Turnaround_Days",
}


def _coerce_value(header: str, raw: str):
    if raw is None:
        return None
    value = raw.strip()
    if value == "":
        return None
    if header in _NUMERIC_COLUMNS:
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            return value  # leave as text if it doesn't actually parse cleanly
    # Google/Excel CSV exports often render whole dates as "YYYY-MM-DD 00:00:00" —
    # trim the redundant midnight timestamp for cleaner output.
    if value.endswith(" 00:00:00") and len(value) == 19:
        value = value[:10]
    return value


def _load_from_csv_url(url: str):
    with urllib.request.urlopen(url, timeout=15) as resp:
        raw = resp.read().decode("utf-8-sig")
    reader = csv.reader(io.StringIO(raw))
    rows = list(reader)
    if not rows:
        return []
    headers = rows[0]
    orders = []
    for row in rows[1:]:
        if all(cell.strip() == "" for cell in row):
            continue
        record = {h: _coerce_value(h, v) for h, v in zip(headers, row)}
        orders.append(record)
    return orders


def _load_from_local_xlsx():
    from openpyxl import load_workbook
    wb = load_workbook(_LOCAL_XLSX_FALLBACK, data_only=True)
    ws = wb["Master_Data"]
    headers = [c.value for c in ws[1]]
    orders = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if all(c is None for c in row):
            continue
        record = {}
        for header, value in zip(headers, row):
            if isinstance(value, (datetime.datetime, datetime.date)):
                value = value.date().isoformat() if isinstance(value, datetime.datetime) else value.isoformat()
            elif isinstance(value, str) and value.strip() == "":
                value = None
            record[header] = value
        orders.append(record)
    return orders


def _load_production_orders():
    """
    Loads fresh every call (cheap for ~200 rows) so it always reflects the
    latest data. Prefers the live published Google Sheet if configured;
    falls back to the bundled Excel file otherwise (useful for local
    testing without an internet connection or a published sheet yet).
    """
    if _CSV_URL:
        return _load_from_csv_url(_CSV_URL)
    return _load_from_local_xlsx()


def get_orders(
    order_id: str | None = None,
    client: str | None = None,
    status: str | None = None,
    priority: int | None = None,
    month: str | None = None,
):
    results = _load_production_orders()
    if order_id:
        results = [o for o in results if str(o.get("Order_ID", "")).lower() == order_id.lower()]
    if client:
        results = [o for o in results if o.get("Client") and client.lower() in o["Client"].lower()]
    if status:
        results = [o for o in results if o.get("Row_Status") and o["Row_Status"].lower() == status.lower()]
    if priority is not None:
        results = [o for o in results if o.get("Priority") == priority]
    if month:
        results = [o for o in results if o.get("Month") and month.lower() in o["Month"].lower()]
    return results


def get_order_by_id(order_id: str):
    for o in _load_production_orders():
        if str(o.get("Order_ID", "")).lower() == order_id.lower():
            return o
    return None


def get_order_summary():
    orders = _load_production_orders()
    total = len(orders)
    by_status: dict[str, int] = {}
    for o in orders:
        s = o.get("Row_Status") or "Unknown"
        by_status[s] = by_status.get(s, 0) + 1

    def _avg(field):
        vals = [
            o[field] for o in orders
            if isinstance(o.get(field), (int, float)) and 0 <= o[field] <= 3650
        ]
        return round(sum(vals) / len(vals), 1) if vals else None

    total_qty_ordered = sum(o["Qty_Ordered"] for o in orders if isinstance(o.get("Qty_Ordered"), (int, float)))
    total_qty_dispatched = sum(o["Qty_Dispatched"] for o in orders if isinstance(o.get("Qty_Dispatched"), (int, float)))

    return {
        "total_orders": total,
        "orders_by_status": by_status,
        "total_qty_ordered": total_qty_ordered,
        "total_qty_dispatched": total_qty_dispatched,
        "avg_pending_days": _avg("Pending_Days"),
        "avg_turnaround_days": _avg("Turnaround_Days"),
    }


# ---------------------------------------------------------------------
# MACHINE STATUS
# ---------------------------------------------------------------------
def get_machine_status(machine_id: str | None = None, line_id: str | None = None):
    results = MACHINES
    if machine_id:
        results = [m for m in results if m["machine_id"].lower() == machine_id.lower()]
    if line_id:
        results = [m for m in results if m["line_id"].lower() == line_id.lower()]
    return results


# ---------------------------------------------------------------------
# WORK ORDERS
# ---------------------------------------------------------------------
def get_work_orders(status: str | None = None, line_id: str | None = None):
    results = WORK_ORDERS
    if status:
        results = [w for w in results if w["status"].lower() == status.lower()]
    if line_id:
        results = [w for w in results if w["line_id"].lower() == line_id.lower()]
    return results


def get_work_order_by_id(order_id: str):
    for w in WORK_ORDERS:
        if w["order_id"].lower() == order_id.lower():
            return w
    return None


# ---------------------------------------------------------------------
# INVENTORY
# ---------------------------------------------------------------------
def get_inventory(sku: str | None = None, below_reorder_only: bool = False):
    results = INVENTORY
    if sku:
        results = [i for i in results if i["sku"].lower() == sku.lower()]
    if below_reorder_only:
        results = [i for i in results if i["quantity"] < i["reorder_level"]]
    return results


# ---------------------------------------------------------------------
# QUALITY LOGS
# ---------------------------------------------------------------------
def get_quality_logs(product_id: str | None = None, min_defect_rate_pct: float | None = None):
    results = QUALITY_LOGS
    if product_id:
        results = [q for q in results if product_id.lower() in q["product_id"].lower()]
    if min_defect_rate_pct is not None:
        results = [q for q in results if q["defect_rate_pct"] >= min_defect_rate_pct]
    return results


# ---------------------------------------------------------------------
# DISPATCH / ON-TIME DELIVERY
# ---------------------------------------------------------------------
def get_dispatches(status: str | None = None, order_id: str | None = None):
    results = DISPATCHES
    if status:
        results = [d for d in results if d["status"].lower() == status.lower()]
    if order_id:
        results = [d for d in results if d["order_id"].lower() == order_id.lower()]
    return results


def get_on_time_dispatch_rate():
    completed = [d for d in DISPATCHES if d["status"] in ("on_time", "late")]
    if not completed:
        return {"on_time_pct": None, "total_completed": 0}
    on_time = [d for d in completed if d["status"] == "on_time"]
    return {
        "on_time_pct": round(len(on_time) / len(completed) * 100, 1),
        "total_completed": len(completed),
        "on_time_count": len(on_time),
        "late_count": len(completed) - len(on_time),
    }


# ---------------------------------------------------------------------
# VEHICLE TRACKING
# ---------------------------------------------------------------------
def get_vehicle_status(vehicle_id: str | None = None):
    results = VEHICLES
    if vehicle_id:
        results = [v for v in results if v["vehicle_id"].lower() == vehicle_id.lower()]
    return results


def get_vehicle_by_dispatch(dispatch_id: str):
    for v in VEHICLES:
        if v["dispatch_id"].lower() == dispatch_id.lower():
            return v
    return None

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

"""
Data access layer — Frappe / ERPNext edition.

Every tool in server.py calls a function in this file. Each function talks to
your Frappe/ERPNext site over its REST API and returns plain Python (a list of
dicts, or a single dict) shaped the way server.py already expects. Because the
function names, arguments, and return shapes are unchanged, server.py does not
need to change (except un-stubbing the 8 tools — see the notes I gave you).

------------------------------------------------------------------------------
REQUIRED ENVIRONMENT VARIABLES  (set these in Render -> your service -> Environment)
------------------------------------------------------------------------------
    FRAPPE_URL          e.g. https://erp.yourcompany.com   (NO trailing slash)
    FRAPPE_API_KEY      the API key of a READ-ONLY Frappe user
    FRAPPE_API_SECRET   that user's API secret

------------------------------------------------------------------------------
IMPORTANT — DocType and field names
------------------------------------------------------------------------------
The DocType names ("Work Order", "Bin", "Delivery Note", ...) and the field
lists below are the STANDARD ERPNext ones. If your site is customised, the
field names may differ. To see the exact fields on any DocType, fetch one full
record, e.g.:

    curl -H "Authorization: token KEY:SECRET" \
         "https://erp.yourcompany.com/api/resource/Work Order/WO-2026-00001"

Then adjust the `fields=[...]` and filter names below to match. Keep each
function's name, arguments, and return shape the same.
"""

import os
import json
import urllib.parse
import urllib.request
import urllib.error


# ---------------------------------------------------------------------
# CONNECTION / LOW-LEVEL HELPERS
# ---------------------------------------------------------------------
FRAPPE_URL = os.environ.get("FRAPPE_URL", "https://airflow-staging.frappe.cloud/app/home").rstrip("/")
FRAPPE_API_KEY = os.environ.get("FRAPPE_API_KEY", "467c5e731c14c33")
FRAPPE_API_SECRET = os.environ.get("FRAPPE_API_SECRET", "467c5e731c14c33:0d013db13b522cc2")

# Keep page size modest — very large page sizes can mis-paginate in Frappe.
_PAGE_SIZE = 200


def _auth_header() -> str:
    if not (FRAPPE_API_KEY and FRAPPE_API_SECRET):
        raise RuntimeError(
            "FRAPPE_API_KEY / FRAPPE_API_SECRET are not set. Add them as "
            "environment variables (see the top of this file)."
        )
    return f"token {FRAPPE_API_KEY}:{FRAPPE_API_SECRET}"


def _request(path: str):
    if not FRAPPE_URL:
        raise RuntimeError("FRAPPE_URL is not set.")
    req = urllib.request.Request(
        f"{FRAPPE_URL}{path}",
        headers={"Authorization": _auth_header(), "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _frappe_list(doctype: str, fields=None, filters=None, order_by=None):
    """
    Fetch ALL records of a DocType, auto-paginating. Returns a list of dicts.
    `filters` is a list like [["status", "=", "Completed"], ["qty", ">", 0]].
    """
    all_rows = []
    start = 0
    params = {"limit_page_length": _PAGE_SIZE}
    if fields:
        params["fields"] = json.dumps(fields)
    if filters:
        params["filters"] = json.dumps(filters)
    if order_by:
        params["order_by"] = order_by
    dt = urllib.parse.quote(doctype)
    while True:
        params["limit_start"] = start
        qs = urllib.parse.urlencode(params)
        data = _request(f"/api/resource/{dt}?{qs}").get("data", [])
        all_rows.extend(data)
        if len(data) < _PAGE_SIZE:
            break
        start += _PAGE_SIZE
    return all_rows


def _frappe_get(doctype: str, name: str):
    """Fetch a single document (all fields) as a dict, or None if not found."""
    try:
        dt = urllib.parse.quote(doctype)
        nm = urllib.parse.quote(name)
        return _request(f"/api/resource/{dt}/{nm}").get("data")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


# ---------------------------------------------------------------------
# MACHINE STATUS  ->  ERPNext "Workstation"
# ---------------------------------------------------------------------
def get_machine_status(machine_id: str | None = None, line_id: str | None = None):
    filters = []
    if machine_id:
        filters.append(["name", "=", machine_id])
    workstations = _frappe_list(
        "Workstation",
        fields=["name", "workstation_type", "status", "hour_rate"],
        filters=filters or None,
    )
    # NOTE: vanilla ERPNext has no live running/idle/down state or uptime for a
    # machine — that is MES/PLC/IoT data. "status" here is only the Workstation
    # config status (may not exist on older sites). To show real-time state,
    # call your MES here and merge it into each dict. `line_id` has no standard
    # equivalent; add a custom field on Workstation and filter on it if needed.
    return workstations


# ---------------------------------------------------------------------
# WORK ORDERS  ->  ERPNext "Work Order"
# ---------------------------------------------------------------------
def get_work_orders(status: str | None = None, line_id: str | None = None):
    filters = []
    if status:
        filters.append(["status", "=", status])
    if line_id:
        # ERPNext Work Orders have no built-in "production line". If you added a
        # custom field for it, rename "line_id" below to match; otherwise remove.
        filters.append(["line_id", "=", line_id])
    return _frappe_list(
        "Work Order",
        fields=["name", "production_item", "item_name", "qty", "produced_qty",
                "status", "planned_start_date", "expected_delivery_date",
                "sales_order", "fg_warehouse"],
        filters=filters or None,
    )


def get_work_order_by_id(order_id: str):
    return _frappe_get("Work Order", order_id)


# ---------------------------------------------------------------------
# INVENTORY  ->  ERPNext "Bin" (stock levels) + "Item Reorder" (reorder levels)
# ---------------------------------------------------------------------
def get_inventory(sku: str | None = None, below_reorder_only: bool = False):
    filters = []
    if sku:
        filters.append(["item_code", "=", sku])
    bins = _frappe_list(
        "Bin",
        fields=["item_code", "warehouse", "actual_qty", "reserved_qty",
                "projected_qty", "stock_uom"],
        filters=filters or None,
    )
    if not below_reorder_only:
        return bins

    # Reorder levels live per item+warehouse on the "Item Reorder" child table.
    reorder = _frappe_list(
        "Item Reorder",
        fields=["parent", "warehouse", "warehouse_reorder_level"],
    )
    level = {(r["parent"], r["warehouse"]): r.get("warehouse_reorder_level")
             for r in reorder}
    out = []
    for b in bins:
        lvl = level.get((b["item_code"], b["warehouse"]))
        if lvl is not None and (b.get("actual_qty") or 0) < lvl:
            b["reorder_level"] = lvl
            out.append(b)
    return out


# ---------------------------------------------------------------------
# QUALITY LOGS  ->  ERPNext "Quality Inspection"
# ---------------------------------------------------------------------
def get_quality_logs(product_id: str | None = None, min_defect_rate_pct: float | None = None):
    filters = []
    if product_id:
        filters.append(["item_code", "like", f"%{product_id}%"])
    logs = _frappe_list(
        "Quality Inspection",
        fields=["name", "item_code", "item_name", "report_date", "status",
                "sample_size", "inspected_by", "remarks",
                "reference_type", "reference_name"],
        filters=filters or None,
    )
    # NOTE: vanilla ERPNext Quality Inspection is pass/fail (status), not a
    # defect-rate %. `min_defect_rate_pct` has no native equivalent, so it is
    # ignored unless you added a custom defect-rate field (then filter on it).
    return logs


# ---------------------------------------------------------------------
# DISPATCH  ->  ERPNext "Delivery Note"
# ---------------------------------------------------------------------
def get_dispatches(status: str | None = None, order_id: str | None = None):
    filters = [["docstatus", "=", 1]]   # submitted delivery notes only
    if status:
        filters.append(["status", "=", status])
    dns = _frappe_list(
        "Delivery Note",
        fields=["name", "customer", "posting_date", "status",
                "transporter", "vehicle_no", "lr_no"],
        filters=filters,
    )
    if order_id:
        # DN -> Sales Order link lives on the child table "Delivery Note Item".
        links = _frappe_list(
            "Delivery Note Item",
            fields=["parent", "against_sales_order"],
            filters=[["against_sales_order", "=", order_id]],
        )
        parents = {l["parent"] for l in links}
        dns = [d for d in dns if d["name"] in parents]
    return dns


def get_on_time_dispatch_rate():
    # Promised date = Sales Order.delivery_date; actual = Delivery Note.posting_date.
    # On-time if actual <= promised. (ERPNext doesn't store this as one field, so
    # we compute it. For large volumes, consider a server-side Frappe report.)
    dns = _frappe_list(
        "Delivery Note",
        fields=["name", "posting_date"],
        filters=[["docstatus", "=", 1]],
    )
    if not dns:
        return {"on_time_pct": None, "total_completed": 0}

    links = _frappe_list(
        "Delivery Note Item",
        fields=["parent", "against_sales_order"],
        filters=[["against_sales_order", "!=", ""]],
    )
    dn_to_so = {}
    so_names = set()
    for row in links:
        so = row.get("against_sales_order")
        if so:
            dn_to_so.setdefault(row["parent"], so)   # first SO per DN
            so_names.add(so)

    so_delivery = {}
    so_list = list(so_names)
    for i in range(0, len(so_list), 100):
        chunk = so_list[i:i + 100]
        for so in _frappe_list(
            "Sales Order",
            fields=["name", "delivery_date"],
            filters=[["name", "in", chunk]],
        ):
            so_delivery[so["name"]] = so.get("delivery_date")

    on_time = late = unknown = 0
    for dn in dns:
        promised = so_delivery.get(dn_to_so.get(dn["name"]))
        actual = dn.get("posting_date")
        if not promised or not actual:
            unknown += 1
        elif actual <= promised:
            on_time += 1
        else:
            late += 1

    completed = on_time + late
    return {
        "on_time_pct": round(on_time / completed * 100, 1) if completed else None,
        "total_completed": completed,
        "on_time_count": on_time,
        "late_count": late,
        "unknown_count": unknown,
    }


# ---------------------------------------------------------------------
# VEHICLE TRACKING  ->  ERPNext "Vehicle" (fleet master) + Delivery Note
# ---------------------------------------------------------------------
def get_vehicle_status(vehicle_id: str | None = None):
    filters = []
    if vehicle_id:
        filters.append(["name", "=", vehicle_id])
    vehicles = _frappe_list(
        "Vehicle",
        fields=["name", "license_plate", "make", "model",
                "last_odometer", "fuel_type"],
        filters=filters or None,
    )
    # NOTE: ERPNext's Vehicle DocType is a fleet MASTER record. Live location /
    # ETA is NOT in ERPNext — it comes from a GPS/telematics provider. If you
    # have one, call its API here and merge location/ETA into each dict.
    return vehicles


def get_vehicle_by_dispatch(dispatch_id: str):
    dn = _frappe_get("Delivery Note", dispatch_id)
    if not dn:
        return None
    return {
        "dispatch_id": dispatch_id,
        "vehicle_no": dn.get("vehicle_no"),
        "transporter": dn.get("transporter"),
        "lr_no": dn.get("lr_no"),
        "customer": dn.get("customer"),
        # Live location/ETA would come from your GPS provider keyed on vehicle_no.
    }


# =====================================================================
# REAL PRODUCTION / SALES ORDERS  ->  ERPNext "Sales Order"
# ---------------------------------------------------------------------
# The spreadsheet/CSV source is gone. This now reads live from your
# Frappe/ERPNext site's Sales Order doctype via the same _frappe_list /
# _frappe_get helpers used everywhere else in this file.
#
# Field names below (customer, transaction_date, delivery_date, total_qty,
# per_delivered, grand_total, status) are STANDARD ERPNext Sales Order
# fields. If your site customised Sales Order, fetch one record to check:
#   curl -H "Authorization: token KEY:SECRET" \
#        "$FRAPPE_URL/api/resource/Sales Order/SO-2026-00001"
#
# NOTE: "Priority" has no standard equivalent on Sales Order. If you added
# a custom field for it, add its fieldname to `_SO_FIELDS` and filter on
# it in get_orders(); until then the `priority` argument is accepted but
# ignored (matches everything, never errors).
# =====================================================================
import datetime
import calendar

_SO_FIELDS = [
    "name", "customer", "status", "transaction_date", "delivery_date",
    "grand_total", "total_qty", "per_delivered", "per_billed",
]


def _month_str(date_str):
    """'2026-07-15' -> 'July-2026' (matches the old Month column format)."""
    if not date_str:
        return None
    try:
        y, m, _d = str(date_str).split("-")
        return f"{calendar.month_name[int(m)]}-{y}"
    except (ValueError, IndexError):
        return None


def _map_sales_order(r: dict) -> dict:
    total_qty = r.get("total_qty") or 0
    per_delivered = r.get("per_delivered") or 0
    qty_dispatched = round(total_qty * per_delivered / 100, 2) if total_qty else 0

    pending_days = None
    delivery_date = r.get("delivery_date")
    if delivery_date and r.get("status") not in ("Completed", "Closed", "Cancelled"):
        try:
            dd = datetime.date.fromisoformat(str(delivery_date))
            pending_days = (dd - datetime.date.today()).days
        except ValueError:
            pass

    return {
        "Order_ID": r.get("name"),
        "Client": r.get("customer"),
        "Row_Status": r.get("status"),
        "Order_Date": r.get("transaction_date"),
        "Delivery_Date": delivery_date,
        "Month": _month_str(r.get("transaction_date")),
        "Amount": r.get("grand_total"),
        "Qty_Ordered": total_qty,
        "Qty_Dispatched": qty_dispatched,
        "Pending_Days": pending_days,
    }


def get_orders(order_id=None, client=None, status=None, priority=None, month=None):
    filters = []
    if order_id:
        filters.append(["name", "=", order_id])
    if client:
        filters.append(["customer", "like", f"%{client}%"])
    if status:
        filters.append(["status", "=", status])
    # month filtering happens after fetch, since Frappe filters can't do
    # "contains substring of formatted month name" directly.

    rows = _frappe_list("Sales Order", fields=_SO_FIELDS, filters=filters or None,
                         order_by="transaction_date desc")
    orders = [_map_sales_order(r) for r in rows]

    if month:
        orders = [o for o in orders if o.get("Month") and month.lower() in o["Month"].lower()]
    # priority: no native field yet — see note above.

    return orders


def get_order_by_id(order_id: str):
    r = _frappe_get("Sales Order", order_id)
    return _map_sales_order(r) if r else None


def get_order_summary():
    orders = get_orders()
    total = len(orders)
    by_status: dict[str, int] = {}
    for o in orders:
        s = o.get("Row_Status") or "Unknown"
        by_status[s] = by_status.get(s, 0) + 1

    def _avg(field):
        vals = [o[field] for o in orders
                if isinstance(o.get(field), (int, float)) and 0 <= o[field] <= 3650]
        return round(sum(vals) / len(vals), 1) if vals else None

    total_qty_ordered = sum(o["Qty_Ordered"] for o in orders if isinstance(o.get("Qty_Ordered"), (int, float)))
    total_qty_dispatched = sum(o["Qty_Dispatched"] for o in orders if isinstance(o.get("Qty_Dispatched"), (int, float)))

    return {
        "total_orders": total,
        "orders_by_status": by_status,
        "total_qty_ordered": total_qty_ordered,
        "total_qty_dispatched": total_qty_dispatched,
        "avg_pending_days": _avg("Pending_Days"),
        "avg_turnaround_days": None,  # no equivalent on Sales Order; add a custom field if you need it
    }

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
FRAPPE_URL = os.environ.get("FRAPPE_URL", "").rstrip("/")
FRAPPE_API_KEY = os.environ.get("FRAPPE_API_KEY", "")
FRAPPE_API_SECRET = os.environ.get("FRAPPE_API_SECRET", "")

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
# REAL PRODUCTION ORDERS
# ---------------------------------------------------------------------
# These 3 functions currently sync from your published Google Sheet (working).
# They are left UNCHANGED so nothing you already rely on breaks.
#
# If your production tracker actually lives inside Frappe (a custom DocType or
# Sales Orders), you can instead point these at Frappe using _frappe_list /
# _frappe_get above — but only do that if the sheet is going away.
# =====================================================================
import csv
import io
import datetime

_CSV_URL = os.environ.get("PRODUCTION_SHEET_CSV_URL", "").strip()
_LOCAL_XLSX_FALLBACK = os.path.join(os.path.dirname(__file__), "production_data.xlsx")

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
            return float(value) if "." in value else int(value)
        except ValueError:
            return value
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
        orders.append({h: _coerce_value(h, v) for h, v in zip(headers, row)})
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
    if _CSV_URL:
        return _load_from_csv_url(_CSV_URL)
    return _load_from_local_xlsx()


def get_orders(order_id=None, client=None, status=None, priority=None, month=None):
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
        "avg_turnaround_days": _avg("Turnaround_Days"),
    }

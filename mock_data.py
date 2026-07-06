"""
Mock/sample data standing in for the real ERP/MES database.

Once you're ready to connect the real ERP, you only need to edit
`data_access.py` — replace the functions there with real DB/API calls
that return data shaped the same way as what's here. Nothing in
server.py needs to change.
"""

from datetime import date, timedelta

TODAY = date.today()

# ---------------------------------------------------------------------
# MACHINES (shop floor equipment)
# ---------------------------------------------------------------------
MACHINES = [
    {
        "machine_id": "M-101",
        "name": "CNC Lathe 1",
        "line_id": "LINE-A",
        "status": "running",
        "uptime_hours_today": 6.5,
        "last_maintenance": str(TODAY - timedelta(days=12)),
        "next_maintenance_due": str(TODAY + timedelta(days=18)),
    },
    {
        "machine_id": "M-102",
        "name": "CNC Lathe 2",
        "line_id": "LINE-A",
        "status": "idle",
        "uptime_hours_today": 2.0,
        "last_maintenance": str(TODAY - timedelta(days=40)),
        "next_maintenance_due": str(TODAY - timedelta(days=10)),  # overdue
    },
    {
        "machine_id": "M-201",
        "name": "Injection Molder 1",
        "line_id": "LINE-B",
        "status": "down",
        "uptime_hours_today": 0.0,
        "last_maintenance": str(TODAY - timedelta(days=5)),
        "next_maintenance_due": str(TODAY + timedelta(days=25)),
        "down_reason": "Hydraulic pressure fault",
    },
    {
        "machine_id": "M-202",
        "name": "Injection Molder 2",
        "line_id": "LINE-B",
        "status": "running",
        "uptime_hours_today": 7.8,
        "last_maintenance": str(TODAY - timedelta(days=3)),
        "next_maintenance_due": str(TODAY + timedelta(days=27)),
    },
    {
        "machine_id": "M-301",
        "name": "Assembly Robot 1",
        "line_id": "LINE-C",
        "status": "running",
        "uptime_hours_today": 8.0,
        "last_maintenance": str(TODAY - timedelta(days=20)),
        "next_maintenance_due": str(TODAY + timedelta(days=10)),
    },
]

# ---------------------------------------------------------------------
# WORK ORDERS
# ---------------------------------------------------------------------
WORK_ORDERS = [
    {
        "order_id": "WO-5001",
        "product": "Steel Bracket A",
        "qty": 500,
        "line_id": "LINE-A",
        "status": "open",
        "priority": "high",
        "due_date": str(TODAY + timedelta(days=2)),
    },
    {
        "order_id": "WO-5002",
        "product": "Plastic Housing X",
        "qty": 1200,
        "line_id": "LINE-B",
        "status": "open",
        "priority": "medium",
        "due_date": str(TODAY + timedelta(days=5)),
    },
    {
        "order_id": "WO-5003",
        "product": "Assembled Unit Z",
        "qty": 300,
        "line_id": "LINE-C",
        "status": "in_progress",
        "priority": "high",
        "due_date": str(TODAY + timedelta(days=1)),
    },
    {
        "order_id": "WO-4998",
        "product": "Steel Bracket B",
        "qty": 800,
        "line_id": "LINE-A",
        "status": "completed",
        "priority": "low",
        "due_date": str(TODAY - timedelta(days=3)),
    },
    {
        "order_id": "WO-4990",
        "product": "Plastic Housing Y",
        "qty": 600,
        "line_id": "LINE-B",
        "status": "completed",
        "priority": "medium",
        "due_date": str(TODAY - timedelta(days=8)),
    },
]

# ---------------------------------------------------------------------
# INVENTORY
# ---------------------------------------------------------------------
INVENTORY = [
    {"sku": "RAW-STL-01", "name": "Steel Sheet 2mm", "quantity": 4200, "unit": "kg", "reorder_level": 1000, "warehouse": "WH-1"},
    {"sku": "RAW-PLS-01", "name": "ABS Plastic Pellets", "quantity": 800, "unit": "kg", "reorder_level": 1000, "warehouse": "WH-2"},
    {"sku": "COMP-SCR-01", "name": "M6 Screws", "quantity": 25000, "unit": "pcs", "reorder_level": 5000, "warehouse": "WH-1"},
    {"sku": "FG-BRK-A", "name": "Steel Bracket A (Finished)", "quantity": 150, "unit": "pcs", "reorder_level": 200, "warehouse": "WH-3"},
    {"sku": "FG-HSG-X", "name": "Plastic Housing X (Finished)", "quantity": 900, "unit": "pcs", "reorder_level": 300, "warehouse": "WH-3"},
]

# ---------------------------------------------------------------------
# QUALITY LOGS
# ---------------------------------------------------------------------
QUALITY_LOGS = [
    {
        "log_id": "QL-9001",
        "product_id": "Steel Bracket A",
        "batch_id": "B-2201",
        "inspected_qty": 500,
        "defect_qty": 8,
        "defect_rate_pct": 1.6,
        "inspector": "R. Sharma",
        "date": str(TODAY - timedelta(days=1)),
        "notes": "Minor surface scratches, within tolerance.",
    },
    {
        "log_id": "QL-9002",
        "product_id": "Plastic Housing X",
        "batch_id": "B-2202",
        "inspected_qty": 1200,
        "defect_qty": 65,
        "defect_rate_pct": 5.4,
        "inspector": "A. Verma",
        "date": str(TODAY - timedelta(days=2)),
        "notes": "Above threshold — flagged for mold inspection.",
    },
    {
        "log_id": "QL-9003",
        "product_id": "Assembled Unit Z",
        "batch_id": "B-2203",
        "inspected_qty": 300,
        "defect_qty": 3,
        "defect_rate_pct": 1.0,
        "inspector": "R. Sharma",
        "date": str(TODAY),
        "notes": "Good batch.",
    },
]

# ---------------------------------------------------------------------
# DISPATCH / ON-TIME DELIVERY
# ---------------------------------------------------------------------
DISPATCHES = [
    {
        "dispatch_id": "DSP-7001",
        "order_id": "WO-4998",
        "customer": "Acme Industries",
        "scheduled_date": str(TODAY - timedelta(days=3)),
        "actual_dispatch_date": str(TODAY - timedelta(days=3)),
        "status": "on_time",
    },
    {
        "dispatch_id": "DSP-7002",
        "order_id": "WO-4990",
        "customer": "Bright Motors",
        "scheduled_date": str(TODAY - timedelta(days=8)),
        "actual_dispatch_date": str(TODAY - timedelta(days=6)),
        "status": "late",
        "delay_days": 2,
    },
    {
        "dispatch_id": "DSP-7003",
        "order_id": "WO-5001",
        "customer": "Nova Engineering",
        "scheduled_date": str(TODAY + timedelta(days=2)),
        "actual_dispatch_date": None,
        "status": "pending",
    },
]

# ---------------------------------------------------------------------
# VEHICLE TRACKING
# ---------------------------------------------------------------------
VEHICLES = [
    {
        "vehicle_id": "VH-01",
        "driver": "S. Kumar",
        "dispatch_id": "DSP-7001",
        "current_location": "Delivered - Acme Industries warehouse",
        "destination": "Acme Industries, Pune",
        "status": "delivered",
        "eta": None,
    },
    {
        "vehicle_id": "VH-02",
        "driver": "M. Khan",
        "dispatch_id": "DSP-7002",
        "current_location": "Delivered - Bright Motors dock",
        "destination": "Bright Motors, Nashik",
        "status": "delivered",
        "eta": None,
    },
    {
        "vehicle_id": "VH-03",
        "driver": "P. Yadav",
        "dispatch_id": "DSP-7003",
        "current_location": "NH-48, 40km from factory",
        "destination": "Nova Engineering, Aurangabad",
        "status": "in_transit",
        "eta": str(TODAY + timedelta(days=2)),
    },
]

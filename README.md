# Manufacturing MCP Server

An MCP (Model Context Protocol) server that lets an AI assistant (like Claude)
answer questions about your factory: work orders, machine status, inventory,
quality logs, on-time dispatch, and vehicle tracking.

**Currently running on mock data** so you can test the whole thing before
touching your real ERP/MES system.

## Files

| File | Purpose |
|---|---|
| `server.py` | Defines the MCP tools. This is what the AI actually talks to. |
| `data_access.py` | Where each tool gets its data. **This is the only file you'll need to edit when you connect the real ERP.** |
| `mock_data.py` | Sample/fake data (machines, work orders, inventory, etc.) used until the ERP is connected. |
| `requirements.txt` | Python dependencies. |

## 1. Setup

```bash
# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

(Recommended alternative: use [uv](https://docs.astral.sh/uv/) instead of venv/pip —
`uv venv && uv add mcp`.)

## 2. Test the tools directly (no MCP client needed)

```bash
python3 -c "
import server
print(server.get_machine_status())
print(server.get_work_orders(status='open'))
print(server.get_on_time_dispatch_rate())
"
```

## 3. Test with MCP Inspector (visual, interactive)

```bash
pip install "mcp[cli]"
mcp dev server.py
```

This opens a browser UI where you can call each tool by hand and see the
exact input/output — the best way to sanity-check before wiring up an AI.

## 4. Connect it to Claude Desktop

Edit Claude Desktop's config file:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "manufacturing": {
      "command": "python3",
      "args": ["/absolute/path/to/manufacturing-mcp/server.py"]
    }
  }
}
```

Restart Claude Desktop. You should see a tools icon showing 9 available tools.
Try asking: *"What machines are currently down?"* or *"What's our on-time
dispatch rate?"*

## Available tools

- `get_machine_status(machine_id?, line_id?)` — machine status, uptime, maintenance dates
- `get_work_orders(status?, line_id?)` — list work orders
- `get_work_order_by_id(order_id)` — single work order detail
- `get_inventory(sku?, below_reorder_only?)` — inventory levels
- `get_quality_logs(product_id?, min_defect_rate_pct?)` — quality inspection records
- `get_dispatches(status?, order_id?)` — shipment/dispatch records
- `get_on_time_dispatch_rate()` — overall on-time delivery percentage
- `get_vehicle_status(vehicle_id?)` — vehicle location, ETA, status
- `get_vehicle_by_dispatch(dispatch_id)` — find the vehicle carrying a dispatch

(`?` = optional parameter; leave blank/omit to get all records.)

## 5. Connecting the real ERP later

When you're ready, open `data_access.py`. Each function currently filters
the mock lists in `mock_data.py`. Replace the body of each function with a
real SQL query or API call to your ERP/MES — **keep the function name,
parameters, and return shape (list of dicts, or a dict) the same** — and
`server.py` will keep working without any changes.

Example for SQL Server, using `pyodbc`:

```python
import pyodbc, os

def get_connection():
    return pyodbc.connect(
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={os.environ['DB_SERVER']};"
        f"DATABASE={os.environ['DB_NAME']};"
        f"UID={os.environ['DB_USER']};"
        f"PWD={os.environ['DB_PASSWORD']};"
    )

def get_machine_status(machine_id=None, line_id=None):
    with get_connection() as conn:
        cur = conn.cursor()
        query = "SELECT * FROM machines WHERE 1=1"
        params = []
        if machine_id:
            query += " AND machine_id = ?"
            params.append(machine_id)
        if line_id:
            query += " AND line_id = ?"
            params.append(line_id)
        cur.execute(query, params)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
```

Always use a **read-only** DB account and parameterized queries (never
string-concatenate values into SQL).

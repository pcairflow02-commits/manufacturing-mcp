"""
Data access layer — multi-sheet edition.

This server can expose ANY number of Google Sheets (or local CSV/XLSX files),
one per environment variable. Each variable holds that sheet's *published CSV*
link (in Google Sheets: File -> Share -> Publish to web -> CSV). Nothing here
is hardcoded to a particular sheet — add a new sheet later by adding a new env
var with a CSV link and it shows up automatically, no code change.

------------------------------------------------------------------------------
HOW SHEETS ARE DISCOVERED
------------------------------------------------------------------------------
By default, every environment variable whose value looks like a published-CSV
link (contains "output=csv") is treated as a sheet, and the variable NAME
becomes the sheet's name. So with these Render vars:

    FMS_SHEET     = https://docs.google.com/.../pub?...output=csv
    Master_Data   = https://docs.google.com/.../pub?...output=csv
    SO_PRODUCTION = https://docs.google.com/.../pub?...output=csv

...the server exposes three sheets: FMS_SHEET, Master_Data, SO_PRODUCTION.
Config vars (AUTHKIT_DOMAIN, BASE_URL, MCP_TRANSPORT, MCP_API_KEY) are ignored
automatically because they aren't CSV links.

To add more sheets in future: just add another env var whose value is a
published CSV link. Done.

To control the list explicitly instead of auto-discovering, set:
    SHEETS = FMS_SHEET,Master_Data,SO_PRODUCTION
Each named var must then hold that sheet's CSV link (or, for local dev, a path
to a .csv / .xlsx file).
"""

import os
import io
import csv
import time
import urllib.request
import urllib.error


_CSV_MARKER = "output=csv"
_CACHE_TTL = 30          # seconds; sheets are re-fetched at most this often
_cache: dict[str, tuple[float, list]] = {}   # source -> (timestamp, rows)


# ---------------------------------------------------------------------
# SHEET REGISTRY
# ---------------------------------------------------------------------
def _discover_sheets() -> dict[str, str]:
    """Return {sheet_name: source_url_or_path}."""
    explicit = os.environ.get("SHEETS", "").strip()
    if explicit:
        names = [n.strip() for n in explicit.split(",") if n.strip()]
        return {n: os.environ.get(n, "").strip()
                for n in names if os.environ.get(n, "").strip()}

    out: dict[str, str] = {}
    for name, val in os.environ.items():
        v = (val or "").strip()
        if not v:
            continue
        if _CSV_MARKER in v or v.lower().endswith((".csv", ".xlsx")):
            out[name] = v
    return out


def _resolve(sheet: str) -> str:
    sheets = _discover_sheets()
    if sheet not in sheets:
        raise KeyError(sheet)
    return sheets[sheet]


def list_sheet_names() -> list[str]:
    return sorted(_discover_sheets().keys())


# ---------------------------------------------------------------------
# LOADING (cached)
# ---------------------------------------------------------------------
def _load(source: str) -> list[dict]:
    now = time.time()
    hit = _cache.get(source)
    if hit and (now - hit[0]) < _CACHE_TTL:
        return hit[1]

    if source.startswith(("http://", "https://")):
        rows = _load_csv_url(source)
    elif source.lower().endswith(".xlsx"):
        rows = _load_xlsx(source)
    elif source.lower().endswith(".csv"):
        rows = _load_csv_file(source)
    else:
        raise RuntimeError(f"Unrecognized data source: {source[:60]}...")

    _cache[source] = (now, rows)
    return rows


def _parse_csv(raw: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(raw))
    return [
        {(k or "").strip(): ("" if v is None else str(v).strip()) for k, v in row.items()}
        for row in reader
    ]


def _load_csv_url(url: str) -> list[dict]:
    req = urllib.request.Request(url, headers={"User-Agent": "manufacturing-mcp/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8-sig", errors="replace")
    except urllib.error.HTTPError as e:
        raise RuntimeError(
            f"Could not fetch sheet CSV (HTTP {e.code}). Make sure the value is "
            "the published-to-web CSV link, not a normal edit/share link."
        ) from e
    return _parse_csv(raw)


def _load_csv_file(path: str) -> list[dict]:
    with open(path, encoding="utf-8-sig") as f:
        return _parse_csv(f.read())


def _load_xlsx(path: str) -> list[dict]:
    from openpyxl import load_workbook   # only needed for local .xlsx
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    it = ws.iter_rows(values_only=True)
    headers = [str(h).strip() if h is not None else "" for h in next(it)]
    out = []
    for r in it:
        if all(c is None for c in r):
            continue
        out.append({
            headers[i]: ("" if i >= len(r) or r[i] is None else str(r[i]).strip())
            for i in range(len(headers))
        })
    return out


# ---------------------------------------------------------------------
# GENERIC QUERY API  (called by server.py — works on ANY sheet)
# ---------------------------------------------------------------------
def _cell(row: dict, col: str):
    if col in row:
        return row[col]
    low = {k.lower(): v for k, v in row.items()}
    return low.get(str(col).lower())


def list_sheets() -> list[dict]:
    """Every connected sheet, with its columns and row count."""
    out = []
    for name in list_sheet_names():
        try:
            rows = _load(_resolve(name))
            out.append({
                "sheet": name,
                "row_count": len(rows),
                "columns": list(rows[0].keys()) if rows else [],
            })
        except Exception as e:   # noqa: BLE001 - report per-sheet, don't crash the list
            out.append({"sheet": name, "error": str(e)})
    return out


def describe_sheet(sheet: str) -> dict:
    """Columns, row count, and a few sample rows for one sheet."""
    rows = _load(_resolve(sheet))
    return {
        "sheet": sheet,
        "columns": list(rows[0].keys()) if rows else [],
        "row_count": len(rows),
        "sample_rows": rows[:3],
    }


def get_sheet_rows(sheet: str, filters: dict | None = None, limit: int | None = None) -> list[dict]:
    """
    Rows from `sheet`. `filters` is {column: value}; a row matches when each
    column's cell CONTAINS the given value (case-insensitive). `limit` caps
    how many rows return.
    """
    rows = _load(_resolve(sheet))
    if filters:
        def match(r):
            for col, val in filters.items():
                if val in (None, ""):
                    continue
                if str(val).lower() not in str(_cell(r, col) or "").lower():
                    return False
            return True
        rows = [r for r in rows if match(r)]
    if limit and limit > 0:
        rows = rows[:limit]
    return rows


def search_sheet(sheet: str, query: str, limit: int | None = None) -> list[dict]:
    """Rows from `sheet` where ANY cell contains `query` (case-insensitive)."""
    q = str(query).lower()
    rows = [r for r in _load(_resolve(sheet)) if any(q in str(v or "").lower() for v in r.values())]
    if limit and limit > 0:
        rows = rows[:limit]
    return rows


# ---------------------------------------------------------------------
# Quick self-test:  python3 data_access.py
# ---------------------------------------------------------------------
if __name__ == "__main__":
    names = list_sheet_names()
    print(f"Discovered {len(names)} sheet(s): {names}")
    for s in list_sheets():
        print(" -", s)

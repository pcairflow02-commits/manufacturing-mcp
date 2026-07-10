"""
Manufacturing MCP Server — multi-sheet edition.

Exposes any number of connected Google Sheets (or local CSV/XLSX files) as
tools an AI assistant can query. Sheets are discovered from environment
variables holding published-CSV links (see data_access.py). Add a new sheet
later just by adding another env var — no code change here.

AUTH:
- Local mode (stdio, for Claude Desktop's `command` config): no auth.
- Remote mode (MCP_TRANSPORT=http): protected by WorkOS AuthKit OAuth.

Required environment variables for remote/http mode:
    MCP_TRANSPORT=http
    AUTHKIT_DOMAIN=https://your-project-xxxx.authkit.app   (from WorkOS)
    BASE_URL=https://your-server.onrender.com               (your Render URL, no trailing slash)

Plus one env var per sheet, each holding a published CSV link, e.g.:
    Master_Data   = https://docs.google.com/.../pub?...output=csv
    FMS_SHEET     = https://docs.google.com/.../pub?...output=csv
    SO_PRODUCTION = https://docs.google.com/.../pub?...output=csv

Run:
    python3 server.py                       # stdio transport (local)
    MCP_TRANSPORT=http python3 server.py    # http transport (remote, authenticated)
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


def _no_sheet(sheet: str) -> dict:
    return {
        "error": (
            f"No sheet named '{sheet}'. Call list_sheets to see the available "
            "sheet names."
        )
    }


# ---------------------------------------------------------------------
# GENERIC SHEET TOOLS  (work across every connected sheet)
# ---------------------------------------------------------------------
@mcp.tool()
def list_sheets() -> list[dict]:
    """
    List every connected data sheet, with its column names and row count.
    Call this FIRST to discover what data is available before querying.
    """
    return db.list_sheets()


@mcp.tool()
def describe_sheet(sheet: str) -> dict:
    """
    Show one sheet's columns, total row count, and a few sample rows — so you
    know what you can filter or search on. `sheet` is a name from list_sheets.
    """
    try:
        return db.describe_sheet(sheet)
    except KeyError:
        return _no_sheet(sheet)


@mcp.tool()
def get_sheet_rows(
    sheet: str,
    filter_column: str = "",
    filter_value: str = "",
    limit: int = 100,
) -> list[dict] | dict:
    """
    Return rows from a sheet. Optionally keep only rows where `filter_column`
    contains `filter_value` (case-insensitive substring match). `limit` caps
    the number of rows returned (default 100; pass 0 for all rows).
    `sheet` and `filter_column` names come from list_sheets / describe_sheet.
    """
    try:
        filters = {filter_column: filter_value} if (filter_column and filter_value) else None
        return db.get_sheet_rows(sheet, filters=filters, limit=limit or None)
    except KeyError:
        return _no_sheet(sheet)


@mcp.tool()
def search_sheet(sheet: str, query: str, limit: int = 100) -> list[dict] | dict:
    """
    Return rows from a sheet where ANY cell contains `query` (case-insensitive).
    Useful when you don't know which column a value lives in. `limit` caps the
    number of rows returned (default 100; pass 0 for all).
    """
    try:
        return db.search_sheet(sheet, query, limit=limit or None)
    except KeyError:
        return _no_sheet(sheet)


if __name__ == "__main__":
    if _transport == "http":
        port = int(os.environ.get("PORT", 8000))
        # Your public domain(s) must be listed here, or fastmcp's built-in
        # DNS-rebinding protection will reject requests with "421 Misdirected
        # Request" / "Invalid Host header", even with valid OAuth.
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

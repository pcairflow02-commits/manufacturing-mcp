# Manufacturing MCP Server

An MCP (Model Context Protocol) server that lets an AI assistant (like Claude)
answer questions about your data in Google Sheets — production orders, dispatch,
PPC, or any other tabs you keep. It reads your sheets **live** and lets the
assistant search across them and pick the relevant one per question.

## Files

| File | Purpose |
|---|---|
| `server.py` | Defines the MCP tools the AI talks to. Doesn't change when you add sheets. |
| `data_access.py` | Reads your Google Sheets via the Google Sheets API. |
| `SHEETS_SETUP.md` | Full guide to the API key, sharing, and adding sheet IDs. |
| `DEPLOYMENT.md` | Deploying to Render as an always-on HTTPS service. |
| `requirements.txt` | Python dependencies. |

## How it reads your data

The server uses the **Google Sheets API**. You give it two things (as
environment variables):

- `GOOGLE_API_KEY` — a Google API key with the Sheets API enabled
- `SPREADSHEET_IDS` — one or more spreadsheet IDs, comma-separated

From those, it automatically discovers **every tab** in **every file** and reads
all columns and rows. Adding more sheets is just adding more IDs to
`SPREADSHEET_IDS` — no code change. See **SHEETS_SETUP.md** for the full walkthrough.

## Available tools

The assistant gets four generic tools that work across every connected sheet:

- `list_sheets()` — every tab across every file, with its columns and row count
- `describe_sheet(sheet)` — one tab's columns, row count, and a few sample rows
- `get_sheet_rows(sheet, filter_column?, filter_value?, limit?)` — rows, optionally filtered
- `search_sheet(sheet, query, limit?)` — rows where any cell matches `query`

Because the tools are generic, the assistant reads whatever columns your sheets
actually have — so tabs you add later work with no changes.

## Quick start

1. **Set up Google access** (one time): create an API key, enable the Sheets
   API, and share each spreadsheet as *Anyone with the link → Viewer*. Full
   steps in **SHEETS_SETUP.md**.
2. **Install dependencies:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate      # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. **Test locally** (prints every tab it can see, with columns and row counts):

   Windows (Command Prompt):
   ```cmd
   set GOOGLE_API_KEY=your-key
   set SPREADSHEET_IDS=your-id
   python data_access.py
   ```
   macOS / Linux:
   ```bash
   GOOGLE_API_KEY="your-key" SPREADSHEET_IDS="your-id" python3 data_access.py
   ```
4. **Deploy** to Render so Claude web/desktop/mobile can reach it — see
   **DEPLOYMENT.md**.

## Connecting to Claude Desktop (local mode)

For local use, edit Claude Desktop's config file:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "manufacturing": {
      "command": "python3",
      "args": ["/absolute/path/to/manufacturing-mcp/server.py"],
      "env": {
        "GOOGLE_API_KEY": "your-key",
        "SPREADSHEET_IDS": "your-id"
      }
    }
  }
}
```

Restart Claude Desktop, then try: *"list the sheets you can see"* or
*"search all sheets for ORD-0001."*

For an always-on hosted server (so mobile and web work too), use the Render
setup in **DEPLOYMENT.md** instead.

## Notes

- Reading public sheets via an API key does **not** require Google Cloud
  billing; the free Sheets API quota is far more than this server needs, and
  results are cached ~30s.
- Only the Sheets API is used — no ERP/database is involved.

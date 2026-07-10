# Connecting Google Sheets to the Manufacturing MCP Server

This server reads your data live from Google Sheets using the **Google Sheets
API**. Given an API key and one or more spreadsheet IDs, it automatically reads
**every tab** of **every file** you list — all columns, all rows. Claude then
picks the relevant sheet per question via four tools: `list_sheets`,
`describe_sheet`, `get_sheet_rows`, and `search_sheet`.

There is **no per-tab setup** and **no code change** when you add sheets — it's
all driven by two environment variables in Render.

---

## The two environment variables

Set these in **Render → your service → Environment**:

| Variable | Value |
|---|---|
| `GOOGLE_API_KEY` | Your Google API key with the Google Sheets API enabled |
| `SPREADSHEET_IDS` | One or more spreadsheet IDs, comma-separated (see below) |

Keep the existing server vars too: `MCP_TRANSPORT=http`, `AUTHKIT_DOMAIN`,
`BASE_URL`. (`MCP_API_KEY` is unused — the server authenticates via WorkOS
AuthKit — so it can be left or removed.)

---

## First-time setup

### 1. Create the API key (free, no billing required)
1. Go to https://console.cloud.google.com and select or create a project.
2. **APIs & Services → Library**, search **Google Sheets API**, open it, click **Enable**.
3. **APIs & Services → Credentials → + Create credentials → API key** (pick
   "API key" from the dropdown — *not* the "User data / Application data" wizard).
4. Copy the key. Optionally restrict it: click the key → API restrictions →
   restrict to **Google Sheets API**. Leave Application restrictions on **None**.
5. Put the key in Render as `GOOGLE_API_KEY`.

### 2. Share each spreadsheet
For **every** file the server should read:
- Open the file → **Share** → General access → **Anyone with the link → Viewer**.

If a file isn't shared this way, the API returns a permission error for that file
(the other files still work).

### 3. Get each spreadsheet's ID
The ID is the part of the **normal edit URL** between `/d/` and `/edit`:

```
https://docs.google.com/spreadsheets/d/1AbCdEf12345XyZ/edit
                                       └────── ID ──────┘
```

> NOT the published `/d/e/2PACX-....../pub` token — that will not work with the API.

---

## Adding sheets (now or later)

`SPREADSHEET_IDS` is a **comma-separated list**. To read more files, add their
IDs to the same variable:

```
1AbCd...first,1EfGh...second,1IjKl...third
```

Rules:
- **Commas between IDs, no spaces:** `id1,id2,id3` — not `id1, id2`.
- **Share every new file** (step 2 above) or it returns a permission error.
- To stop reading a file, just delete its ID from the list.

Save the variable → Render redeploys → the new tabs appear automatically.

You do **not** add a separate variable per sheet, and you do **not** edit any
code. One variable, comma-separated, grows as long as you need.

### Tab name collisions
If two different files each have a tab with the same name, the server keeps them
distinct by labeling the second as `FileTitle::TabName`, so nothing is
overwritten — every tab remains visible.

---

## Testing it

**From Claude** (in a chat with the `manufacturing` connector enabled):
- "list the sheets you can see" → should return every tab, each with its columns
  and row count
- "show me the columns in <TabName>"
- "search all sheets for <value>"

**Locally** (optional sanity check; run from the project folder):

Windows (Command Prompt):
```cmd
set GOOGLE_API_KEY=your-key
set SPREADSHEET_IDS=your-id
python data_access.py
```

Windows (PowerShell):
```powershell
$env:GOOGLE_API_KEY="your-key"; $env:SPREADSHEET_IDS="your-id"; python data_access.py
```

macOS / Linux:
```bash
GOOGLE_API_KEY="your-key" SPREADSHEET_IDS="your-id" python3 data_access.py
```

It prints every tab found with its columns and row count. An `error` next to a
file almost always means it isn't shared (step 2) or the Sheets API isn't
enabled (step 1) — the message says which.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| No sheets returned at all | `SPREADSHEET_IDS` misspelled (e.g. `SPREADSHEET_ID`) or empty | Confirm the name is exactly `SPREADSHEET_IDS` (plural) |
| One file errors, others fine | That file isn't shared | Set it to Anyone with the link → Viewer |
| All files error with permission/403 | Sheets API not enabled, or key restricted wrongly | Enable Sheets API; check key restrictions |
| "Couldn't reach the MCP server" | Render free instance asleep (cold start), or a required server var (`MCP_TRANSPORT`/`AUTHKIT_DOMAIN`/`BASE_URL`) missing | Retry once for cold start; check those three vars are set and the deploy is **Live** |
| A tab shows fewer columns than expected | Blank header cells or a truly empty column | Header cells become `col2`, `col3`… ; check the sheet's header row |

---

## How it works (reference)

- `data_access.py` calls the Sheets API: one metadata call per file to list its
  tabs, then one values call per tab to read its full used range. Results are
  cached ~30s to stay well within the free quota.
- `server.py` exposes the four generic tools and is unchanged by adding sheets.
- If `GOOGLE_API_KEY` / `SPREADSHEET_IDS` are ever unset, the code falls back to
  its older mode: any env var whose value is a published-CSV link is treated as
  one sheet (one tab each).

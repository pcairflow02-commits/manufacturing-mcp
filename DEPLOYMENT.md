# Deploying the Manufacturing MCP Server on Render (free tier)

This turns the server into an always-on HTTPS service that Claude web, Claude
Desktop, and Claude mobile can all connect to, protected by WorkOS AuthKit
login so only invited people can use it.

## What the code does

- `server.py` supports two modes via the `MCP_TRANSPORT` env var:
  - unset / `stdio` → local mode for Claude Desktop's `command` config. No auth (local only).
  - `http` → runs as an HTTP service on `PORT` (Render sets this), protected by
    WorkOS AuthKit OAuth. Every user logs in with an invited email.
- `data_access.py` reads your Google Sheets via the Google Sheets API (see
  **SHEETS_SETUP.md**).

---

## Step 1: Put the code on GitHub

```bash
cd manufacturing-mcp
git init
git add .
git commit -m "Manufacturing MCP server"
```

Then create a **Private** repo on GitHub and push:
```bash
git remote add origin https://github.com/<your-username>/manufacturing-mcp.git
git branch -M main
git push -u origin main
```

## Step 2: Get your Google Sheets access ready

Before deploying, make sure you have (full steps in **SHEETS_SETUP.md**):
- a `GOOGLE_API_KEY` (Sheets API enabled),
- your `SPREADSHEET_IDS` (comma-separated IDs from each file's `/d/<ID>/edit` URL),
- each spreadsheet shared as **Anyone with the link → Viewer**.

## Step 3: Create the Render service

1. Go to https://render.com → sign up (no card required for the free tier).
2. **New +** → **Web Service** → connect GitHub → select `manufacturing-mcp`.
3. Render detects the `Dockerfile`. Set:
   - **Name:** `manufacturing-mcp`
   - **Region:** closest to your staff
   - **Instance type:** **Free**
4. Before creating, scroll to **Environment Variables** and add:

   | Key | Value |
   |---|---|
   | `MCP_TRANSPORT` | `http` |
   | `AUTHKIT_DOMAIN` | your WorkOS AuthKit domain, e.g. `https://your-project-xxxx.authkit.app` |
   | `BASE_URL` | your Render URL, no trailing slash, e.g. `https://manufacturing-mcp.onrender.com` |
   | `GOOGLE_API_KEY` | your Google API key |
   | `SPREADSHEET_IDS` | your spreadsheet IDs, comma-separated, no spaces |

   > Note the exact name **`SPREADSHEET_IDS`** — plural, with an `S`. A singular
   > `SPREADSHEET_ID` is silently ignored and no sheets will load.

5. Click **Create Web Service**. First build takes a few minutes.

## Step 4: Get your URL

Render shows a URL like `https://manufacturing-mcp.onrender.com`. Your MCP
endpoint is that plus `/mcp`:
```
https://manufacturing-mcp.onrender.com/mcp
```
Make sure `BASE_URL` matches the Render URL (without `/mcp`, no trailing slash).

## Step 5: Connect it in each Claude client

### Claude.ai (web)
Settings → Connectors → Add custom connector:
- URL: `https://manufacturing-mcp.onrender.com/mcp`

You'll be sent through WorkOS login the first time.

### Claude Desktop
Edit `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "manufacturing": {
      "url": "https://manufacturing-mcp.onrender.com/mcp"
    }
  }
}
```
Fully quit and reopen Claude Desktop after saving.

### Claude mobile
No separate setup — connectors added on web or desktop sync to your account.

## Step 6: Test

In a connected Claude chat:
- *"list the sheets you can see"* → every tab across your files, with columns
- *"search all sheets for <value>"*

## Adding more sheets later

Add the new spreadsheet's ID to `SPREADSHEET_IDS` (comma-separated) and share
that file (Anyone with the link → Viewer). Save; Render redeploys and the new
tabs appear. No code change. See **SHEETS_SETUP.md**.

## Updating the server later

Any push to the `main` branch triggers an automatic rebuild and redeploy.

---

## Troubleshooting

- **"Couldn't reach the MCP server."** Free instances sleep after ~15 min idle;
  the first request takes 30–60s to wake. Retry once. If it persists, check
  Render → Logs that the deploy is **Live** and there's no startup traceback
  (usually a missing `MCP_TRANSPORT` / `AUTHKIT_DOMAIN` / `BASE_URL`).
- **No sheets returned.** Check `SPREADSHEET_IDS` is spelled correctly (plural)
  and populated.
- **One file errors, others fine.** That file isn't shared — set it to Anyone
  with the link → Viewer.
- **"421 Misdirected Request" / "Invalid Host header".** `BASE_URL` doesn't match
  the actual Render host; fix it to the exact URL.

## Local development

```bash
python3 server.py    # MCP_TRANSPORT unset → stdio, local only
```
Set `GOOGLE_API_KEY` and `SPREADSHEET_IDS` in your shell (or the Desktop config
`env` block) so the tools have data to read.

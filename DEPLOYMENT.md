# Deploying the Manufacturing MCP Server on Render (free tier)

This turns the local stdio server into an always-on HTTPS service that
Claude web, Claude Desktop, and Claude mobile can all connect to, protected
by a shared API key so only people you give the key to can use it.

## What changed in the code

- `server.py` now supports two modes, controlled by the `MCP_TRANSPORT` env var:
  - `MCP_TRANSPORT` unset or `stdio` → old behavior, local-only, for Claude Desktop's `command` config. No auth (not needed — it's local).
  - `MCP_TRANSPORT=http` → runs as an HTTP service on `PORT` (Render sets this automatically), and **requires** every request to include `Authorization: Bearer <MCP_API_KEY>`.
- `requirements.txt` and `Dockerfile` added — Render builds directly from the Dockerfile.

---

## Step 1: Put the code on GitHub

Render deploys by connecting to a Git repo (GitHub or GitLab).

```bash
cd manufacturing-mcp
git init
git add .
git commit -m "Manufacturing MCP server"
```

Then on GitHub:
1. Create a new repo (make it **Private**) — e.g. `manufacturing-mcp`.
2. Follow GitHub's "push an existing repo" instructions, e.g.:
```bash
git remote add origin https://github.com/<your-username>/manufacturing-mcp.git
git branch -M main
git push -u origin main
```

## Step 2: Generate your API key now (you'll need it in Step 3)

Run this locally and save the output somewhere safe (password manager):
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Step 3: Create the Render account and service

1. Go to https://render.com → sign up (no card required for the free tier).
2. Click **New +** → **Web Service**.
3. Connect your GitHub account, then select the `manufacturing-mcp` repo.
4. Render will detect the `Dockerfile` automatically. Configuration:
   - **Name:** `manufacturing-mcp` (or anything)
   - **Region:** pick the one closest to your staff
   - **Instance type:** **Free**
5. Before clicking create, scroll to **Environment Variables** and add:
   - `MCP_API_KEY` = the key you generated in Step 2
   - `MCP_TRANSPORT` = `http`
6. Click **Create Web Service**. Render will build the Docker image and deploy — first build takes a few minutes.

## Step 4: Get your URL

Once deployed, Render shows a URL at the top of the service page, like:
```
https://manufacturing-mcp.onrender.com
```
Your MCP endpoint is that plus `/mcp`:
```
https://manufacturing-mcp.onrender.com/mcp
```

## Step 5: Test it before touching Claude

```bash
# No key → should return 401
curl -i https://manufacturing-mcp.onrender.com/mcp

# Correct key → should return a JSON-RPC response, not 401
curl -i https://manufacturing-mcp.onrender.com/mcp \
  -H "Authorization: Bearer <your-MCP_API_KEY>" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}},"id":1}'
```

**Note on the free tier:** if the service has been idle for 15+ minutes,
the first request above may take 30–60 seconds while it wakes up. That's
expected — Render free services sleep when unused and it's what makes them
free. Just wait for it; it'll respond.

## Step 6: Connect it in each Claude client

### Claude Desktop
Edit `claude_desktop_config.json` (paths from before) — replace the old
`command`-based entry with:
```json
{
  "mcpServers": {
    "manufacturing": {
      "url": "https://manufacturing-mcp.onrender.com/mcp",
      "headers": {
        "Authorization": "Bearer <your-MCP_API_KEY>"
      }
    }
  }
}
```
Fully quit and reopen Claude Desktop after saving.

### Claude.ai (web)
Settings → Connectors → Add custom connector:
- URL: `https://manufacturing-mcp.onrender.com/mcp`
- Header: `Authorization: Bearer <your-MCP_API_KEY>`

### Claude mobile
No separate setup — connectors added on web or desktop sync automatically
to your account.

## Step 7: Share the key with staff

- Use a password manager with sharing (1Password, Bitwarden, etc.) — not
  Slack/email in plain text.
- Everyone uses the same URL + same key in their own client config.

## Updating the server later

Any time you push a new commit to the `main` branch on GitHub, Render
automatically rebuilds and redeploys — no manual redeploy step needed.

## Rotating/revoking the key

Render dashboard → your service → **Environment** tab → edit `MCP_API_KEY`
→ save. Render redeploys with the new key; the old one stops working
immediately for everyone (shared-key tradeoff — see earlier note on OAuth
if you need to revoke individual users later).

## Local development still works

```bash
python3 server.py    # MCP_TRANSPORT unset → stdio, unauthenticated, local only
```

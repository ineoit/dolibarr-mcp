# Develop — environment and running the server

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate        # .venv\Scripts\activate on Windows
pip install -r requirements.txt
pip install -e .                 # editable install; add '.[dev]' for pytest extras
```

## Configuration

Copy `.env.example` to `.env` (gitignored) and set at minimum:

- `DOLIBARR_URL` — e.g. `https://your-dolibarr.example.com/api/index.php`
- `DOLIBARR_API_KEY` — personal API token of a least-privilege Dolibarr user

Full list in `docs/configuration.md`. Security-relevant knobs: `MCP_HTTP_TOKEN` (bearer token for the
HTTP listener), `MCP_READ_ONLY`, `MCP_ENABLE_RAW_API`, `MCP_CORS_ORIGINS`, `MCP_BIND_ADDRESS`.

## Run

```bash
# STDIO transport (default; for Claude Desktop)
python -m dolibarr_mcp.dolibarr_mcp_server

# Streamable HTTP transport (for Open WebUI / remote clients)
MCP_TRANSPORT=http MCP_HTTP_PORT=8080 python -m dolibarr_mcp.dolibarr_mcp_server

# Connectivity check before wiring into an MCP host
python -m dolibarr_mcp.test_connection

# Docker Compose HTTP listener (publishes 127.0.0.1:18004 by default)
docker compose up -d
```

## Debugging API failures

HTTP 500 responses carry a `correlation_id`; grep the server logs (stderr, or
`docker logs <container> 2>&1 | grep <correlation_id>`) for the full stack trace. Never log or report
`DOLAPIKEY`.

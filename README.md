# Zendesk MCP Server

![ci](https://github.com/reminia/zendesk-mcp-server/actions/workflows/ci.yml/badge.svg)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

A Model Context Protocol server for Zendesk, focused on Help Center (Knowledge Base) management.

This server provides:

- Full CRUD for Help Center **Categories** (list, get, create, update)
- Article **search** with filters for locale, category, section, and labels
- **Read-only ticket tools** for referencing past tickets when authoring articles
- Full access to the Zendesk Help Center as a knowledge base resource

![demo](https://res.cloudinary.com/leecy-me/image/upload/v1736410626/open/zendesk_yunczu.gif)

## Setup

- build: `uv venv && uv pip install -e .` or `uv build` in short.
- setup zendesk credentials in `.env` file, refer to [.env.example](.env.example).
- configure in Claude desktop:

```json
{
  "mcpServers": {
      "zendesk": {
          "command": "uv",
          "args": [
              "--directory",
              "/path/to/zendesk-mcp-server",
              "run",
              "zendesk"
          ]
      }
  }
}
```

### Docker

You can containerize the server if you prefer an isolated runtime:

1. Copy `.env.example` to `.env` and fill in your Zendesk credentials. Keep this file outside version control.
2. Build the image:

   ```bash
   docker build -t zendesk-mcp-server .
   ```

3. Run the server, providing the environment file:

   ```bash
   docker run --rm --env-file /path/to/.env zendesk-mcp-server
   ```

   Add `-i` when wiring the container to MCP clients over STDIN/STDOUT (Claude Code uses this mode). For daemonized runs, add `-d --name zendesk-mcp`.

The image installs dependencies from `requirements.lock`, drops privileges to a non-root user, and expects configuration exclusively via environment variables.

#### Claude MCP Integration

To use the Dockerized server from Claude Code/Desktop, add an entry to Claude Code's `settings.json` similar to:

```json
{
  "mcpServers": {
    "zendesk": {
      "command": "/usr/local/bin/docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "--env-file",
        "/path/to/zendesk-mcp-server/.env",
        "zendesk-mcp-server"
      ]
    }
  }
}
```

Adjust the paths to match your environment. After saving the file, restart Claude for the new MCP server to be detected.

## Testing

The test suite runs integration tests against the live Zendesk API. All tests require valid credentials in `.env`.

### Install dev dependencies

```bash
uv sync --group dev
```

### Run all tests

```bash
uv run pytest tests/ -v
```

### Optional environment variables

Set these in `.env` to pin tests to known-good IDs. If omitted, tests fall back to the first item returned by the corresponding list call.

| Variable | Used by |
|---|---|
| `TEST_CATEGORY_ID` | `test_get_category_returns_expected_id` |
| `TEST_ARTICLE_ID` | `test_get_article_returns_expected_id` |
| `TEST_TICKET_ID` | `test_get_ticket_returns_expected_id`, `test_get_ticket_comments_returns_list` |

### Startup auth check

The server also verifies credentials on every startup by calling `GET /api/v2/users/me`. If the credentials are invalid it exits immediately with a clear error rather than failing silently on the first tool call.

## Resources

- zendesk://knowledge-base, get access to the whole help center articles.

## Tools

### Knowledge Base — Categories

| Tool | Description |
|---|---|
| `list_categories` | List all Help Center categories |
| `get_category` | Retrieve a category by ID |
| `create_category` | Create a new category |
| `update_category` | Update an existing category |

### Knowledge Base — Articles

| Tool | Description |
|---|---|
| `search_articles` | Search articles by keyword, category, section, or label |
| `get_article` | Retrieve the full content of an article by ID |

### Tickets (read-only)

| Tool | Description |
|---|---|
| `get_tickets` | Fetch tickets with pagination and sorting |
| `get_ticket` | Retrieve a ticket by ID |
| `get_ticket_comments` | Retrieve all comments for a ticket |
| `get_ticket_attachment` | Fetch a ticket attachment as base64-encoded data |

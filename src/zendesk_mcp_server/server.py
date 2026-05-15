import asyncio
import json
import logging
import os
from typing import Any, Dict

from cachetools.func import ttl_cache
from dotenv import load_dotenv
from mcp.server import InitializationOptions, NotificationOptions
from mcp.server import Server, types
from mcp.server.stdio import stdio_server
from pydantic import AnyUrl

from zendesk_mcp_server.zendesk_client import ZendeskClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("zendesk-mcp-server")
logger.info("zendesk mcp server started")

load_dotenv()
zendesk_client = ZendeskClient(
    subdomain=os.getenv("ZENDESK_SUBDOMAIN"),
    email=os.getenv("ZENDESK_EMAIL"),
    token=os.getenv("ZENDESK_API_KEY")
)

server = Server("Zendesk Server")


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available Zendesk tools"""
    return [
        types.Tool(
            name="get_ticket",
            description="Retrieve a Zendesk ticket by its ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "The ID of the ticket to retrieve"
                    }
                },
                "required": ["ticket_id"]
            }
        ),
        types.Tool(
            name="get_tickets",
            description="Fetch the latest tickets with pagination support",
            inputSchema={
                "type": "object",
                "properties": {
                    "page": {
                        "type": "integer",
                        "description": "Page number",
                        "default": 1
                    },
                    "per_page": {
                        "type": "integer",
                        "description": "Number of tickets per page (max 100)",
                        "default": 25
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "Field to sort by (created_at, updated_at, priority, status)",
                        "default": "created_at"
                    },
                    "sort_order": {
                        "type": "string",
                        "description": "Sort order (asc or desc)",
                        "default": "desc"
                    }
                },
                "required": []
            }
        ),
        types.Tool(
            name="get_ticket_comments",
            description="Retrieve all comments for a Zendesk ticket by its ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "integer",
                        "description": "The ID of the ticket to get comments for"
                    }
                },
                "required": ["ticket_id"]
            }
        ),
        types.Tool(
            name="search_articles",
            description="Search Help Center articles by keyword, category, section, or label. Returns titles, snippets, and URLs. At least one of query, category_id, section_id, or label_names must be provided.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search keywords"
                    },
                    "locale": {
                        "type": "string",
                        "description": "Locale to search in (default: en-us)",
                        "default": "en-us"
                    },
                    "category_id": {
                        "type": "integer",
                        "description": "Limit results to a specific category ID"
                    },
                    "section_id": {
                        "type": "integer",
                        "description": "Limit results to a specific section ID"
                    },
                    "label_names": {
                        "type": "string",
                        "description": "Comma-separated list of labels to filter by"
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "Sort field: created_at or updated_at"
                    },
                    "sort_order": {
                        "type": "string",
                        "description": "Sort direction: asc or desc"
                    },
                    "page": {
                        "type": "integer",
                        "description": "Page number (default: 1)",
                        "default": 1
                    },
                    "per_page": {
                        "type": "integer",
                        "description": "Results per page, max 100 (default: 25)",
                        "default": 25
                    }
                },
                "required": []
            }
        ),
        types.Tool(
            name="get_article",
            description="Retrieve the full content of a Help Center article by its ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "article_id": {
                        "type": "integer",
                        "description": "The ID of the article to retrieve"
                    },
                    "locale": {
                        "type": "string",
                        "description": "Locale of the article content (default: en-us)",
                        "default": "en-us"
                    }
                },
                "required": ["article_id"]
            }
        ),
        types.Tool(
            name="list_categories",
            description="List all Help Center categories",
            inputSchema={
                "type": "object",
                "properties": {
                    "locale": {
                        "type": "string",
                        "description": "Locale for category names and descriptions (default: en-us)",
                        "default": "en-us"
                    }
                },
                "required": []
            }
        ),
        types.Tool(
            name="get_category",
            description="Retrieve a single Help Center category by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "category_id": {
                        "type": "integer",
                        "description": "The ID of the category to retrieve"
                    },
                    "locale": {
                        "type": "string",
                        "description": "Locale for category content (default: en-us)",
                        "default": "en-us"
                    }
                },
                "required": ["category_id"]
            }
        ),
        types.Tool(
            name="create_category",
            description="Create a new Help Center category",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Category name"
                    },
                    "description": {
                        "type": "string",
                        "description": "Category description"
                    },
                    "locale": {
                        "type": "string",
                        "description": "Locale for the category (default: en-us)",
                        "default": "en-us"
                    },
                    "position": {
                        "type": "integer",
                        "description": "Display position (lower numbers appear first)"
                    }
                },
                "required": ["name"]
            }
        ),
        types.Tool(
            name="update_category",
            description="Update an existing Help Center category",
            inputSchema={
                "type": "object",
                "properties": {
                    "category_id": {
                        "type": "integer",
                        "description": "The ID of the category to update"
                    },
                    "name": {
                        "type": "string",
                        "description": "New category name"
                    },
                    "description": {
                        "type": "string",
                        "description": "New category description"
                    },
                    "position": {
                        "type": "integer",
                        "description": "New display position"
                    }
                },
                "required": ["category_id"]
            }
        ),
        types.Tool(
            name="get_ticket_attachment",
            description="Fetch a Zendesk ticket attachment by its content_url and return the file as base64-encoded data. Use the attachment URLs returned by get_ticket_comments.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content_url": {
                        "type": "string",
                        "description": "The content_url of the attachment from get_ticket_comments"
                    }
                },
                "required": ["content_url"]
            }
        ),
    ]


@server.call_tool()
async def handle_call_tool(
        name: str,
        arguments: dict[str, Any] | None
) -> list[types.TextContent]:
    """Handle Zendesk tool execution requests"""
    try:
        if name == "get_ticket":
            if not arguments:
                raise ValueError("Missing arguments")
            ticket = zendesk_client.get_ticket(arguments["ticket_id"])
            return [types.TextContent(
                type="text",
                text=json.dumps(ticket)
            )]

        elif name == "get_tickets":
            page = arguments.get("page", 1) if arguments else 1
            per_page = arguments.get("per_page", 25) if arguments else 25
            sort_by = arguments.get("sort_by", "created_at") if arguments else "created_at"
            sort_order = arguments.get("sort_order", "desc") if arguments else "desc"

            tickets = zendesk_client.get_tickets(
                page=page,
                per_page=per_page,
                sort_by=sort_by,
                sort_order=sort_order
            )
            return [types.TextContent(
                type="text",
                text=json.dumps(tickets, indent=2)
            )]

        elif name == "get_ticket_comments":
            if not arguments:
                raise ValueError("Missing arguments")
            comments = zendesk_client.get_ticket_comments(
                arguments["ticket_id"])
            return [types.TextContent(
                type="text",
                text=json.dumps(comments)
            )]

        elif name == "search_articles":
            results = zendesk_client.search_articles(
                query=arguments.get("query") if arguments else None,
                locale=arguments.get("locale", "en-us") if arguments else "en-us",
                category_id=arguments.get("category_id") if arguments else None,
                section_id=arguments.get("section_id") if arguments else None,
                label_names=arguments.get("label_names") if arguments else None,
                sort_by=arguments.get("sort_by") if arguments else None,
                sort_order=arguments.get("sort_order") if arguments else None,
                page=arguments.get("page", 1) if arguments else 1,
                per_page=arguments.get("per_page", 25) if arguments else 25,
            )
            return [types.TextContent(
                type="text",
                text=json.dumps(results, indent=2)
            )]

        elif name == "get_article":
            if not arguments:
                raise ValueError("Missing arguments")
            article = zendesk_client.get_article(
                article_id=arguments["article_id"],
                locale=arguments.get("locale", "en-us"),
            )
            return [types.TextContent(
                type="text",
                text=json.dumps(article, indent=2)
            )]

        elif name == "list_categories":
            locale = arguments.get("locale", "en-us") if arguments else "en-us"
            categories = zendesk_client.list_categories(locale=locale)
            return [types.TextContent(
                type="text",
                text=json.dumps(categories, indent=2)
            )]

        elif name == "get_category":
            if not arguments:
                raise ValueError("Missing arguments")
            locale = arguments.get("locale", "en-us")
            category = zendesk_client.get_category(
                category_id=arguments["category_id"],
                locale=locale
            )
            return [types.TextContent(
                type="text",
                text=json.dumps(category, indent=2)
            )]

        elif name == "create_category":
            if not arguments:
                raise ValueError("Missing arguments")
            category = zendesk_client.create_category(
                name=arguments["name"],
                description=arguments.get("description"),
                locale=arguments.get("locale", "en-us"),
                position=arguments.get("position"),
            )
            return [types.TextContent(
                type="text",
                text=json.dumps({"message": "Category created successfully", "category": category}, indent=2)
            )]

        elif name == "update_category":
            if not arguments:
                raise ValueError("Missing arguments")
            category = zendesk_client.update_category(
                category_id=arguments["category_id"],
                name=arguments.get("name"),
                description=arguments.get("description"),
                position=arguments.get("position"),
            )
            return [types.TextContent(
                type="text",
                text=json.dumps({"message": "Category updated successfully", "category": category}, indent=2)
            )]

        elif name == "get_ticket_attachment":
            if not arguments:
                raise ValueError("Missing arguments")
            result = zendesk_client.get_ticket_attachment(arguments["content_url"])
            content_type = result["content_type"]
            if content_type.startswith("image/"):
                return [types.ImageContent(
                    type="image",
                    data=result["data"],
                    mimeType=content_type,
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=json.dumps({"content_type": content_type, "data_base64": result["data"]})
                )]

        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        return [types.TextContent(
            type="text",
            text=f"Error: {str(e)}"
        )]


@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    logger.debug("Handling list_resources request")
    return [
        types.Resource(
            uri=AnyUrl("zendesk://knowledge-base"),
            name="Zendesk Knowledge Base",
            description="Access to Zendesk Help Center articles and sections",
            mimeType="application/json",
        )
    ]


@ttl_cache(ttl=3600)
def get_cached_kb():
    return zendesk_client.get_all_articles()


@server.read_resource()
async def handle_read_resource(uri: AnyUrl) -> str:
    logger.debug(f"Handling read_resource request for URI: {uri}")
    if uri.scheme != "zendesk":
        logger.error(f"Unsupported URI scheme: {uri.scheme}")
        raise ValueError(f"Unsupported URI scheme: {uri.scheme}")

    path = str(uri).replace("zendesk://", "")
    if path != "knowledge-base":
        logger.error(f"Unknown resource path: {path}")
        raise ValueError(f"Unknown resource path: {path}")

    try:
        kb_data = get_cached_kb()
        return json.dumps({
            "knowledge_base": kb_data,
            "metadata": {
                "sections": len(kb_data),
                "total_articles": sum(len(section['articles']) for section in kb_data.values()),
            }
        }, indent=2)
    except Exception as e:
        logger.error(f"Error fetching knowledge base: {e}")
        raise


async def main():
    # Run the server using stdin/stdout streams
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream=read_stream,
            write_stream=write_stream,
            initialization_options=InitializationOptions(
                server_name="Zendesk",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())

"""
Integration tests for ZendeskClient.

These tests run against the live Zendesk API and require valid credentials
in the environment (or a .env file). They verify that authentication is
working and that each client method returns an HTTP 200 with a well-formed
response.

Optional env vars for known-value assertions:
  TEST_CATEGORY_ID   — a category ID known to exist
  TEST_SECTION_ID    — a section ID known to exist
  TEST_ARTICLE_ID    — an article ID known to exist
  TEST_TICKET_ID     — a ticket ID known to exist

If these are not set, the tests fall back to using the first item returned
by the corresponding list call (or skip if nothing is available).
"""

import os
import pytest
from dotenv import load_dotenv

load_dotenv()

from zendesk_mcp_server.zendesk_client import ZendeskClient


@pytest.fixture(scope="session")
def client() -> ZendeskClient:
    subdomain = os.environ.get("ZENDESK_SUBDOMAIN")
    email = os.environ.get("ZENDESK_EMAIL")
    token = os.environ.get("ZENDESK_API_KEY")
    if not all([subdomain, email, token]):
        pytest.fail("ZENDESK_SUBDOMAIN, ZENDESK_EMAIL and ZENDESK_API_KEY must be set")
    return ZendeskClient(subdomain=subdomain, email=email, token=token)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def test_auth_returns_valid_user(client):
    user = client.verify_auth()
    assert user.get("id"), "Expected a user ID from /api/v2/users/me"
    assert user.get("email"), "Expected an email from /api/v2/users/me"


# ---------------------------------------------------------------------------
# Tickets (read-only)
# ---------------------------------------------------------------------------

def test_get_tickets_returns_list(client):
    result = client.get_tickets(per_page=1)
    assert "tickets" in result
    assert isinstance(result["tickets"], list)


def test_get_ticket_returns_expected_id(client):
    ticket_id = int(os.environ.get("TEST_TICKET_ID", 0))
    if not ticket_id:
        tickets = client.get_tickets(per_page=1)["tickets"]
        if not tickets:
            pytest.skip("No tickets available to test against")
        ticket_id = tickets[0]["id"]
    ticket = client.get_ticket(ticket_id)
    assert ticket["id"] == ticket_id


def test_get_ticket_comments_returns_list(client):
    ticket_id = int(os.environ.get("TEST_TICKET_ID", 0))
    if not ticket_id:
        tickets = client.get_tickets(per_page=1)["tickets"]
        if not tickets:
            pytest.skip("No tickets available to test against")
        ticket_id = tickets[0]["id"]
    comments = client.get_ticket_comments(ticket_id)
    assert isinstance(comments, list)


# ---------------------------------------------------------------------------
# Knowledge Base — Categories
# ---------------------------------------------------------------------------

def test_list_categories_returns_list(client):
    categories = client.list_categories()
    assert isinstance(categories, list)
    assert len(categories) > 0, "Expected at least one category"


def test_get_category_returns_expected_id(client):
    category_id = int(os.environ.get("TEST_CATEGORY_ID", 0))
    if not category_id:
        categories = client.list_categories()
        if not categories:
            pytest.skip("No categories available to test against")
        category_id = categories[0]["id"]
    category = client.get_category(category_id)
    assert category["id"] == category_id


# ---------------------------------------------------------------------------
# Knowledge Base — Articles
# ---------------------------------------------------------------------------

def test_search_articles_returns_results(client):
    result = client.search_articles(query="a")
    assert "results" in result
    assert isinstance(result["results"], list)


def test_get_article_returns_expected_id(client):
    article_id = int(os.environ.get("TEST_ARTICLE_ID", 0))
    if not article_id:
        result = client.search_articles(query="a", per_page=1)
        if not result["results"]:
            pytest.skip("No articles available to test against")
        article_id = result["results"][0]["id"]
    article = client.get_article(article_id)
    assert article["id"] == article_id
    assert "body" in article


def test_update_article_persists_title_and_body(client):
    """Regression test: title and body must be routed to the translations endpoint."""
    article_id = int(os.environ.get("TEST_ARTICLE_ID", 0))
    if not article_id:
        pytest.skip("TEST_ARTICLE_ID not set — required for write regression test")

    original = client.get_article(article_id)
    sentinel_title = original["title"] + " [update-test]"
    sentinel_body = (original.get("body") or "") + "<!-- update-test -->"

    try:
        updated = client.update_article(
            article_id=article_id,
            title=sentinel_title,
            body=sentinel_body,
        )
        assert updated["title"] == sentinel_title, (
            f"title not persisted — got {updated['title']!r}, expected {sentinel_title!r}"
        )
        assert "update-test" in (updated.get("body") or ""), (
            "body not persisted — update-test sentinel missing from returned body"
        )
    finally:
        # Restore original values regardless of assertion outcome.
        client.update_article(
            article_id=article_id,
            title=original["title"],
            body=original.get("body") or "",
        )

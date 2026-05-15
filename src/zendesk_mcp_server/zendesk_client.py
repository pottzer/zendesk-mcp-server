from typing import Dict, Any, List
import json
import urllib.request
import urllib.parse
import base64
import requests as _requests

from zenpy import Zenpy
from zenpy.lib.api_objects.help_centre_objects import Category, Section, Article


class ZendeskClient:
    def __init__(self, subdomain: str, email: str, token: str):
        """
        Initialize the Zendesk client using zenpy lib and direct API.
        """
        self.client = Zenpy(
            subdomain=subdomain,
            email=email,
            token=token
        )

        # For direct API calls
        self.subdomain = subdomain
        self.email = email
        self.token = token
        self.base_url = f"https://{subdomain}.zendesk.com/api/v2"
        # Create basic auth header
        credentials = f"{email}/token:{token}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode('ascii')
        self.auth_header = f"Basic {encoded_credentials}"

    def get_ticket(self, ticket_id: int) -> Dict[str, Any]:
        """
        Query a ticket by its ID
        """
        try:
            ticket = self.client.tickets(id=ticket_id)
            return {
                'id': ticket.id,
                'subject': ticket.subject,
                'description': ticket.description,
                'status': ticket.status,
                'priority': ticket.priority,
                'created_at': str(ticket.created_at),
                'updated_at': str(ticket.updated_at),
                'requester_id': ticket.requester_id,
                'assignee_id': ticket.assignee_id,
                'organization_id': ticket.organization_id
            }
        except Exception as e:
            raise Exception(f"Failed to get ticket {ticket_id}: {str(e)}")

    def get_ticket_comments(self, ticket_id: int) -> List[Dict[str, Any]]:
        """
        Get all comments for a specific ticket, including attachment metadata.
        """
        try:
            comments = self.client.tickets.comments(ticket=ticket_id)
            result = []
            for comment in comments:
                attachments = []
                for a in getattr(comment, 'attachments', []) or []:
                    attachments.append({
                        'id': a.id,
                        'file_name': a.file_name,
                        'content_url': a.content_url,
                        'content_type': a.content_type,
                        'size': a.size,
                    })
                result.append({
                    'id': comment.id,
                    'author_id': comment.author_id,
                    'body': comment.body,
                    'html_body': comment.html_body,
                    'public': comment.public,
                    'created_at': str(comment.created_at),
                    'attachments': attachments,
                })
            return result
        except Exception as e:
            raise Exception(f"Failed to get comments for ticket {ticket_id}: {str(e)}")

    # Allowed image MIME types. SVG is excluded — it can contain active XML/JS content.
    _ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}

    # Magic bytes (file signatures) for each allowed type.
    _MAGIC_BYTES: Dict[str, List[bytes]] = {
        'image/jpeg': [b'\xff\xd8\xff'],
        'image/png':  [b'\x89PNG\r\n\x1a\n'],
        'image/gif':  [b'GIF87a', b'GIF89a'],
        'image/webp': [b'RIFF'],  # RIFF....WEBP — checked further below
    }

    # 10 MB hard cap to guard against image bombs and token budget blowout.
    _MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024

    def get_ticket_attachment(self, content_url: str) -> Dict[str, Any]:
        """
        Fetch an image attachment and return base64-encoded data.

        Security measures applied:
        - Allowlist of safe image MIME types (no SVG or arbitrary binary).
        - Magic byte validation so the file header must match the declared type.
        - 10 MB size cap to prevent image bombs and excessive token usage.

        Zendesk attachment URLs redirect to zdusercontent.com (Zendesk's CDN).
        requests strips the Authorization header on cross-origin redirects,
        which is required — the CDN returns 403 if it receives an auth header.
        """
        try:
            response = _requests.get(
                content_url,
                headers={'Authorization': self.auth_header},
                timeout=30,
                stream=True,
            )
            response.raise_for_status()

            content_type = response.headers.get('Content-Type', '').split(';')[0].strip().lower()

            if content_type not in self._ALLOWED_IMAGE_TYPES:
                raise ValueError(
                    f"Attachment type '{content_type}' is not allowed. "
                    f"Supported types: {sorted(self._ALLOWED_IMAGE_TYPES)}"
                )

            # Read with size cap — stops download as soon as limit is exceeded.
            chunks = []
            total = 0
            for chunk in response.iter_content(chunk_size=65536):
                total += len(chunk)
                if total > self._MAX_ATTACHMENT_BYTES:
                    raise ValueError(
                        f"Attachment exceeds the {self._MAX_ATTACHMENT_BYTES // (1024*1024)} MB size limit."
                    )
                chunks.append(chunk)
            content = b''.join(chunks)

            # Validate magic bytes to catch MIME type spoofing.
            magic_signatures = self._MAGIC_BYTES.get(content_type, [])
            if magic_signatures and not any(content.startswith(sig) for sig in magic_signatures):
                raise ValueError(
                    f"File header does not match declared content type '{content_type}'. "
                    "The attachment may be spoofed."
                )
            # Extra check for WebP: bytes 8–12 must be b'WEBP'.
            if content_type == 'image/webp' and content[8:12] != b'WEBP':
                raise ValueError("File header does not match declared content type 'image/webp'.")

            return {
                'data': base64.b64encode(content).decode('ascii'),
                'content_type': content_type,
            }
        except (ValueError, _requests.HTTPError):
            raise
        except Exception as e:
            raise Exception(f"Failed to fetch attachment from {content_url}: {str(e)}")

    def get_tickets(self, page: int = 1, per_page: int = 25, sort_by: str = 'created_at', sort_order: str = 'desc') -> Dict[str, Any]:
        """
        Get the latest tickets with proper pagination support using direct API calls.

        Args:
            page: Page number (1-based)
            per_page: Number of tickets per page (max 100)
            sort_by: Field to sort by (created_at, updated_at, priority, status)
            sort_order: Sort order (asc or desc)

        Returns:
            Dict containing tickets and pagination info
        """
        try:
            # Cap at reasonable limit
            per_page = min(per_page, 100)

            # Build URL with parameters for offset pagination
            params = {
                'page': str(page),
                'per_page': str(per_page),
                'sort_by': sort_by,
                'sort_order': sort_order
            }
            query_string = urllib.parse.urlencode(params)
            data = self._api_get(f"/tickets.json?{query_string}")

            tickets_data = data.get('tickets', [])

            # Process tickets to return only essential fields
            ticket_list = []
            for ticket in tickets_data:
                ticket_list.append({
                    'id': ticket.get('id'),
                    'subject': ticket.get('subject'),
                    'status': ticket.get('status'),
                    'priority': ticket.get('priority'),
                    'description': ticket.get('description'),
                    'created_at': ticket.get('created_at'),
                    'updated_at': ticket.get('updated_at'),
                    'requester_id': ticket.get('requester_id'),
                    'assignee_id': ticket.get('assignee_id')
                })

            return {
                'tickets': ticket_list,
                'page': page,
                'per_page': per_page,
                'count': len(ticket_list),
                'sort_by': sort_by,
                'sort_order': sort_order,
                'has_more': data.get('next_page') is not None,
                'next_page': page + 1 if data.get('next_page') else None,
                'previous_page': page - 1 if data.get('previous_page') and page > 1 else None
            }
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else "No response body"
            raise Exception(f"Failed to get latest tickets: HTTP {e.code} - {e.reason}. {error_body}")
        except Exception as e:
            raise Exception(f"Failed to get latest tickets: {str(e)}")

    def list_categories(self, locale: str = 'en-us') -> List[Dict[str, Any]]:
        try:
            categories = self.client.help_center.categories(locale=locale)
            return [
                {
                    'id': c.id,
                    'name': c.name,
                    'description': c.description,
                    'locale': c.locale,
                    'position': c.position,
                    'html_url': c.html_url,
                    'created_at': str(c.created_at),
                    'updated_at': str(c.updated_at),
                }
                for c in categories
            ]
        except Exception as e:
            raise Exception(f"Failed to list categories: {str(e)}")

    def get_category(self, category_id: int, locale: str = 'en-us') -> Dict[str, Any]:
        try:
            c = self.client.help_center.categories(id=category_id, locale=locale)
            return {
                'id': c.id,
                'name': c.name,
                'description': c.description,
                'locale': c.locale,
                'position': c.position,
                'html_url': c.html_url,
                'created_at': str(c.created_at),
                'updated_at': str(c.updated_at),
            }
        except Exception as e:
            raise Exception(f"Failed to get category {category_id}: {str(e)}")

    def create_category(
        self,
        name: str,
        description: str | None = None,
        locale: str = 'en-us',
        position: int | None = None,
    ) -> Dict[str, Any]:
        try:
            category = Category(
                name=name,
                description=description,
                locale=locale,
                position=position,
            )
            created = self.client.help_center.categories.create(category)
            return {
                'id': created.id,
                'name': created.name,
                'description': created.description,
                'locale': created.locale,
                'position': created.position,
                'html_url': created.html_url,
                'created_at': str(created.created_at),
                'updated_at': str(created.updated_at),
            }
        except Exception as e:
            raise Exception(f"Failed to create category: {str(e)}")

    def update_category(
        self,
        category_id: int,
        name: str | None = None,
        description: str | None = None,
        position: int | None = None,
    ) -> Dict[str, Any]:
        try:
            category = self.client.help_center.categories(id=category_id)
            if name is not None:
                category.name = name
            if description is not None:
                category.description = description
            if position is not None:
                category.position = position
            updated = self.client.help_center.categories.update(category)
            return {
                'id': updated.id,
                'name': updated.name,
                'description': updated.description,
                'locale': updated.locale,
                'position': updated.position,
                'html_url': updated.html_url,
                'created_at': str(updated.created_at),
                'updated_at': str(updated.updated_at),
            }
        except Exception as e:
            raise Exception(f"Failed to update category {category_id}: {str(e)}")

    def search_articles(
        self,
        query: str | None = None,
        locale: str = 'en-us',
        category_id: int | None = None,
        section_id: int | None = None,
        label_names: str | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> Dict[str, Any]:
        # At least one of query, category, section, or label_names is required by the API
        if not any([query, category_id, section_id, label_names]):
            raise ValueError("At least one of query, category_id, section_id, or label_names must be provided")

        try:
            per_page = min(per_page, 100)
            params: Dict[str, Any] = {
                'locale': locale,
                'page': page,
                'per_page': per_page,
            }
            if query:
                params['query'] = query
            if category_id is not None:
                params['category'] = category_id
            if section_id is not None:
                params['section'] = section_id
            if label_names:
                params['label_names'] = label_names
            if sort_by:
                params['sort_by'] = sort_by
            if sort_order:
                params['sort_order'] = sort_order

            query_string = urllib.parse.urlencode(params)
            data = self._api_get(f"/help_center/articles/search?{query_string}")

            results = [
                {
                    'id': a.get('id'),
                    'title': a.get('title'),
                    'snippet': a.get('snippet'),
                    'locale': a.get('locale'),
                    'section_id': a.get('section_id'),
                    'html_url': a.get('html_url'),
                    'updated_at': a.get('updated_at'),
                }
                for a in data.get('results', [])
            ]

            return {
                'results': results,
                'count': data.get('count', len(results)),
                'page': page,
                'per_page': per_page,
                'page_count': data.get('page_count'),
                'next_page': data.get('next_page'),
                'previous_page': data.get('previous_page'),
            }
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else "No response body"
            raise Exception(f"Failed to search articles: HTTP {e.code} - {e.reason}. {error_body}")
        except Exception as e:
            raise Exception(f"Failed to search articles: {str(e)}")

    def _api_get(self, path: str) -> Any:
        """Make an authenticated GET request to the Zendesk API."""
        req = urllib.request.Request(f"{self.base_url}{path}")
        req.add_header('Authorization', self.auth_header)
        req.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())

    def get_all_articles(self) -> Dict[str, Any]:
        """
        Fetch help center articles as knowledge base.
        Returns a Dict of section -> [article].
        """
        try:
            sections = self.client.help_center.sections()
            kb = {}
            for section in sections:
                page = 1
                articles = []
                while True:
                    data = self._api_get(
                        f"/help_center/sections/{section.id}/articles?page={page}&per_page=100"
                    )
                    articles.extend(data.get('articles', []))
                    if data.get('next_page') is None:
                        break
                    page += 1

                kb[section.name] = {
                    'section_id': section.id,
                    'description': section.description,
                    'articles': [{
                        'id': a.get('id'),
                        'title': a.get('title'),
                        'body': a.get('body'),
                        'updated_at': a.get('updated_at'),
                        'url': a.get('html_url'),
                    } for a in articles]
                }

            return kb
        except Exception as e:
            raise Exception(f"Failed to fetch knowledge base: {str(e)}")


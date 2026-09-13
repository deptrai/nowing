"""Write-side operations for the Notion history connector (page CRUD)."""

import contextlib
import logging
from typing import Any

from notion_client.errors import APIResponseError
from notion_markdown import to_notion

logger = logging.getLogger(__name__)


class NotionPagesMixin:
    """Page create/update/delete operations."""

    async def _get_first_accessible_parent(self) -> str | None:
        """
        Get the first accessible page ID that can be used as a parent.

        Returns:
            Page ID string, or None if no accessible pages found
        """
        try:
            notion = await self._get_client()

            # Search for pages, get most recently edited first
            response = await self._api_call_with_retry(
                notion.search,
                filter={"property": "object", "value": "page"},
                sort={"direction": "descending", "timestamp": "last_edited_time"},
                page_size=1,  # We only need the first one
            )

            results = response.get("results", [])
            if results:
                return results[0]["id"]

            return None

        except Exception as e:  # per-item sync failure; continue batch
            logger.error(f"Error finding accessible parent page: {e}")
            return None

    def _markdown_to_blocks(self, markdown: str) -> list[dict[str, Any]]:
        """Convert markdown content to Notion blocks using notion-markdown."""
        return to_notion(markdown)

    async def create_page(
        self, title: str, content: str, parent_page_id: str | None = None
    ) -> dict[str, Any]:
        """
        Create a new Notion page.

        Args:
            title: Page title
            content: Page content (markdown format)
            parent_page_id: Optional parent page ID (creates as subpage if provided)

        Returns:
            Dictionary with page details:
            - page_id: Created page ID
            - url: Page URL
            - title: Page title
            - status: "success" or "error"
            - message: Success/error message

        Raises:
            APIResponseError: If Notion API returns an error
        """
        try:
            logger.info(
                f"Creating Notion page: title='{title}', parent_page_id={parent_page_id}"
            )

            # Get Notion client
            notion = await self._get_client()

            # Convert markdown content to Notion blocks
            children = self._markdown_to_blocks(content)

            # Prepare parent - find first available page if not provided
            if not parent_page_id:
                logger.info(
                    "No parent_page_id provided, searching for first accessible page..."
                )
                parent_page_id = await self._get_first_accessible_parent()
                if not parent_page_id:
                    logger.warning("No accessible parent pages found")
                    return {
                        "status": "error",
                        "message": "Could not find any accessible Notion pages to use as parent. "
                        "Please make sure your Notion integration has access to at least one page.",
                    }
                logger.info(f"Using parent_page_id: {parent_page_id}")

            parent = {"type": "page_id", "page_id": parent_page_id}

            # Create the page with standard title property
            properties = {
                "title": {"title": [{"type": "text", "text": {"content": title}}]}
            }

            response = await self._api_call_with_retry(
                notion.pages.create,
                parent=parent,
                properties=properties,
                children=children[:100],  # Notion API limit: 100 blocks per request
            )

            page_id = response["id"]
            page_url = response["url"]

            # If content has more than 100 blocks, append them
            if len(children) > 100:
                for i in range(100, len(children), 100):
                    batch = children[i : i + 100]
                    await self._api_call_with_retry(
                        notion.blocks.children.append, block_id=page_id, children=batch
                    )

            return {
                "status": "success",
                "page_id": page_id,
                "url": page_url,
                "title": title,
                "message": f"Created Notion page '{title}'",
            }

        except APIResponseError as e:
            logger.error(f"Notion API error creating page: {e}")
            error_msg = self._api_error_message(e)
            return {
                "status": "error",
                "message": f"Failed to create Notion page: {error_msg}",
            }
        except Exception as e:  # per-item sync failure; continue batch
            logger.error(f"Unexpected error creating Notion page: {e}")
            return {
                "status": "error",
                "message": f"Failed to create Notion page: {e!s}",
            }

    async def update_page(
        self, page_id: str, content: str | None = None
    ) -> dict[str, Any]:
        """
        Update an existing Notion page by appending new content.

        Note: Content is appended to the page, not replaced.

        Args:
            page_id: Page ID to update
            content: New markdown content to append to the page (optional)

        Returns:
            Dictionary with update result

        Raises:
            APIResponseError: If Notion API returns an error
        """
        try:
            notion = await self._get_client()

            appended_block_ids = []
            if content:
                # Convert new content to blocks
                try:
                    children = self._markdown_to_blocks(content)
                    if not children:
                        logger.warning(
                            "No blocks generated from content, skipping append"
                        )
                        return {
                            "status": "error",
                            "message": "Content conversion failed: no valid blocks generated",
                        }
                except Exception as e:  # per-item sync failure; continue batch
                    logger.error(f"Failed to convert markdown to blocks: {e}")
                    return {
                        "status": "error",
                        "message": f"Failed to parse content: {e!s}",
                    }

                # Append new content blocks
                try:
                    for i in range(0, len(children), 100):
                        batch = children[i : i + 100]
                        response = await self._api_call_with_retry(
                            notion.blocks.children.append,
                            block_id=page_id,
                            children=batch,
                        )
                        batch_block_ids = [
                            block["id"] for block in response.get("results", [])
                        ]
                        appended_block_ids.extend(batch_block_ids)
                    logger.info(
                        f"Successfully appended {len(children)} new blocks to page {page_id}"
                    )
                    logger.debug(
                        f"Appended block IDs: {appended_block_ids[:5]}..."
                        if len(appended_block_ids) > 5
                        else f"Appended block IDs: {appended_block_ids}"
                    )
                except Exception as e:  # per-item sync failure; continue batch
                    logger.error(f"Failed to append content blocks: {e}")
                    return {
                        "status": "error",
                        "message": f"Failed to append content: {e!s}",
                    }

            # Get updated page info
            response = await self._api_call_with_retry(
                notion.pages.retrieve, page_id=page_id
            )
            page_url = response["url"]
            page_title = response["properties"]["title"]["title"][0]["text"]["content"]

            return {
                "status": "success",
                "page_id": page_id,
                "url": page_url,
                "title": page_title,
                "appended_block_ids": appended_block_ids,
                "message": f"Updated Notion page '{page_title}' (content appended)",
            }

        except APIResponseError as e:
            logger.error(f"Notion API error updating page: {e}")
            error_msg = self._api_error_message(e)
            return {
                "status": "error",
                "message": f"Failed to update Notion page: {error_msg}",
            }
        except Exception as e:  # per-item sync failure; continue batch
            logger.error(f"Unexpected error updating Notion page: {e}")
            return {
                "status": "error",
                "message": f"Failed to update Notion page: {e!s}",
            }

    async def delete_page(self, page_id: str) -> dict[str, Any]:
        """
        Delete (archive) a Notion page.

        Note: Notion doesn't truly delete pages, it archives them.

        Args:
            page_id: Page ID to delete

        Returns:
            Dictionary with deletion result

        Raises:
            APIResponseError: If Notion API returns an error
        """
        try:
            notion = await self._get_client()

            # Archive the page (Notion's way of "deleting")
            response = await self._api_call_with_retry(
                notion.pages.update, page_id=page_id, archived=True
            )

            page_title = "Unknown"
            with contextlib.suppress(KeyError, IndexError):
                page_title = response["properties"]["title"]["title"][0]["text"][
                    "content"
                ]

            return {
                "status": "success",
                "page_id": page_id,
                "message": f"Deleted Notion page '{page_title}'",
            }

        except APIResponseError as e:
            logger.error(f"Notion API error deleting page: {e}")
            error_msg = self._api_error_message(e)
            return {
                "status": "error",
                "message": f"Failed to delete Notion page: {error_msg}",
            }
        except Exception as e:  # per-item sync failure; continue batch
            logger.error(f"Unexpected error deleting Notion page: {e}")
            return {
                "status": "error",
                "message": f"Failed to delete Notion page: {e!s}",
            }

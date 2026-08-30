"""Composio Google Calendar toolkit operations."""

from __future__ import annotations

import logging
from typing import Any

from app.services.composio.base import ComposioClientMixin

logger = logging.getLogger(__name__)


class ComposioCalendarMixin(ComposioClientMixin):
    """Google Calendar operations via Composio tools."""

    async def get_calendar_events(
        self,
        connected_account_id: str,
        entity_id: str,
        time_min: str | None = None,
        time_max: str | None = None,
        max_results: int = 250,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """List Google Calendar events via Composio."""
        try:
            params = {
                "max_results": min(max_results, 250),
                "single_events": True,
                "order_by": "startTime",
            }
            if time_min:
                params["time_min"] = time_min
            if time_max:
                params["time_max"] = time_max

            result = await self.execute_tool(
                connected_account_id=connected_account_id,
                tool_name="GOOGLECALENDAR_EVENTS_LIST",
                params=params,
                entity_id=entity_id,
            )

            if not result.get("success"):
                return [], result.get("error", "Unknown error")

            data = result.get("data", {})

            events = []
            if isinstance(data, dict):
                inner_data = data.get("data", data)
                response_data = (
                    inner_data.get("response_data", {})
                    if isinstance(inner_data, dict)
                    else {}
                )
                events = (
                    data.get("items", [])
                    or (
                        inner_data.get("items", [])
                        if isinstance(inner_data, dict)
                        else []
                    )
                    or response_data.get("items", [])
                    or data.get("events", [])
                    or (
                        inner_data.get("events", [])
                        if isinstance(inner_data, dict)
                        else []
                    )
                    or response_data.get("events", [])
                )
            elif isinstance(data, list):
                events = data

            return events, None

        except Exception as e:
            logger.error(f"Failed to list Calendar events: {e!s}")
            return [], str(e)

    async def create_calendar_event(
        self,
        connected_account_id: str,
        entity_id: str,
        summary: str,
        start_datetime: str,
        end_datetime: str,
        timezone: str | None = None,
        description: str | None = None,
        location: str | None = None,
        attendees: list[str] | None = None,
        calendar_id: str = "primary",
    ) -> tuple[str | None, str | None, str | None]:
        """Create a Google Calendar event via GOOGLECALENDAR_CREATE_EVENT."""
        try:
            params: dict[str, Any] = {
                "summary": summary,
                "start_datetime": start_datetime,
                "end_datetime": end_datetime,
                "calendar_id": calendar_id,
            }
            if timezone:
                params["timezone"] = timezone
            if description:
                params["description"] = description
            if location:
                params["location"] = location
            if attendees:
                params["attendees"] = [a for a in attendees if a]

            result = await self.execute_tool(
                connected_account_id=connected_account_id,
                tool_name="GOOGLECALENDAR_CREATE_EVENT",
                params=params,
                entity_id=entity_id,
            )
            if not result.get("success"):
                return None, None, result.get("error", "Unknown error")

            payload = self._unwrap_response_data(result.get("data", {}))
            event_id = None
            html_link = None
            if isinstance(payload, dict):
                event_id = payload.get("id") or payload.get("event_id")
                html_link = payload.get("htmlLink") or payload.get("html_link")
            return event_id, html_link, None
        except Exception as e:
            logger.error(f"Failed to create Calendar event: {e!s}")
            return None, None, str(e)

    async def update_calendar_event(
        self,
        connected_account_id: str,
        entity_id: str,
        event_id: str,
        summary: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        timezone: str | None = None,
        description: str | None = None,
        location: str | None = None,
        attendees: list[str] | None = None,
        calendar_id: str = "primary",
    ) -> tuple[str | None, str | None, str | None]:
        """Patch an existing Google Calendar event via GOOGLECALENDAR_PATCH_EVENT."""
        try:
            params: dict[str, Any] = {
                "event_id": event_id,
                "calendar_id": calendar_id,
            }
            if summary is not None:
                params["summary"] = summary
            if start_time is not None:
                params["start_time"] = start_time
            if end_time is not None:
                params["end_time"] = end_time
            if timezone:
                params["timezone"] = timezone
            if description is not None:
                params["description"] = description
            if location is not None:
                params["location"] = location
            if attendees is not None:
                params["attendees"] = [a for a in attendees if a]

            result = await self.execute_tool(
                connected_account_id=connected_account_id,
                tool_name="GOOGLECALENDAR_PATCH_EVENT",
                params=params,
                entity_id=entity_id,
            )
            if not result.get("success"):
                return None, None, result.get("error", "Unknown error")

            payload = self._unwrap_response_data(result.get("data", {}))
            new_event_id = event_id
            html_link = None
            if isinstance(payload, dict):
                new_event_id = payload.get("id") or payload.get("event_id") or event_id
                html_link = payload.get("htmlLink") or payload.get("html_link")
            return new_event_id, html_link, None
        except Exception as e:
            logger.error(f"Failed to patch Calendar event: {e!s}")
            return None, None, str(e)

    async def delete_calendar_event(
        self,
        connected_account_id: str,
        entity_id: str,
        event_id: str,
        calendar_id: str = "primary",
    ) -> str | None:
        """Delete a Google Calendar event via GOOGLECALENDAR_DELETE_EVENT."""
        try:
            result = await self.execute_tool(
                connected_account_id=connected_account_id,
                tool_name="GOOGLECALENDAR_DELETE_EVENT",
                params={
                    "event_id": event_id,
                    "calendar_id": calendar_id,
                },
                entity_id=entity_id,
            )
            if not result.get("success"):
                return result.get("error", "Unknown error")
            return None
        except Exception as e:
            logger.error(f"Failed to delete Calendar event: {e!s}")
            return str(e)

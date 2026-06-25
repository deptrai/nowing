/**
 * Unit tests — lib/connectors/utils.ts
 * Covers: getConnectorTypeDisplay
 * Priority: P1
 */
import { describe, it, expect } from "vitest";
import { getConnectorTypeDisplay } from "@/lib/connectors/utils";

describe("getConnectorTypeDisplay", () => {
	// API connectors
	it("maps SERPER_API → 'Serper API'", () => {
		expect(getConnectorTypeDisplay("SERPER_API")).toBe("Serper API");
	});

	it("maps TAVILY_API → 'Tavily API'", () => {
		expect(getConnectorTypeDisplay("TAVILY_API")).toBe("Tavily API");
	});

	it("maps SEARXNG_API → 'SearxNG'", () => {
		expect(getConnectorTypeDisplay("SEARXNG_API")).toBe("SearxNG");
	});

	it("maps LINKUP_API → 'Linkup'", () => {
		expect(getConnectorTypeDisplay("LINKUP_API")).toBe("Linkup");
	});

	// Collaboration connectors
	it("maps SLACK_CONNECTOR → 'Slack'", () => {
		expect(getConnectorTypeDisplay("SLACK_CONNECTOR")).toBe("Slack");
	});

	it("maps TEAMS_CONNECTOR → 'Microsoft Teams'", () => {
		expect(getConnectorTypeDisplay("TEAMS_CONNECTOR")).toBe("Microsoft Teams");
	});

	it("maps NOTION_CONNECTOR → 'Notion'", () => {
		expect(getConnectorTypeDisplay("NOTION_CONNECTOR")).toBe("Notion");
	});

	it("maps GITHUB_CONNECTOR → 'GitHub'", () => {
		expect(getConnectorTypeDisplay("GITHUB_CONNECTOR")).toBe("GitHub");
	});

	it("maps JIRA_CONNECTOR → 'Jira'", () => {
		expect(getConnectorTypeDisplay("JIRA_CONNECTOR")).toBe("Jira");
	});

	it("maps DISCORD_CONNECTOR → 'Discord'", () => {
		expect(getConnectorTypeDisplay("DISCORD_CONNECTOR")).toBe("Discord");
	});

	it("maps LINEAR_CONNECTOR → 'Linear'", () => {
		expect(getConnectorTypeDisplay("LINEAR_CONNECTOR")).toBe("Linear");
	});

	// Storage connectors
	it("maps ONEDRIVE_CONNECTOR → 'OneDrive'", () => {
		expect(getConnectorTypeDisplay("ONEDRIVE_CONNECTOR")).toBe("OneDrive");
	});

	it("maps GOOGLE_DRIVE_CONNECTOR → 'Google Drive'", () => {
		expect(getConnectorTypeDisplay("GOOGLE_DRIVE_CONNECTOR")).toBe("Google Drive");
	});

	it("maps DROPBOX_CONNECTOR → 'Dropbox'", () => {
		expect(getConnectorTypeDisplay("DROPBOX_CONNECTOR")).toBe("Dropbox");
	});

	// Google connectors
	it("maps GOOGLE_CALENDAR_CONNECTOR → 'Google Calendar'", () => {
		expect(getConnectorTypeDisplay("GOOGLE_CALENDAR_CONNECTOR")).toBe("Google Calendar");
	});

	it("maps GOOGLE_GMAIL_CONNECTOR → 'Google Gmail'", () => {
		expect(getConnectorTypeDisplay("GOOGLE_GMAIL_CONNECTOR")).toBe("Google Gmail");
	});

	// Composio aliases
	it("maps COMPOSIO_GOOGLE_DRIVE_CONNECTOR → 'Google Drive'", () => {
		expect(getConnectorTypeDisplay("COMPOSIO_GOOGLE_DRIVE_CONNECTOR")).toBe("Google Drive");
	});

	it("maps COMPOSIO_GMAIL_CONNECTOR → 'Gmail'", () => {
		expect(getConnectorTypeDisplay("COMPOSIO_GMAIL_CONNECTOR")).toBe("Gmail");
	});

	it("maps COMPOSIO_GOOGLE_CALENDAR_CONNECTOR → 'Google Calendar'", () => {
		expect(getConnectorTypeDisplay("COMPOSIO_GOOGLE_CALENDAR_CONNECTOR")).toBe("Google Calendar");
	});

	// Other connectors
	it("maps MCP_CONNECTOR → 'MCP Server'", () => {
		expect(getConnectorTypeDisplay("MCP_CONNECTOR")).toBe("MCP Server");
	});

	it("maps WEBCRAWLER_CONNECTOR → 'Web Pages'", () => {
		expect(getConnectorTypeDisplay("WEBCRAWLER_CONNECTOR")).toBe("Web Pages");
	});

	it("maps YOUTUBE_CONNECTOR → 'YouTube'", () => {
		expect(getConnectorTypeDisplay("YOUTUBE_CONNECTOR")).toBe("YouTube");
	});

	it("maps ELASTICSEARCH_CONNECTOR → 'Elasticsearch'", () => {
		expect(getConnectorTypeDisplay("ELASTICSEARCH_CONNECTOR")).toBe("Elasticsearch");
	});

	// Fallback — unknown type returns the type itself
	it("returns the raw type string for unknown connector", () => {
		expect(getConnectorTypeDisplay("UNKNOWN_CUSTOM_CONNECTOR")).toBe("UNKNOWN_CUSTOM_CONNECTOR");
	});

	it("returns empty string for empty input", () => {
		expect(getConnectorTypeDisplay("")).toBe("");
	});
});

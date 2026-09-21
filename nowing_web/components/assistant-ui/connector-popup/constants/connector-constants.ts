import { EnumConnectorName } from "@/contracts/enums/connector";

/**
 * Connectors retired during the MCP migration (no viable official MCP server).
 * The catalog card is shown disabled with a "Deprecated" badge so existing
 * users understand why; the backend `/add` routes also refuse with HTTP 410.
 * Reinstate by removing the type here and in the backend
 * `DEPRECATED_CONNECTOR_TYPES` if demand returns.
 */
export const DEPRECATED_CONNECTOR_TYPES = new Set<string>([
	EnumConnectorName.DISCORD_CONNECTOR,
	EnumConnectorName.TEAMS_CONNECTOR,
	EnumConnectorName.LUMA_CONNECTOR,
	// Search APIs retired by the Google-only web-search consolidation. Public
	// web search now runs through the google_search subagent; Tavily/Linkup can
	// still be added via the generic Custom MCP connector (API-key headers).
	EnumConnectorName.TAVILY_API,
	EnumConnectorName.SEARXNG_API,
	EnumConnectorName.LINKUP_API,
	EnumConnectorName.BAIDU_SEARCH_API,
	// Legacy content crawlers/search retired in favor of the file Import menu and
	// hosted MCP tooling. Existing rows stay manageable; new connections refused.
	EnumConnectorName.YOUTUBE_CONNECTOR,
	EnumConnectorName.WEBCRAWLER_CONNECTOR,
	EnumConnectorName.ELASTICSEARCH_CONNECTOR,
]);

/**
 * File-import connectors surfaced through the Documents sidebar "Import" menu
 * instead of the external-MCP connector catalog. They index remote files into
 * the knowledge base, so they belong with uploads, not with live MCP tools.
 */
export const IMPORT_CONNECTOR_TYPES = new Set<string>([
	EnumConnectorName.GOOGLE_DRIVE_CONNECTOR,
	EnumConnectorName.COMPOSIO_GOOGLE_DRIVE_CONNECTOR,
	EnumConnectorName.ONEDRIVE_CONNECTOR,
	EnumConnectorName.DROPBOX_CONNECTOR,
]);

/**
 * Connectors that operate in real time (no background indexing).
 * Used to adjust UI: hide sync controls, show "Connected" instead of doc counts.
 */
export const LIVE_CONNECTOR_TYPES = new Set<string>([
	EnumConnectorName.LINEAR_CONNECTOR,
	EnumConnectorName.SLACK_CONNECTOR,
	EnumConnectorName.JIRA_CONNECTOR,
	EnumConnectorName.CLICKUP_CONNECTOR,
	EnumConnectorName.AIRTABLE_CONNECTOR,
	EnumConnectorName.DISCORD_CONNECTOR,
	EnumConnectorName.TEAMS_CONNECTOR,
	EnumConnectorName.GOOGLE_CALENDAR_CONNECTOR,
	EnumConnectorName.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR,
	EnumConnectorName.GOOGLE_GMAIL_CONNECTOR,
	EnumConnectorName.COMPOSIO_GMAIL_CONNECTOR,
	EnumConnectorName.LUMA_CONNECTOR,
	// Migrated to hosted MCP: real-time agent tools, no background indexing.
	EnumConnectorName.NOTION_CONNECTOR,
	EnumConnectorName.CONFLUENCE_CONNECTOR,
]);

// OAuth Connectors (Quick Connect)
export const OAUTH_CONNECTORS = [
	{
		id: "google-drive-connector",
		title: "Google Drive",
		description: "Search your Drive files",
		descKey: "desc_google_drive_connector",
		connectorType: EnumConnectorName.GOOGLE_DRIVE_CONNECTOR,
		authEndpoint: "/api/v1/auth/google/drive/connector/add/",
		selfHostedOnly: true,
	},
	{
		id: "google-gmail-connector",
		title: "Gmail",
		description: "Search, read, draft, and send emails",
		descKey: "desc_google_gmail_connector",
		connectorType: EnumConnectorName.GOOGLE_GMAIL_CONNECTOR,
		authEndpoint: "/api/v1/auth/google/gmail/connector/add/",
		selfHostedOnly: true,
	},
	{
		id: "google-calendar-connector",
		title: "Google Calendar",
		description: "Search and manage your events",
		descKey: "desc_google_calendar_connector",
		connectorType: EnumConnectorName.GOOGLE_CALENDAR_CONNECTOR,
		authEndpoint: "/api/v1/auth/google/calendar/connector/add/",
		selfHostedOnly: true,
	},
	{
		id: "airtable-connector",
		title: "Airtable",
		description: "Browse bases, tables, and records",
		descKey: "desc_airtable_connector",
		connectorType: EnumConnectorName.AIRTABLE_CONNECTOR,
		authEndpoint: "/api/v1/auth/mcp/airtable/connector/add/",
	},
	{
		id: "notion-connector",
		title: "Notion",
		description: "Search, read, and create pages",
		descKey: "desc_notion_connector",
		connectorType: EnumConnectorName.NOTION_CONNECTOR,
		authEndpoint: "/api/v1/auth/mcp/notion/connector/add/",
	},
	{
		id: "linear-connector",
		title: "Linear",
		description: "Search, read, and manage issues & projects",
		descKey: "desc_linear_connector",
		connectorType: EnumConnectorName.LINEAR_CONNECTOR,
		authEndpoint: "/api/v1/auth/mcp/linear/connector/add/",
	},
	{
		id: "slack-connector",
		title: "Slack",
		description: "Search and read channels and threads",
		descKey: "desc_slack_connector",
		connectorType: EnumConnectorName.SLACK_CONNECTOR,
		authEndpoint: "/api/v1/auth/mcp/slack/connector/add/",
	},
	{
		id: "teams-connector",
		title: "Microsoft Teams",
		description: "Search, read, and send messages",
		descKey: "desc_teams_connector",
		connectorType: EnumConnectorName.TEAMS_CONNECTOR,
		authEndpoint: "/api/v1/auth/teams/connector/add/",
	},
	{
		id: "onedrive-connector",
		title: "OneDrive",
		description: "Search your OneDrive files",
		descKey: "desc_onedrive_connector",
		connectorType: EnumConnectorName.ONEDRIVE_CONNECTOR,
		authEndpoint: "/api/v1/auth/onedrive/connector/add/",
	},
	{
		id: "dropbox-connector",
		title: "Dropbox",
		description: "Search your Dropbox files",
		descKey: "desc_dropbox_connector",
		connectorType: EnumConnectorName.DROPBOX_CONNECTOR,
		authEndpoint: "/api/v1/auth/dropbox/connector/add/",
	},
	{
		id: "discord-connector",
		title: "Discord",
		description: "Search, read, and send messages",
		descKey: "desc_discord_connector",
		connectorType: EnumConnectorName.DISCORD_CONNECTOR,
		authEndpoint: "/api/v1/auth/discord/connector/add/",
	},
	{
		id: "jira-connector",
		title: "Jira",
		description: "Search, read, and manage issues",
		descKey: "desc_jira_connector",
		connectorType: EnumConnectorName.JIRA_CONNECTOR,
		authEndpoint: "/api/v1/auth/mcp/jira/connector/add/",
	},
	{
		id: "confluence-connector",
		title: "Confluence",
		description: "Search, read, and create pages",
		descKey: "desc_confluence_connector",
		connectorType: EnumConnectorName.CONFLUENCE_CONNECTOR,
		authEndpoint: "/api/v1/auth/mcp/confluence/connector/add/",
	},
	{
		id: "clickup-connector",
		title: "ClickUp",
		description: "Search and read tasks",
		descKey: "desc_clickup_connector",
		connectorType: EnumConnectorName.CLICKUP_CONNECTOR,
		authEndpoint: "/api/v1/auth/mcp/clickup/connector/add/",
	},
] as const;

// Content Sources (tools that extract and import content from external sources)
export const CRAWLERS = [
	{
		id: "youtube-crawler",
		title: "YouTube",
		description: "Crawl YouTube channels and playlists",
		descKey: "desc_youtube_crawler",
		connectorType: EnumConnectorName.YOUTUBE_CONNECTOR,
	},
	{
		id: "webcrawler-connector",
		title: "Web Pages",
		description: "Index and periodically sync web content",
		descKey: "desc_webcrawler_connector",
		connectorType: EnumConnectorName.WEBCRAWLER_CONNECTOR,
	},
] as const;

// Non-OAuth Connectors (redirect to old connector config pages)
export const OTHER_CONNECTORS = [
	{
		id: "bookstack-connector",
		title: "BookStack",
		description: "Search BookStack docs",
		descKey: "desc_bookstack_connector",
		connectorType: EnumConnectorName.BOOKSTACK_CONNECTOR,
	},
	{
		id: "github-connector",
		title: "GitHub",
		description: "Search repositories",
		descKey: "desc_github_connector",
		connectorType: EnumConnectorName.GITHUB_CONNECTOR,
	},
	{
		id: "luma-connector",
		title: "Luma",
		description: "Browse, read, and create events",
		descKey: "desc_luma_connector",
		connectorType: EnumConnectorName.LUMA_CONNECTOR,
	},
	{
		id: "elasticsearch-connector",
		title: "Elasticsearch",
		description: "Search ES indexes",
		descKey: "desc_elasticsearch_connector",
		connectorType: EnumConnectorName.ELASTICSEARCH_CONNECTOR,
	},
	{
		id: "tavily-api",
		title: "Tavily AI",
		description: "Search with Tavily",
		descKey: "desc_tavily_api",
		connectorType: EnumConnectorName.TAVILY_API,
	},
	{
		id: "linkup-api",
		title: "Linkup API",
		description: "Search with Linkup",
		descKey: "desc_linkup_api",
		connectorType: EnumConnectorName.LINKUP_API,
	},
	{
		id: "baidu-search-api",
		title: "Baidu Search",
		description: "Search with Baidu",
		descKey: "desc_baidu_search_api",
		connectorType: EnumConnectorName.BAIDU_SEARCH_API,
	},
	{
		id: "circleback-connector",
		title: "Circleback",
		description: "Receive meeting notes, transcripts",
		descKey: "desc_circleback_connector",
		connectorType: EnumConnectorName.CIRCLEBACK_CONNECTOR,
	},
	{
		id: "mcp-connector",
		title: "MCPs",
		description: "Connect to MCP servers for AI tools",
		descKey: "desc_mcp_connector",
		connectorType: EnumConnectorName.MCP_CONNECTOR,
	},
	{
		id: "obsidian-connector",
		title: "Obsidian",
		description: "Sync your Obsidian vault on desktop or mobile",
		descKey: "desc_obsidian_connector",
		connectorType: EnumConnectorName.OBSIDIAN_CONNECTOR,
	},
	{
		id: "rss-feed-connector",
		title: "RSS",
		description: "Index Vietnamese news RSS feeds",
		descKey: "desc_rss_feed_connector",
		connectorType: EnumConnectorName.RSS_FEED,
	},
] as const;

// Composio Connectors - Individual entries for each supported toolkit
export const COMPOSIO_CONNECTORS = [
	{
		id: "composio-googledrive",
		title: "Google Drive",
		description: "Search your Drive files via Composio",
		descKey: "desc_composio_googledrive",
		connectorType: EnumConnectorName.COMPOSIO_GOOGLE_DRIVE_CONNECTOR,
		authEndpoint: "/api/v1/auth/composio/connector/add/?toolkit_id=googledrive",
	},
	{
		id: "composio-gmail",
		title: "Gmail",
		description: "Search, read, draft, and send emails via Composio",
		descKey: "desc_composio_gmail",
		connectorType: EnumConnectorName.COMPOSIO_GMAIL_CONNECTOR,
		authEndpoint: "/api/v1/auth/composio/connector/add/?toolkit_id=gmail",
	},
	{
		id: "composio-googlecalendar",
		title: "Google Calendar",
		description: "Search and manage your events via Composio",
		descKey: "desc_composio_googlecalendar",
		connectorType: EnumConnectorName.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR,
		authEndpoint: "/api/v1/auth/composio/connector/add/?toolkit_id=googlecalendar",
	},
] as const;

export const CONNECTOR_DISPLAY_DEFINITIONS = [
	...OAUTH_CONNECTORS,
	...CRAWLERS,
	...OTHER_CONNECTORS,
	...COMPOSIO_CONNECTORS,
] as const;

export function getConnectorTitle(connectorType: string): string {
	return (
		CONNECTOR_DISPLAY_DEFINITIONS.find((connector) => connector.connectorType === connectorType)
			?.title ?? connectorType
	);
}

/**
 * Primary way a user interacts with a connector.
 * Drives the two top-level groupings in the connector catalog UI.
 */
export type ConnectorCategory = "knowledge_base" | "tools_live";

export const CONNECTOR_CATEGORY_LABELS: Record<ConnectorCategory, string> = {
	knowledge_base: "Knowledge Base",
	tools_live: "Tools & Live Sources",
};

const KNOWLEDGE_BASE_CONNECTOR_TYPES = new Set<string>([
	EnumConnectorName.GOOGLE_DRIVE_CONNECTOR,
	EnumConnectorName.COMPOSIO_GOOGLE_DRIVE_CONNECTOR,
	EnumConnectorName.ONEDRIVE_CONNECTOR,
	EnumConnectorName.DROPBOX_CONNECTOR,
	EnumConnectorName.NOTION_CONNECTOR,
	EnumConnectorName.CONFLUENCE_CONNECTOR,
	EnumConnectorName.YOUTUBE_CONNECTOR,
	EnumConnectorName.WEBCRAWLER_CONNECTOR,
	EnumConnectorName.BOOKSTACK_CONNECTOR,
	EnumConnectorName.GITHUB_CONNECTOR,
	EnumConnectorName.ELASTICSEARCH_CONNECTOR,
	EnumConnectorName.CIRCLEBACK_CONNECTOR,
	EnumConnectorName.OBSIDIAN_CONNECTOR,
]);

/** Unmapped connectors surface under Tools & Live Sources. */
export function getConnectorCategory(connectorType: string): ConnectorCategory {
	return KNOWLEDGE_BASE_CONNECTOR_TYPES.has(connectorType) ? "knowledge_base" : "tools_live";
}

// Composio Toolkits (available integrations via Composio)
export const COMPOSIO_TOOLKITS = [
	{
		id: "googledrive",
		name: "Google Drive",
		description: "Search your Drive files",
		descKey: "desc_googledrive",
		isIndexable: true,
	},
	{
		id: "gmail",
		name: "Gmail",
		description: "Search, read, draft, and send emails",
		descKey: "desc_gmail",
		isIndexable: false,
	},
	{
		id: "googlecalendar",
		name: "Google Calendar",
		description: "Search and manage your events",
		descKey: "desc_googlecalendar",
		isIndexable: false,
	},
	{
		id: "slack",
		name: "Slack",
		description: "Search Slack messages",
		descKey: "desc_slack",
		isIndexable: false,
	},
	{
		id: "notion",
		name: "Notion",
		description: "Search Notion pages",
		descKey: "desc_notion",
		isIndexable: false,
	},
	{
		id: "github",
		name: "GitHub",
		description: "Search repositories",
		descKey: "desc_github",
		isIndexable: false,
	},
] as const;

export interface AutoIndexConfig {
	daysBack: number;
	daysForward: number;
	frequencyMinutes: number;
	syncDescription: string;
}

export const AUTO_INDEX_DEFAULTS: Record<string, AutoIndexConfig> = {
	[EnumConnectorName.NOTION_CONNECTOR]: {
		daysBack: 365,
		daysForward: 0,
		frequencyMinutes: 1440,
		syncDescription: "Syncing your pages.",
	},
	[EnumConnectorName.CONFLUENCE_CONNECTOR]: {
		daysBack: 365,
		daysForward: 0,
		frequencyMinutes: 1440,
		syncDescription: "Syncing your documentation.",
	},
};

export const AUTO_INDEX_CONNECTOR_TYPES = new Set<string>(Object.keys(AUTO_INDEX_DEFAULTS));

// Re-export IndexingConfigState from schemas for backward compatibility
export type { IndexingConfigState } from "./connector-popup.schemas";

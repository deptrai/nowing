"use client";

export const BANNER_CONNECTORS = [
	{ type: "GOOGLE_DRIVE_CONNECTOR", label: "Google Drive" },
	{ type: "GOOGLE_GMAIL_CONNECTOR", label: "Gmail" },
	{ type: "NOTION_CONNECTOR", label: "Notion" },
	{ type: "YOUTUBE_CONNECTOR", label: "YouTube" },
	{ type: "SLACK_CONNECTOR", label: "Slack" },
] as const;

export const BANNER_DISMISSED_KEY = "nowing-connect-tools-banner-dismissed";
export const OUTREACH_BETA_DISMISSED_KEY = "nowing-outreach-beta-card-dismissed";

export interface ToolGroup {
	label: string;
	tools: string[];
	connectorIcon?: string;
	tooltip?: string;
	tooltipKey?: string;
}

export const TOOL_GROUPS: ToolGroup[] = [
	{
		label: "Research",
		tools: ["scrape_webpage"],
	},
	{
		label: "Generate",
		tools: [
			"generate_podcast",
			"generate_video_presentation",
			"generate_report",
			"generate_resume",
			"generate_image",
		],
	},
	{
		label: "Memory",
		tools: ["update_memory"],
	},
	{
		label: "Gmail",
		tools: [
			"search_gmail",
			"read_gmail_email",
			"create_gmail_draft",
			"update_gmail_draft",
			"send_gmail_email",
			"trash_gmail_email",
		],
		connectorIcon: "gmail",
		tooltip: "assistant.connector_gmail_tooltip",
		tooltipKey: "assistant.connector_gmail_tooltip",
	},
	{
		label: "Google Calendar",
		tools: [
			"search_calendar_events",
			"create_calendar_event",
			"update_calendar_event",
			"delete_calendar_event",
		],
		connectorIcon: "google_calendar",
		tooltip: "assistant.connector_gcal_tooltip",
		tooltipKey: "assistant.connector_gcal_tooltip",
	},
	{
		label: "Google Drive",
		tools: ["create_google_drive_file", "delete_google_drive_file"],
		connectorIcon: "google_drive",
		tooltip: "assistant.connector_drive_tooltip",
		tooltipKey: "assistant.connector_drive_tooltip",
	},
	{
		label: "OneDrive",
		tools: ["create_onedrive_file", "delete_onedrive_file"],
		connectorIcon: "onedrive",
		tooltip: "assistant.connector_onedrive_tooltip",
		tooltipKey: "assistant.connector_onedrive_tooltip",
	},
	{
		label: "Dropbox",
		tools: ["create_dropbox_file", "delete_dropbox_file"],
		connectorIcon: "dropbox",
		tooltip: "assistant.connector_dropbox_tooltip",
		tooltipKey: "assistant.connector_dropbox_tooltip",
	},
	{
		label: "Notion",
		tools: ["create_notion_page", "update_notion_page", "delete_notion_page"],
		connectorIcon: "notion",
		tooltip: "assistant.connector_notion_tooltip",
		tooltipKey: "assistant.connector_notion_tooltip",
	},
	{
		label: "Linear",
		tools: ["create_linear_issue", "update_linear_issue", "delete_linear_issue"],
		connectorIcon: "linear",
		tooltip: "assistant.connector_linear_tooltip",
		tooltipKey: "assistant.connector_linear_tooltip",
	},
	{
		label: "Jira",
		tools: ["create_jira_issue", "update_jira_issue", "delete_jira_issue"],
		connectorIcon: "jira",
		tooltip: "assistant.connector_jira_tooltip",
		tooltipKey: "assistant.connector_jira_tooltip",
	},
	{
		label: "Confluence",
		tools: ["create_confluence_page", "update_confluence_page", "delete_confluence_page"],
		connectorIcon: "confluence",
		tooltip: "assistant.connector_confluence_tooltip",
		tooltipKey: "assistant.connector_confluence_tooltip",
	},
	{
		label: "Discord",
		tools: ["list_discord_channels", "read_discord_messages", "send_discord_message"],
		connectorIcon: "discord",
		tooltip: "assistant.connector_discord_tooltip",
		tooltipKey: "assistant.connector_discord_tooltip",
	},
	{
		label: "Microsoft Teams",
		tools: ["list_teams_channels", "read_teams_messages", "send_teams_message"],
		connectorIcon: "teams",
		tooltip: "assistant.connector_teams_tooltip",
		tooltipKey: "assistant.connector_teams_tooltip",
	},
	{
		label: "Luma",
		tools: ["list_luma_events", "read_luma_event", "create_luma_event"],
		connectorIcon: "luma",
		tooltip: "assistant.connector_luma_tooltip",
		tooltipKey: "assistant.connector_luma_tooltip",
	},
];

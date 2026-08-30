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
		tooltip: "Search, read, draft, update, send, and trash emails in Gmail",
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
		tooltip: "Search, create, update, and delete events in Google Calendar",
	},
	{
		label: "Google Drive",
		tools: ["create_google_drive_file", "delete_google_drive_file"],
		connectorIcon: "google_drive",
		tooltip: "Create and delete files in Google Drive",
	},
	{
		label: "OneDrive",
		tools: ["create_onedrive_file", "delete_onedrive_file"],
		connectorIcon: "onedrive",
		tooltip: "Create and delete files in OneDrive",
	},
	{
		label: "Dropbox",
		tools: ["create_dropbox_file", "delete_dropbox_file"],
		connectorIcon: "dropbox",
		tooltip: "Create and delete files in Dropbox",
	},
	{
		label: "Notion",
		tools: ["create_notion_page", "update_notion_page", "delete_notion_page"],
		connectorIcon: "notion",
		tooltip: "Create, update, and delete pages in Notion",
	},
	{
		label: "Linear",
		tools: ["create_linear_issue", "update_linear_issue", "delete_linear_issue"],
		connectorIcon: "linear",
		tooltip: "Create, update, and delete issues in Linear",
	},
	{
		label: "Jira",
		tools: ["create_jira_issue", "update_jira_issue", "delete_jira_issue"],
		connectorIcon: "jira",
		tooltip: "Create, update, and delete issues in Jira",
	},
	{
		label: "Confluence",
		tools: ["create_confluence_page", "update_confluence_page", "delete_confluence_page"],
		connectorIcon: "confluence",
		tooltip: "Create, update, and delete pages in Confluence",
	},
	{
		label: "Discord",
		tools: ["list_discord_channels", "read_discord_messages", "send_discord_message"],
		connectorIcon: "discord",
		tooltip: "List channels, read messages, and send messages in Discord",
	},
	{
		label: "Microsoft Teams",
		tools: ["list_teams_channels", "read_teams_messages", "send_teams_message"],
		connectorIcon: "teams",
		tooltip: "List channels, read messages, and send messages in Microsoft Teams",
	},
	{
		label: "Luma",
		tools: ["list_luma_events", "read_luma_event", "create_luma_event"],
		connectorIcon: "luma",
		tooltip: "List, read, and create events in Luma",
	},
];

import { IconUsersGroup } from "@tabler/icons-react";
import {
	Brain,
	File,
	FileText,
	Globe,
	Microscope,
	Newspaper,
	Search,
	Sparkles,
	Telescope,
	Webhook,
} from "lucide-react";
import Image from "next/image";
import type { ComponentType } from "react";
import { cn } from "@/lib/utils";
import { EnumConnectorName } from "./connector";

const IMAGE_CONNECTORS: Record<string, { src: string; alt: string }> = {
	[EnumConnectorName.LINKUP_API]: { src: "/connectors/linkup.svg", alt: "Linkup" },
	[EnumConnectorName.LINEAR_CONNECTOR]: { src: "/connectors/linear.svg", alt: "Linear" },
	[EnumConnectorName.GITHUB_CONNECTOR]: { src: "/connectors/github.svg", alt: "GitHub" },
	[EnumConnectorName.TAVILY_API]: { src: "/connectors/tavily.svg", alt: "Tavily" },
	[EnumConnectorName.SEARXNG_API]: { src: "/connectors/searxng.svg", alt: "SearXNG" },
	[EnumConnectorName.BAIDU_SEARCH_API]: { src: "/connectors/baidu-search.svg", alt: "Baidu" },
	[EnumConnectorName.SLACK_CONNECTOR]: { src: "/connectors/slack.svg", alt: "Slack" },
	[EnumConnectorName.TEAMS_CONNECTOR]: {
		src: "/connectors/microsoft-teams.svg",
		alt: "Microsoft Teams",
	},
	[EnumConnectorName.ONEDRIVE_CONNECTOR]: { src: "/connectors/onedrive.svg", alt: "OneDrive" },
	[EnumConnectorName.NOTION_CONNECTOR]: { src: "/connectors/notion.svg", alt: "Notion" },
	[EnumConnectorName.DROPBOX_CONNECTOR]: { src: "/connectors/dropbox.svg", alt: "Dropbox" },
	[EnumConnectorName.DISCORD_CONNECTOR]: { src: "/connectors/discord.svg", alt: "Discord" },
	[EnumConnectorName.JIRA_CONNECTOR]: { src: "/connectors/jira.svg", alt: "Jira" },
	[EnumConnectorName.GOOGLE_CALENDAR_CONNECTOR]: {
		src: "/connectors/google-calendar.svg",
		alt: "Google Calendar",
	},
	[EnumConnectorName.GOOGLE_GMAIL_CONNECTOR]: {
		src: "/connectors/google-gmail.svg",
		alt: "Gmail",
	},
	[EnumConnectorName.GOOGLE_DRIVE_CONNECTOR]: {
		src: "/connectors/google-drive.svg",
		alt: "Google Drive",
	},
	[EnumConnectorName.AIRTABLE_CONNECTOR]: { src: "/connectors/airtable.svg", alt: "Airtable" },
	[EnumConnectorName.CONFLUENCE_CONNECTOR]: {
		src: "/connectors/confluence.svg",
		alt: "Confluence",
	},
	[EnumConnectorName.BOOKSTACK_CONNECTOR]: {
		src: "/connectors/bookstack.svg",
		alt: "BookStack",
	},
	[EnumConnectorName.CLICKUP_CONNECTOR]: { src: "/connectors/clickup.svg", alt: "ClickUp" },
	[EnumConnectorName.LUMA_CONNECTOR]: { src: "/connectors/luma.svg", alt: "Luma" },
	[EnumConnectorName.ELASTICSEARCH_CONNECTOR]: {
		src: "/connectors/elasticsearch.svg",
		alt: "Elasticsearch",
	},
	[EnumConnectorName.YOUTUBE_CONNECTOR]: { src: "/connectors/youtube.svg", alt: "YouTube" },
	[EnumConnectorName.CIRCLEBACK_CONNECTOR]: {
		src: "/connectors/circleback.svg",
		alt: "Circleback",
	},
	[EnumConnectorName.OBSIDIAN_CONNECTOR]: { src: "/connectors/obsidian.svg", alt: "Obsidian" },
	[EnumConnectorName.COMPOSIO_GOOGLE_DRIVE_CONNECTOR]: {
		src: "/connectors/google-drive.svg",
		alt: "Google Drive",
	},
	[EnumConnectorName.COMPOSIO_GMAIL_CONNECTOR]: {
		src: "/connectors/google-gmail.svg",
		alt: "Gmail",
	},
	[EnumConnectorName.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR]: {
		src: "/connectors/google-calendar.svg",
		alt: "Google Calendar",
	},
	// Additional cases for non-enum connector types
	YOUTUBE_VIDEO: { src: "/connectors/youtube.svg", alt: "YouTube" },
	MICROSOFT_TEAMS: { src: "/connectors/microsoft-teams.svg", alt: "Microsoft Teams" },
	"ms-teams": { src: "/connectors/microsoft-teams.svg", alt: "Microsoft Teams" },
	ZOOM: { src: "/connectors/zoom.svg", alt: "Zoom" },
	zoom: { src: "/connectors/zoom.svg", alt: "Zoom" },
	GOOGLE_DRIVE_FILE: { src: "/connectors/google-drive.svg", alt: "Google Drive" },
	DROPBOX_FILE: { src: "/connectors/dropbox.svg", alt: "Dropbox" },
	ONEDRIVE_FILE: { src: "/connectors/onedrive.svg", alt: "OneDrive" },
};

const ICON_CONNECTORS: Record<string, ComponentType<{ className?: string }>> = {
	[EnumConnectorName.WEBCRAWLER_CONNECTOR]: Globe,
	[EnumConnectorName.RSS_FEED]: Newspaper,
	CIRCLEBACK: IconUsersGroup,
	CRAWLED_URL: Globe,
	FILE: File,
	LOCAL_FOLDER_FILE: File,
	NOTE: FileText,
	EXTENSION: Webhook,
	USER_MEMORY: Brain,
	TEAM_MEMORY: Brain,
	DEEP: Sparkles,
	DEEPER: Microscope,
	DEEPEST: Telescope,
};

const MCP_CONNECTORS = new Set<string>([
	EnumConnectorName.MCP_CONNECTOR,
	EnumConnectorName.EXA_MCP_CONNECTOR,
	EnumConnectorName.MEDIRUS_MCP_CONNECTOR,
]);

export const getConnectorIcon = (connectorType: EnumConnectorName | string, className?: string) => {
	const img = IMAGE_CONNECTORS[connectorType];
	if (img) {
		return (
			<Image
				src={img.src}
				alt={img.alt}
				className={`${className || "h-5 w-5"} select-none pointer-events-none`}
				width={20}
				height={20}
				draggable={false}
			/>
		);
	}

	const IconComponent = ICON_CONNECTORS[connectorType];
	if (IconComponent) {
		return <IconComponent className={className || "h-4 w-4"} />;
	}

	if (MCP_CONNECTORS.has(connectorType)) {
		return (
			<span
				aria-hidden="true"
				className={cn("shrink-0 bg-current", className || "size-5")}
				style={{
					mask: "url('/connectors/modelcontextprotocol.svg') center / contain no-repeat",
					WebkitMask: "url('/connectors/modelcontextprotocol.svg') center / contain no-repeat",
				}}
			/>
		);
	}

	return <Search className={className || "h-4 w-4"} />;
};

export interface TabHistoryEntry {
	url: string;
	title: string;
	entryTime: number;
	reffererUrl: string;
	duration: number;
	pageContentMarkdown?: string;
	renderedHtml?: string;
}

export interface WebHistory {
	tabsessionId: number;
	tabHistory: TabHistoryEntry[];
}

export interface UrlQueueEntry {
	tabsessionId: number;
	urlQueue: string[];
}

export interface TimeQueueEntry {
	tabsessionId: number;
	timeQueue: number[];
}

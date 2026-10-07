import type { PlasmoMessaging } from "@plasmohq/messaging";

import { Storage } from "@plasmohq/storage";
import { convertHtmlToMarkdown } from "dom-to-semantic-markdown";
import { DOMParser } from "linkedom";
import { buildBackendUrl } from "~utils/backend-url";
import { getRenderedHtml, webhistoryToLangChainDocument } from "~utils/commons";
import type { TabHistoryEntry, TimeQueueEntry, UrlQueueEntry } from "~utils/interfaces";

// @ts-ignore
globalThis.Node = {
	ELEMENT_NODE: 1,
	ATTRIBUTE_NODE: 2,
	TEXT_NODE: 3,
	CDATA_SECTION_NODE: 4,
	PROCESSING_INSTRUCTION_NODE: 7,
	COMMENT_NODE: 8,
	DOCUMENT_NODE: 9,
	DOCUMENT_TYPE_NODE: 10,
	DOCUMENT_FRAGMENT_NODE: 11,
};

const handler: PlasmoMessaging.MessageHandler = async (_req, res) => {
	try {
		chrome.tabs.query({ active: true, currentWindow: true }, async (tabs) => {
			const storage = new Storage({ area: "local" });
			const tab = tabs[0];
			if (tab.id) {
				const tabId: number = tab.id;
				console.log("tabs", tabs);
				const result = await chrome.scripting.executeScript({
					// @ts-ignore
					target: { tabId: tab.id },
					// @ts-ignore
					func: getRenderedHtml,
					// world: "MAIN"
				});

				console.log("SnapRes", result);

				const toPushInTabHistory = result[0].result as TabHistoryEntry & {
					renderedHtml: string;
				};

				toPushInTabHistory.pageContentMarkdown = convertHtmlToMarkdown(
					toPushInTabHistory.renderedHtml,
					{
						extractMainContent: true,
						enableTableColumnTracking: true,
						includeMetaData: false,
						overrideDOMParser: new DOMParser(),
					}
				);

				const { renderedHtml: _renderedHtml, ...toSave } = toPushInTabHistory;

				console.log("toPushInTabHistory", toPushInTabHistory);

				const urlQueueListObj = (await storage.get("urlQueueList")) as {
					urlQueueList?: UrlQueueEntry[];
				};
				const timeQueueListObj = (await storage.get("timeQueueList")) as {
					timeQueueList?: TimeQueueEntry[];
				};

				const isUrlQueueThere = urlQueueListObj.urlQueueList?.find(
					(data: UrlQueueEntry) => data.tabsessionId === tabId
				);
				const isTimeQueueThere = timeQueueListObj.timeQueueList?.find(
					(data: TimeQueueEntry) => data.tabsessionId === tabId
				);

				toPushInTabHistory.duration =
					toPushInTabHistory.entryTime - (isTimeQueueThere?.timeQueue.at(-1) ?? 0);
				if ((isUrlQueueThere?.urlQueue.length ?? 0) === 1) {
					toPushInTabHistory.reffererUrl = "START";
				}
				if ((isUrlQueueThere?.urlQueue.length ?? 0) > 1) {
					toPushInTabHistory.reffererUrl = isUrlQueueThere?.urlQueue.at(-2) ?? "";
				}

				const toSaveFinally: { metadata: Record<string, unknown>; pageContent: unknown }[] = [];

				const markdownFormat = webhistoryToLangChainDocument(tab.id, [toSave]);
				toSaveFinally.push(...markdownFormat);

				console.log("toSaveFinally", toSaveFinally);

				// Log first item to debug metadata structure
				if (toSaveFinally.length > 0) {
					console.log("First item metadata:", toSaveFinally[0].metadata);
				}

				// Create content array for documents in the format expected by the new API
				// The metadata is already in the correct format in toSaveFinally
				const content = toSaveFinally.map((item) => ({
					metadata: {
						BrowsingSessionId: String(item.metadata.BrowsingSessionId || ""),
						VisitedWebPageURL: String(item.metadata.VisitedWebPageURL || ""),
						VisitedWebPageTitle: String(item.metadata.VisitedWebPageTitle || "No Title"),
						VisitedWebPageDateWithTimeInISOString: String(
							item.metadata.VisitedWebPageDateWithTimeInISOString || ""
						),
						VisitedWebPageReffererURL: String(item.metadata.VisitedWebPageReffererURL || ""),
						VisitedWebPageVisitDurationInMilliseconds: String(
							item.metadata.VisitedWebPageVisitDurationInMilliseconds || "0"
						),
					},
					pageContent: String(item.pageContent || ""),
				}));

				const token = await storage.get("token");
				const workspace_id = parseInt(await storage.get("workspace_id"), 10);

				const toSend = {
					document_type: "EXTENSION",
					content: content,
					workspace_id: workspace_id,
				};

				const requestOptions = {
					method: "POST",
					headers: {
						"Content-Type": "application/json",
						Authorization: `Bearer ${token}`,
					},
					body: JSON.stringify(toSend),
				};

				const response = await fetch(await buildBackendUrl("/api/v1/documents"), requestOptions);
				const resp = await response.json();
				if (resp) {
					res.send({
						message: "Snapshot Saved Successfully",
					});
				}
			}
		});
	} catch (error) {
		console.log(error);
	}
};

export default handler;

import type { PlasmoMessaging } from "@plasmohq/messaging";
import { Storage } from "@plasmohq/storage";
import { buildBackendUrl } from "~utils/backend-url";
import type { WebHistory } from "~utils/interfaces";
import { emptyArr, webhistoryToLangChainDocument } from "~utils/commons";

const clearMemory = async () => {
	try {
		const storage = new Storage({ area: "local" });

		const webHistory = (await storage.get("webhistory")) as {
			webhistory?: WebHistory[];
		};
		const urlQueue = (await storage.get("urlQueueList")) as {
			urlQueueList?: WebHistory[];
		};
		const timeQueue = (await storage.get("timeQueueList")) as {
			timeQueueList?: WebHistory[];
		};

		if (!webHistory.webhistory) {
			return;
		}

		//Main Cleanup COde
		chrome.tabs.query({}, async (tabs) => {
			//Get Active Tabs Ids
			const actives = tabs.map((tab) => tab.id).filter((id): id is number => id != null);

			//Only retain which is still active
			const newHistory = webHistory.webhistory?.map((element) => {
				if (actives.includes(element.tabsessionId)) {
					return element;
				}
			});

			const newUrlQueue = urlQueue.urlQueueList?.map((element) => {
				if (actives.includes(element.tabsessionId)) {
					return element;
				}
			});

			const newTimeQueue = timeQueue.timeQueueList?.map((element) => {
				if (actives.includes(element.tabsessionId)) {
					return element;
				}
			});

			await storage.set("webhistory", {
				webhistory: newHistory?.filter(Boolean) ?? [],
			});
			await storage.set("urlQueueList", {
				urlQueueList: newUrlQueue?.filter(Boolean) ?? [],
			});
			await storage.set("timeQueueList", {
				timeQueueList: newTimeQueue?.filter(Boolean) ?? [],
			});
		});
	} catch (error) {
		console.log(error);
	}
};

const handler: PlasmoMessaging.MessageHandler = async (_req, res) => {
	try {
		const storage = new Storage({ area: "local" });

		const webhistoryObj = (await storage.get("webhistory")) as {
			webhistory?: WebHistory[];
		};
		const webhistory = webhistoryObj.webhistory;
		if (webhistory) {
			const toSaveFinally: { metadata: Record<string, unknown>; pageContent: unknown }[] = [];
			const newHistoryAfterCleanup: WebHistory[] = [];

			for (let i = 0; i < webhistory.length; i++) {
				const markdownFormat = webhistoryToLangChainDocument(
					webhistory[i].tabsessionId,
					webhistory[i].tabHistory
				);
				toSaveFinally.push(...markdownFormat);
				newHistoryAfterCleanup.push({
					tabsessionId: webhistory[i].tabsessionId,
					tabHistory: emptyArr,
				});
			}

			await storage.set("webhistory", { webhistory: newHistoryAfterCleanup });

			// Log first item to debug metadata structure
			if (toSaveFinally.length > 0) {
				console.log("First item metadata:", toSaveFinally[0].metadata);
			}

			// Create content array for documents in the format expected by the new API
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

			console.log("toSend", toSend);

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
				await clearMemory();
				res.send({
					message: "Save Job Started",
				});
			}
		}
	} catch (error) {
		console.log(error);
	}
};

export default handler;

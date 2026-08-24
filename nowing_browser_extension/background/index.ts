import { Storage } from "@plasmohq/storage";
import { getRenderedHtml, initQueues, initWebHistory } from "~utils/commons";
import type { WebHistory } from "~utils/interfaces";
import { CdpBridge } from "./cdp-bridge";

// Start listening for CDP commands from Nowing Backend
CdpBridge.getInstance().startListening();

chrome.runtime.onSuspend.addListener(() => {
	CdpBridge.getInstance().stopListening();
});

chrome.tabs.onActivated?.addListener(() => {
	CdpBridge.getInstance().startListening();
});

chrome.tabs.onCreated.addListener(async (tab: any) => {
	CdpBridge.getInstance().startListening();
	try {
		await initWebHistory(tab.id);
		await initQueues(tab.id);
	} catch (error) {
		console.log(error);
	}
});

chrome.tabs.onUpdated.addListener(async (tabId: number, changeInfo: any, tab: any) => {
	if (
		changeInfo.status === "complete" &&
		tab.url &&
		(tab.url.startsWith("http://") || tab.url.startsWith("https://"))
	) {
		const storage = new Storage({ area: "local" });
		await initWebHistory(tab.id);
		await initQueues(tab.id);

		const result = await chrome.scripting.executeScript({
			// @ts-ignore
			target: { tabId: tab.id },
			// @ts-ignore
			func: getRenderedHtml,
		});

		const toPushInTabHistory: any = result[0].result; // const { renderedHtml, title, url, entryTime } = result[0].result;

		const urlQueueListObj: any = await storage.get("urlQueueList");
		const timeQueueListObj: any = await storage.get("timeQueueList");

		urlQueueListObj.urlQueueList
			.find((data: WebHistory) => data.tabsessionId === tabId)
			.urlQueue.push(toPushInTabHistory.url);
		timeQueueListObj.timeQueueList
			.find((data: WebHistory) => data.tabsessionId === tabId)
			.timeQueue.push(toPushInTabHistory.entryTime);

		await storage.set("urlQueueList", {
			urlQueueList: urlQueueListObj.urlQueueList,
		});
		await storage.set("timeQueueList", {
			timeQueueList: timeQueueListObj.timeQueueList,
		});
	}
});

chrome.tabs.onReplaced.addListener(async (_addedTabId: number, removedTabId: number) => {
	const bridge = CdpBridge.getInstance();
	if (bridge.getActiveDebuggeeTabId() === removedTabId) {
		await bridge.detachActiveDebugger();
	}
});

chrome.tabs.onRemoved.addListener(async (tabId: number, _removeInfo: object) => {
	const bridge = CdpBridge.getInstance();
	if (bridge.getActiveDebuggeeTabId() === tabId) {
		await bridge.detachActiveDebugger();
	}
	const storage = new Storage({ area: "local" });
	const urlQueueListObj: any = await storage.get("urlQueueList");
	const timeQueueListObj: any = await storage.get("timeQueueList");
	if (urlQueueListObj.urlQueueList && timeQueueListObj.timeQueueList) {
		const urlQueueListToSave = urlQueueListObj.urlQueueList.map((element: WebHistory) => {
			if (element.tabsessionId !== tabId) {
				return element;
			}
		});
		const timeQueueListSave = timeQueueListObj.timeQueueList.map((element: WebHistory) => {
			if (element.tabsessionId !== tabId) {
				return element;
			}
		});
		await storage.set("urlQueueList", {
			urlQueueList: urlQueueListToSave.filter((item: any) => item),
		});
		await storage.set("timeQueueList", {
			timeQueueList: timeQueueListSave.filter((item: any) => item),
		});
	}
});

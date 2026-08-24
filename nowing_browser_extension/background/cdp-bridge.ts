import { Storage } from "@plasmohq/storage";
import { buildBackendUrl } from "~utils/backend-url";

const storage = new Storage({ area: "local" });

// Known challenge signatures. Runtime.evaluate returns true if any is present.
const CHALLENGE_SELECTORS = [
	".cf-turnstile",
	".recaptcha",
	'iframe[src*="recaptcha"]',
	'iframe[src*="challenges.cloudflare"]',
	'input[type="password"]',
	'input[autocomplete="one-time-code"]',
	'input[name*="otp" i]',
	'[id*="turnstile"]',
];

const CHALLENGE_DETECTION_JS = `
(function() {
  const selectors = ${JSON.stringify(CHALLENGE_SELECTORS)};
  for (const s of selectors) {
    if (document.querySelector(s)) return { challenge: s };
  }
  return null;
})()
`;

type CdpCommand = {
	action: string;
	mission_id: string;
	command_id: string;
	user_id?: string;
	url?: string;
	selector?: string;
	text?: string;
	direction?: "up" | "down";
	px?: number;
	format?: "png" | "jpeg";
};

// ponytail: cap screenshot base64 payload so it does not blow the CDP result pipeline.
// 2MB base64 ~= 1.5MB decoded; JPEG quality reduction is attempted before failing.
const MAX_SCREENSHOT_B64_CHARS = 2_000_000;

class CdpBridge {
	private static instance: CdpBridge | null = null;
	private fetchAbortController: AbortController | null = null;
	private activeDebuggeeTabId: number | null = null;
	private processing = false;
	private queued: CdpCommand[] = [];
	private reconnectDelay = 1000;
	private reconnectAttempts = 0;
	private readonly maxReconnectAttempts = 10;
	private readonly maxQueueSize = 20;
	private expectedUserId: string | null = null;

	public static getInstance(): CdpBridge {
		if (!CdpBridge.instance) {
			CdpBridge.instance = new CdpBridge();
			if (typeof chrome !== "undefined" && chrome.storage?.onChanged) {
				chrome.storage.onChanged.addListener((changes, area) => {
					if (area === "local" && (changes.token?.newValue || changes.backend_base_url?.newValue)) {
						CdpBridge.getInstance().startListening();
					}
				});
			}
		}
		return CdpBridge.instance;
	}

	public async startListening(): Promise<void> {
		if (this.fetchAbortController && !this.fetchAbortController.signal.aborted) {
			return;
		}

		const token = await this._requireToken();
		if (!token) {
			console.warn("CdpBridge: no auth token; cannot connect SSE");
			return;
		}

		const streamUrl = await buildBackendUrl("/api/v1/dsh/cdp/stream");

		try {
			this.fetchAbortController = new AbortController();
			const response = await fetch(streamUrl, {
				method: "GET",
				headers: {
					Accept: "text/event-stream",
					Authorization: `Bearer ${token}`,
				},
				signal: this.fetchAbortController.signal,
			});

			if (!response.ok) {
				if (response.status === 401 || response.status === 403) {
					console.warn("CdpBridge: auth rejected; stop reconnection");
					return;
				}
				throw new Error(`SSE connection failed: ${response.status}`);
			}

			const body = response.body;
			if (!body) {
				throw new Error("SSE response has no body");
			}

			const reader = body.getReader();
			const decoder = new TextDecoder();
			let buffer = "";

			// Reset backoff and attempt counter after a successful connection.
			this.reconnectDelay = 1000;
			this.reconnectAttempts = 0;

			while (true) {
				const { done, value } = await reader.read();
				if (done) {
					break;
				}
				buffer += decoder.decode(value, { stream: true });
				const lines = buffer.split("\n");
				buffer = lines.pop() ?? "";
				const events = this._parseSSE(lines);
				for (const event of events) {
					if (event.event === "cdp_command") {
						try {
							const cmd = JSON.parse(event.data) as CdpCommand;
							this._enqueueCommand(cmd);
						} catch (err) {
							console.error("CdpBridge: failed to parse command:", err);
						}
					}
				}
			}
		} catch (err: any) {
			if (err.name === "AbortError") {
				console.info("CdpBridge: SSE connection aborted");
				return;
			}
			console.error("CdpBridge: SSE error:", err);
		} finally {
			this.stopListening();
		}

		// Attempt to reconnect with capped exponential backoff and a max retry count.
		this.reconnectAttempts += 1;
		if (this.reconnectAttempts > this.maxReconnectAttempts) {
			console.error("CdpBridge: max reconnect attempts reached; stopping");
			return;
		}
		if (this.reconnectDelay < 30000) {
			this.reconnectDelay = Math.min(this.reconnectDelay * 2, 30000);
		}
		setTimeout(() => this.startListening(), this.reconnectDelay);
	}

	public stopListening(): void {
		if (this.fetchAbortController) {
			try {
				this.fetchAbortController.abort();
			} catch {
				// ignore
			}
			this.fetchAbortController = null;
		}
		this.detachDebugger();
	}

	private _parseSSE(lines: string[]): { event: string; data: string }[] {
		const events: { event: string; data: string }[] = [];
		let currentEvent = "";
		let currentData = "";

		for (const raw of lines) {
			const line = raw.trim();
			if (line.startsWith("event:")) {
				currentEvent = line.slice("event:".length).trim();
			} else if (line.startsWith("data:")) {
				currentData = line.slice("data:".length).trim();
			} else if (line === "" && currentEvent) {
				events.push({ event: currentEvent, data: currentData });
				currentEvent = "";
				currentData = "";
			}
		}

		return events;
	}

	private _enqueueCommand(cmd: CdpCommand): void {
		if (this.processing) {
			if (this.queued.length >= this.maxQueueSize) {
				console.warn("CdpBridge: command queue full; dropping oldest");
				this.queued.shift();
			}
			this.queued.push(cmd);
			return;
		}
		this.processing = true;
		this._processCommand(cmd).finally(() => {
			this.processing = false;
			const next = this.queued.shift();
			if (next) this._enqueueCommand(next);
		});
	}

	private async _processCommand(cmd: CdpCommand): Promise<void> {
		await this.handleCdpCommand(cmd);
	}

	private async _requireToken(): Promise<string | null> {
		try {
			const token = await storage.get("token");
			if (typeof token === "string" && token) return token;
		} catch {
			// fallback
		}
		if (typeof chrome !== "undefined" && chrome.storage?.local) {
			try {
				const res = await chrome.storage.local.get(["token", "apiKey"]);
				if (typeof res.token === "string" && res.token) return res.token;
				if (typeof res.apiKey === "string" && res.apiKey) return res.apiKey;
			} catch {
				// ignore
			}
		}
		return null;
	}

	private async _findMatchingTab(
		targetUrl: string | undefined
	): Promise<chrome.tabs.Tab | undefined> {
		const allTabs = await chrome.tabs.query({});
		if (targetUrl) {
			try {
				const targetHost = new URL(targetUrl).hostname;
				const match = allTabs.find((t) => t.url && new URL(t.url).hostname === targetHost);
				if (match?.id) return match;
			} catch {
				// invalid URL; fall through
			}
		}
		const active = allTabs.find((t) => t.active) || allTabs[0];
		if (active) return active;
		if (targetUrl) {
			return await chrome.tabs.create({ url: targetUrl, active: true });
		}
		return undefined;
	}

	private async _attachDebugger(tabId: number): Promise<void> {
		if (this.activeDebuggeeTabId === tabId) return;
		await this.detachDebugger();
		await chrome.debugger.attach({ tabId }, "1.3");
		this.activeDebuggeeTabId = tabId;
	}

	private async detachDebugger(): Promise<void> {
		if (this.activeDebuggeeTabId !== null) {
			try {
				await chrome.debugger.detach({ tabId: this.activeDebuggeeTabId });
			} catch (err) {
				console.warn("Debugger detach warning:", err);
			} finally {
				this.activeDebuggeeTabId = null;
			}
		}
	}

	public getActiveDebuggeeTabId(): number | null {
		return this.activeDebuggeeTabId;
	}

	public async detachActiveDebugger(): Promise<void> {
		await this.detachDebugger();
	}

	private async _sendCommand<T = any>(
		tabId: number,
		method: string,
		params?: Record<string, any>,
		timeoutMs = 15000
	): Promise<T> {
		return new Promise<T>((resolve, reject) => {
			const timer = setTimeout(() => {
				reject(new Error(`CDP command ${method} timed out`));
			}, timeoutMs);

			chrome.debugger.sendCommand({ tabId }, method, params, (result) => {
				clearTimeout(timer);
				if (chrome.runtime.lastError) {
					reject(new Error(chrome.runtime.lastError.message || `CDP command ${method} failed`));
				} else {
					resolve(result as T);
				}
			});
		});
	}

	private _waitForEvent(tabId: number, eventMethod: string, timeoutMs = 30000): Promise<any> {
		return new Promise((resolve, reject) => {
			const timer = setTimeout(() => {
				cleanup();
				reject(new Error(`Timeout waiting for ${eventMethod}`));
			}, timeoutMs);

			const handler = (debuggee: chrome.debugger.Debuggee, recvMethod: string, params?: any) => {
				if (debuggee.tabId !== tabId) return;
				if (recvMethod === eventMethod) {
					cleanup();
					resolve(params);
				}
			};

			const cleanup = () => {
				clearTimeout(timer);
				chrome.debugger.onEvent.removeListener(handler);
			};

			chrome.debugger.onEvent.addListener(handler);
		});
	}

	private async _detectChallenge(tabId: number): Promise<string | null> {
		try {
			await this._sendCommand(tabId, "Runtime.enable");
			const result: any = await this._sendCommand(
				tabId,
				"Runtime.evaluate",
				{
					expression: CHALLENGE_DETECTION_JS,
					returnByValue: true,
				},
				5000
			);
			const value = result?.result?.value;
			return value?.challenge ?? null;
		} catch (err) {
			console.warn("CdpBridge: challenge detection failed:", err);
			return null;
		}
	}

	private async _getDocumentInfo(tabId: number): Promise<{ url?: string; title?: string }> {
		try {
			const result: any = await this._sendCommand(
				tabId,
				"Runtime.evaluate",
				{
					expression: "JSON.stringify({ url: location.href, title: document.title })",
					returnByValue: true,
				},
				5000
			);
			return JSON.parse(result?.result?.value ?? "{}") as { url?: string; title?: string };
		} catch (err) {
			console.warn("CdpBridge: getDocumentInfo failed:", err);
			return {};
		}
	}

	private _extractJwtUserId(token: string): string | null {
		try {
			const parts = token.split(".");
			if (parts.length !== 3) return null;
			const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
			const json = atob(base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), "="));
			const payload = JSON.parse(json);
			return payload.sub || payload.user_id || payload.userId || null;
		} catch (err) {
			console.warn("CdpBridge: could not decode token user_id:", err);
			return null;
		}
	}

	private _validateCommandOwnership(cmd: CdpCommand, token: string | null): boolean {
		if (!cmd.user_id || !token) return true;
		if (this.expectedUserId === null) {
			this.expectedUserId = this._extractJwtUserId(token);
		}
		if (this.expectedUserId && cmd.user_id !== this.expectedUserId) {
			console.warn("CdpBridge: command user_id mismatch; ignoring command", cmd.mission_id);
			return false;
		}
		return true;
	}

	private async _captureCappedScreenshot(
		tabId: number,
		format: "png" | "jpeg"
	): Promise<{ data: string; format: string }> {
		const attempts: { format: "png" | "jpeg"; quality?: number }[] = [
			{ format },
			{ format: "jpeg", quality: 60 },
			{ format: "jpeg", quality: 30 },
		];

		let data = "";
		for (const opts of attempts) {
			const cap: any = await this._sendCommand(tabId, "Page.captureScreenshot", opts);
			data = cap?.data ?? "";
			if (data.length <= MAX_SCREENSHOT_B64_CHARS) {
				return { data, format: opts.format };
			}
			console.warn(
				`CdpBridge: screenshot too large (${data.length} chars) with`,
				opts,
				"; retrying with lower quality"
			);
		}

		throw new Error(`Screenshot exceeded size cap (${data.length} base64 chars)`);
	}

	private async handleCdpCommand(cmd: CdpCommand): Promise<void> {
		const { action, mission_id, command_id, url, user_id } = cmd;

		if (!action || !mission_id || !command_id) {
			console.error("CdpBridge: invalid CDP command", cmd);
			return;
		}

		// Tab/user ownership: verify the command is for the authenticated user and
		// that we operate on the tab matching the requested URL.
		const token = await this._requireToken();
		if (!this._validateCommandOwnership(cmd, token)) {
			return;
		}

		const targetUrl = action === "navigate" ? url : cmd.url;
		const targetTab = await this._findMatchingTab(targetUrl);
		if (!targetTab?.id) {
			await this.sendResult(
				mission_id,
				null,
				"No active tab available for CDP takeover",
				command_id
			);
			return;
		}

		const tabId = targetTab.id;

		// Validate URL scheme to avoid javascript:/data: trickery.
		const target = action === "navigate" ? targetUrl : targetTab.url;
		if (target) {
			try {
				const parsed = new URL(target);
				if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
					await this.sendResult(
						mission_id,
						null,
						`Unsupported URL scheme: ${parsed.protocol}`,
						command_id
					);
					return;
				}
			} catch {
				await this.sendResult(mission_id, null, "Invalid URL", command_id);
				return;
			}
		}

		try {
			await this._attachDebugger(tabId);

			let resultPayload: Record<string, any> = { success: true };
			let skipAutoChallenge = false;

			switch (action) {
				case "navigate": {
					if (!targetUrl) {
						await this.sendResult(mission_id, null, "navigate requires url", command_id);
						return;
					}
					try {
						await chrome.tabs.update(tabId, { url: targetUrl, active: true });
						if (targetTab.windowId) {
							await chrome.windows.update(targetTab.windowId, { focused: true });
						}
					} catch (e) {
						console.warn("tab update error:", e);
					}
					await this._sendCommand(tabId, "Page.enable").catch(() => {});
					const loadPromise = this._waitForEvent(tabId, "Page.loadEventFired", 15000).catch(
						() => {}
					);
					await this._sendCommand(tabId, "Page.navigate", { url: targetUrl }).catch(() => {});
					await loadPromise;
					await new Promise((r) => setTimeout(r, 1000));
					const info = await this._getDocumentInfo(tabId);
					resultPayload = {
						navigatedUrl: info.url ?? targetUrl,
						title: info.title,
						tabId,
					};
					break;
				}

				case "click": {
					if (!cmd.selector) {
						throw new Error("click requires selector");
					}
					await this._sendCommand(tabId, "DOM.enable");
					const doc: any = await this._sendCommand(tabId, "DOM.getDocument");
					const node: any = await this._sendCommand(tabId, "DOM.querySelector", {
						nodeId: doc.root.nodeId,
						selector: cmd.selector,
					});
					if (!node?.nodeId) {
						throw new Error(`Selector not found: ${cmd.selector}`);
					}
					const box: any = await this._sendCommand(tabId, "DOM.getBoxModel", {
						nodeId: node.nodeId,
					});
					const [x, y] = this._boxCenter(box.model.content);
					await this._sendCommand(tabId, "Input.dispatchMouseEvent", {
						type: "mousePressed",
						x,
						y,
						button: "left",
						clickCount: 1,
					});
					await this._sendCommand(tabId, "Input.dispatchMouseEvent", {
						type: "mouseReleased",
						x,
						y,
						button: "left",
						clickCount: 1,
					});
					resultPayload = { clickedSelector: cmd.selector, tabId };
					break;
				}

				case "fill": {
					if (!cmd.selector || cmd.text === undefined) {
						throw new Error("fill requires selector and text");
					}
					await this._sendCommand(tabId, "DOM.enable");
					const doc: any = await this._sendCommand(tabId, "DOM.getDocument");
					const node: any = await this._sendCommand(tabId, "DOM.querySelector", {
						nodeId: doc.root.nodeId,
						selector: cmd.selector,
					});
					if (!node?.nodeId) {
						throw new Error(`Selector not found: ${cmd.selector}`);
					}
					await this._sendCommand(tabId, "DOM.focus", { nodeId: node.nodeId });
					await this._sendCommand(tabId, "Input.insertText", { text: cmd.text });
					resultPayload = { filledSelector: cmd.selector, tabId };
					break;
				}

				case "scroll": {
					const direction = cmd.direction ?? "down";
					const px = cmd.px ?? 500;
					const deltaY = direction === "up" ? -px : px;
					await this._sendCommand(tabId, "Runtime.enable").catch(() => {});
					await this._sendCommand(tabId, "Runtime.evaluate", {
						expression: `window.scrollBy({ top: ${deltaY}, behavior: 'smooth' });`,
					}).catch(() => {});
					await this._sendCommand(tabId, "Input.dispatchMouseEvent", {
						type: "mouseWheel",
						x: 200,
						y: 200,
						deltaX: 0,
						deltaY,
					}).catch(() => {});
					resultPayload = { scrolled: direction, px, tabId };
					break;
				}

				case "extract": {
					if (!cmd.selector) {
						throw new Error("extract requires selector");
					}
					const expression = `
            (function() {
              const el = document.querySelector(${JSON.stringify(cmd.selector)});
              if (!el) return null;
              return { text: el.innerText, html: el.innerHTML };
            })()
          `;
					const evalResult: any = await this._sendCommand(tabId, "Runtime.evaluate", {
						expression,
						returnByValue: true,
					});
					const value = evalResult?.result?.value;
					resultPayload = {
						selector: cmd.selector,
						text: typeof value?.text === "string" ? value.text.slice(0, 50000) : "",
						html: typeof value?.html === "string" ? value.html.slice(0, 50000) : "",
						tabId,
					};
					break;
				}

				case "take_screenshot": {
					const requestedFormat = cmd.format ?? "png";
					const { data, format } = await this._captureCappedScreenshot(tabId, requestedFormat);
					resultPayload = {
						data,
						format,
						tabId,
					};
					break;
				}

				case "detect_challenge": {
					skipAutoChallenge = true;
					const challenge = await this._detectChallenge(tabId);
					resultPayload = { challenge, tabId };
					break;
				}

				default:
					await this.sendResult(mission_id, null, `Unsupported action: ${action}`, command_id);
					return;
			}

			// After navigation or interaction, check whether a human challenge is present.
			if (!skipAutoChallenge) {
				const challenge = await this._detectChallenge(tabId);
				if (challenge) {
					// Store the active mission so the popup can offer a Release Control button.
					await storage.set("activeMissionId", mission_id);
					await this.sendResult(mission_id, null, challenge, command_id, true, challenge);
					return;
				}
			}

			await this.sendResult(mission_id, resultPayload, null, command_id);
		} catch (err: any) {
			console.error("CDP execution error:", err);
			await this.sendResult(mission_id, null, err.message || String(err), command_id);
		} finally {
			await this.detachDebugger();
		}
	}

	private _boxCenter(content: number[]): [number, number] {
		// content from DOM.getBoxModel is [x1, y1, x2, y2, ...]
		if (!content || content.length < 8) return [0, 0];
		const [x1, y1, , , x2, y2] = content;
		return [x1 + (x2 - x1) / 2, y1 + (y2 - y1) / 2];
	}

	private async sendResult(
		missionId: string,
		result: Record<string, any> | null,
		error: string | null,
		commandId: string,
		requiresHuman = false,
		challenge?: string
	): Promise<void> {
		const token = await this._requireToken();
		if (!token) {
			console.error("CdpBridge: cannot send result without auth token");
			return;
		}

		const resultUrl = await buildBackendUrl("/api/v1/dsh/cdp/result");

		const body = {
			mission_id: missionId,
			result: result ? { ...result, command_id: commandId } : null,
			error,
			requires_human: requiresHuman,
			challenge,
		};

		const isRetryableStatus = (status: number) => status >= 500 || status === 429;

		for (let i = 0; i < 3; i++) {
			try {
				const res = await fetch(resultUrl, {
					method: "POST",
					headers: {
						"Content-Type": "application/json",
						Authorization: `Bearer ${token}`,
					},
					body: JSON.stringify(body),
				});

				if (res.ok) {
					if (requiresHuman) {
						console.info("CdpBridge: human takeover requested for mission", missionId);
					}
					return;
				}

				if (res.status === 401 || res.status === 403) {
					console.warn("CdpBridge: auth rejected when sending result");
					return;
				}

				if (!isRetryableStatus(res.status)) {
					console.error(`CdpBridge: result POST failed (${res.status}); not retryable`);
					return;
				}

				console.warn(`CdpBridge: result POST failed (${res.status}); retry ${i + 1}/3`);
			} catch (err) {
				console.warn(`CdpBridge: result POST network error; retry ${i + 1}/3`, err);
			}

			if (i < 2) {
				await this._sleep(1000 * (i + 1));
			}
		}

		console.error("CdpBridge: failed to post CDP result after retries");
	}

	private _sleep(ms: number): Promise<void> {
		return new Promise((resolve) => setTimeout(resolve, ms));
	}
}

export { CdpBridge };

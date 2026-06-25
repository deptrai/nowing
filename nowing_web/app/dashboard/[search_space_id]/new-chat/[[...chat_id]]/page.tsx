"use client";

import {
	type AppendMessage,
	AssistantRuntimeProvider,
	type ThreadMessageLike,
	useExternalStoreRuntime,
} from "@assistant-ui/react";
import { useQueryClient } from "@tanstack/react-query";
import { useAtomValue, useSetAtom } from "jotai";
import dynamic from "next/dynamic";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { z } from "zod";
import { disabledToolsAtom } from "@/atoms/agent-tools/agent-tools.atoms";
import { selectedSystemModelIdAtom } from "@/atoms/new-llm-config/system-models-query.atoms";
import { isCloud } from "@/lib/env-config";
import {
	clearTargetCommentIdAtom,
	currentThreadAtom,
	setTargetCommentIdAtom,
} from "@/atoms/chat/current-thread.atom";
import {
	type MentionedDocumentInfo,
	mentionedDocumentIdsAtom,
	mentionedDocumentsAtom,
	messageDocumentsMapAtom,
	sidebarSelectedDocumentsAtom,
} from "@/atoms/chat/mentioned-documents.atom";
import {
	clearPlanOwnerRegistry,
	// extractWriteTodosFromContent,
} from "@/atoms/chat/plan-state.atom";
import { closeReportPanelAtom } from "@/atoms/chat/report-panel.atom";
import { type AgentCreatedDocument, agentCreatedDocumentsAtom } from "@/atoms/documents/ui.atoms";
import { closeEditorPanelAtom } from "@/atoms/editor/editor-panel.atom";
import { membersAtom } from "@/atoms/members/members-query.atoms";
import { removeChatTabAtom, updateChatTabTitleAtom } from "@/atoms/tabs/tabs.atom";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { ThinkingStepsDataUI } from "@/components/assistant-ui/thinking-steps";
import { Thread } from "@/components/assistant-ui/thread";
import { ChatHeader } from "@/components/new-chat/chat-header";
// Crypto Tool UI Components - Conversational Crypto Advisor
import {
	ActionConfirmationToolUI,
	AlertConfigurationToolUI,
	HolderAnalysisToolUI,
	LiveTokenDataToolUI,
	// Real-time crypto tools (Hybrid approach: RAG + Real-time)
	LiveTokenPriceToolUI,
	MarketOverviewToolUI,
	PortfolioDisplayToolUI,
	ProactiveAlertToolUI,
	TokenAnalysisToolUI,
	TrendingTokensToolUI,
	UserProfileToolUI,
	WatchlistDisplayToolUI,
	WhaleActivityToolUI,
} from "@/components/tool-ui/crypto";
import type { ThinkingStep } from "@/components/tool-ui/deepagent-thinking";
import { DisplayImageToolUI } from "@/components/tool-ui/display-image";
import { GeneratePodcastToolUI } from "@/components/tool-ui/generate-podcast";
import { LinkPreviewToolUI } from "@/components/tool-ui/link-preview";
import { ScrapeWebpageToolUI } from "@/components/tool-ui/scrape-webpage";
import { RecallMemoryToolUI, SaveMemoryToolUI } from "@/components/tool-ui/user-memory";
import { Spinner } from "@/components/ui/spinner";
import { useChatSessionStateSync } from "@/hooks/use-chat-session-state";
import { useMessagesSync } from "@/hooks/use-messages-sync";
import { documentsApiService } from "@/lib/apis/documents-api.service";
import { getBearerToken } from "@/lib/auth-utils";
import { convertToThreadMessage } from "@/lib/chat/message-utils";
import {
	isPodcastGenerating,
	looksLikePodcastRequest,
	setActivePodcastTaskId,
} from "@/lib/chat/podcast-state";
import {
	addToolCall,
	appendText,
	buildContentForPersistence,
	buildContentForUI,
	type ContentPartsState,
	FrameBatchedUpdater,
	type SmartMoneyFlowData,
	type ThinkingStepData,
	updateThinkingSteps,
	updateToolCall,
} from "@/lib/chat/streaming-state";
import {
	appendMessage,
	createThread,
	getRegenerateUrl,
	getThreadFull,
	getThreadMessages,
	type ThreadRecord,
} from "@/lib/chat/thread-persistence";
import { NotFoundError, QuotaExceededError, StreamMaxRetriesError } from "@/lib/error";
import {
	trackChatCreated,
	trackChatError,
	trackChatMessageSent,
	trackChatResponseReceived,
	trackOrchestraAgentDone,
	trackOrchestraAgentFail,
	trackOrchestraCompleted,
	trackOrchestraCancelled,
	trackOrchestraSpawn,
} from "@/lib/posthog/events";
import { applyOrchestraEvent, orchestraStateAtom } from "@/atoms/chat/orchestra.atom";
import {
	activeRunsAtom,
	abandonedSessionIdsAtom,
	upsertRun,
	removeRun,
	resumeRunBySessionAtom,
} from "@/atoms/chat/active-runs.atom";
import {
	startRun,
	getActiveRuns,
	streamRun,
	resumeRun,
	type ChatRun,
} from "@/lib/apis/chat-runs-api.service";
import Loading from "../loading";

/**
 * Handle every orchestra-* and data-orchestra-* SSE event in one place.
 * Returns true when the event was an orchestra event (so the caller can
 * `break` from its outer switch). Returns false otherwise — the caller
 * falls through to other event types.
 *
 * Adding a new orchestra event type? Add it here and its case will be
 * picked up by all 3 SSE-loop call sites automatically.
 */
function handleOrchestraEvent(
	parsed: { type: string; data?: Record<string, unknown> },
	setOrchestraState: (fn: (prev: unknown) => unknown) => void
): boolean {
	const t = parsed.type;
	if (
		t !== "orchestra-spawn" &&
		t !== "orchestra-update" &&
		t !== "orchestra-done" &&
		t !== "orchestra-fail" &&
		t !== "orchestra-cancel" &&
		t !== "orchestra-complete" &&
		t !== "data-orchestra-narration" &&
		t !== "data-orchestra-source-fetched" &&
		t !== "data-orchestra-fact-captured" &&
		t !== "data-orchestra-model-attribution" &&
		t !== "data-orchestra-rate-gate-wait" &&
		t !== "data-orchestra-llm-call" &&
		t !== "data-agent-result"
	) {
		return false;
	}
	// V2-P12: guard the reducer so a malformed event from a future BE version
	// doesn't kill the SSE loop for the entire chat session.
	try {
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		setOrchestraState((prev: any) => applyOrchestraEvent(prev, parsed as any));
	} catch (err) {
		console.warn("orchestra reducer failed for event", t, err);
	}
	const data = (parsed.data ?? {}) as Record<string, unknown>;
	switch (t) {
		case "orchestra-spawn":
			trackOrchestraSpawn({
				sessionId: String(data.sessionId ?? ""),
				agentId: String(data.agentId ?? ""),
				agentName: String(data.agentName ?? ""),
			});
			break;
		case "orchestra-done":
			trackOrchestraAgentDone({
				sessionId: String(data.sessionId ?? ""),
				agentId: String(data.agentId ?? ""),
			});
			break;
		case "orchestra-fail":
			trackOrchestraAgentFail({
				sessionId: String(data.sessionId ?? ""),
				agentId: String(data.agentId ?? ""),
				errorCode: String(data.errorCode ?? ""),
			});
			break;
		case "orchestra-cancel":
			trackOrchestraCancelled({
				sessionId: String(data.sessionId ?? ""),
				agentId: String(data.agentId ?? ""),
			});
			break;
		case "orchestra-complete":
			trackOrchestraCompleted({
				sessionId: String(data.sessionId ?? ""),
				agentIds: (data.agentIds as string[]) ?? [],
				citationCount: Number(data.citationCount ?? 0),
			});
			break;
	}
	return true;
}

const MobileEditorPanel = dynamic(
	() =>
		import("@/components/editor-panel/editor-panel").then((m) => ({
			default: m.MobileEditorPanel,
		})),
	{ ssr: false }
);
const MobileHitlEditPanel = dynamic(
	() =>
		import("@/components/hitl-edit-panel/hitl-edit-panel").then((m) => ({
			default: m.MobileHitlEditPanel,
		})),
	{ ssr: false }
);
const MobileReportPanel = dynamic(
	() =>
		import("@/components/report-panel/report-panel").then((m) => ({
			default: m.MobileReportPanel,
		})),
	{ ssr: false }
);

/**
 * After a tool produces output, mark any previously-decided interrupt tool
 * calls as completed so the ApprovalCard can transition from shimmer to done.
 */
/**
 * Validate raw SSE smart-money-flow payload and coerce into SmartMoneyFlowData.
 * Returns null when payload is malformed (missing nodes/links) so the caller
 * can short-circuit instead of polluting state with partial data.
 */
function parseSmartMoneyFlow(raw: unknown): SmartMoneyFlowData | null {
	if (typeof raw !== "object" || raw === null) return null;
	const data = raw as {
		nodes?: unknown;
		links?: unknown;
		net_flow_amount?: unknown;
		currency?: unknown;
		source_domain?: unknown;
		cohort_summary?: unknown;
	};
	if (!Array.isArray(data.nodes) || !Array.isArray(data.links)) return null;
	return {
		nodes: data.nodes as SmartMoneyFlowData["nodes"],
		links: data.links as SmartMoneyFlowData["links"],
		net_flow_amount: Number(data.net_flow_amount ?? 0) || 0,
		currency: typeof data.currency === "string" ? data.currency : "USD",
		source_domain: typeof data.source_domain === "string" ? data.source_domain : undefined,
		cohort_summary:
			data.cohort_summary &&
			typeof data.cohort_summary === "object" &&
			!Array.isArray(data.cohort_summary)
				? (data.cohort_summary as SmartMoneyFlowData["cohort_summary"])
				: undefined,
	};
}

/**
 * Apply a smart-money-flow SSE event to both contentPartsState (for DB persistence)
 * and React message metadata (for live render). Used by all 3 SSE handlers
 * (onNew, handleResume, regenerate).
 */
function applySmartMoneyFlowUpdate(
	flowData: SmartMoneyFlowData,
	assistantMsgId: string,
	contentPartsState: ContentPartsState,
	setMessages: (updater: (prev: ThreadMessageLike[]) => ThreadMessageLike[]) => void
): void {
	contentPartsState.contentParts.push({
		type: "data-smart-money-flow",
		data: flowData,
	});
	setMessages((prev) =>
		prev.map((m) =>
			m.id === assistantMsgId
				? {
						...m,
						metadata: {
							...(m.metadata as Record<string, unknown> | undefined),
							custom: {
								...((m.metadata as { custom?: Record<string, unknown> })?.custom ?? {}),
								smart_money_flow: flowData,
							},
						},
					}
				: m
		)
	);
}

function markInterruptsCompleted(contentParts: Array<{ type: string; result?: unknown }>): void {
	for (const part of contentParts) {
		if (
			part.type === "tool-call" &&
			typeof part.result === "object" &&
			part.result !== null &&
			(part.result as Record<string, unknown>).__interrupt__ === true &&
			(part.result as Record<string, unknown>).__decided__ &&
			!(part.result as Record<string, unknown>).__completed__
		) {
			part.result = { ...(part.result as Record<string, unknown>), __completed__: true };
		}
	}
}

/**
 * Zod schema for mentioned document info (for type-safe parsing)
 */
const MentionedDocumentInfoSchema = z.object({
	id: z.number(),
	title: z.string(),
	document_type: z.string(),
});

const MentionedDocumentsPartSchema = z.object({
	type: z.literal("mentioned-documents"),
	documents: z.array(MentionedDocumentInfoSchema),
});

/**
 * Extract mentioned documents from message content (type-safe with Zod)
 */
function extractMentionedDocuments(content: unknown): MentionedDocumentInfo[] {
	if (!Array.isArray(content)) return [];

	for (const part of content) {
		const result = MentionedDocumentsPartSchema.safeParse(part);
		if (result.success) {
			return result.data.documents;
		}
	}

	return [];
}

/**
 * Tools that should render custom UI in the chat.
 */
const TOOLS_WITH_UI = new Set([
	"web_search",
	"generate_podcast",
	"generate_report",
	"generate_video_presentation",
	"display_image",
	"generate_image",
	"delete_notion_page",
	"create_notion_page",
	"update_notion_page",
	"create_linear_issue",
	"update_linear_issue",
	"delete_linear_issue",
	"create_google_drive_file",
	"delete_google_drive_file",
	"create_onedrive_file",
	"delete_onedrive_file",
	"create_dropbox_file",
	"delete_dropbox_file",
	"create_calendar_event",
	"update_calendar_event",
	"delete_calendar_event",
	"create_gmail_draft",
	"update_gmail_draft",
	"send_gmail_email",
	"trash_gmail_email",
	"create_jira_issue",
	"update_jira_issue",
	"delete_jira_issue",
	"create_confluence_page",
	"update_confluence_page",
	"delete_confluence_page",
	"execute",
	// "write_todos", // Disabled for now
]);

export default function NewChatPage() {
	const params = useParams();
	const queryClient = useQueryClient();
	const [isInitializing, setIsInitializing] = useState(true);
	const [threadId, setThreadId] = useState<number | null>(null);
	const [currentThread, setCurrentThread] = useState<ThreadRecord | null>(null);
	const [messages, setMessages] = useState<ThreadMessageLike[]>([]);
	const [isRunning, setIsRunning] = useState(false);
	const abortControllerRef = useRef<AbortController | null>(null);
	const [pendingInterrupt, setPendingInterrupt] = useState<{
		threadId: number;
		assistantMsgId: string;
		interruptData: Record<string, unknown>;
	} | null>(null);

	// Get disabled tools from the tool toggle UI
	const disabledTools = useAtomValue(disabledToolsAtom);

	// Cloud mode: selected system model ID (null = backend default)
	const selectedSystemModelId = useAtomValue(selectedSystemModelIdAtom);

	// Get mentioned document IDs from the composer (derived from @ mentions + sidebar selections)
	const mentionedDocumentIds = useAtomValue(mentionedDocumentIdsAtom);
	const mentionedDocuments = useAtomValue(mentionedDocumentsAtom);
	const sidebarDocuments = useAtomValue(sidebarSelectedDocumentsAtom);
	const setMentionedDocuments = useSetAtom(mentionedDocumentsAtom);
	const setSidebarDocuments = useSetAtom(sidebarSelectedDocumentsAtom);
	const setMessageDocumentsMap = useSetAtom(messageDocumentsMapAtom);
	const setCurrentThreadState = useSetAtom(currentThreadAtom);
	const setTargetCommentId = useSetAtom(setTargetCommentIdAtom);
	const clearTargetCommentId = useSetAtom(clearTargetCommentIdAtom);
	const closeReportPanel = useSetAtom(closeReportPanelAtom);
	const closeEditorPanel = useSetAtom(closeEditorPanelAtom);
	const updateChatTabTitle = useSetAtom(updateChatTabTitleAtom);
	const removeChatTab = useSetAtom(removeChatTabAtom);
	const setAgentCreatedDocuments = useSetAtom(agentCreatedDocumentsAtom);
	const setOrchestraState = useSetAtom(orchestraStateAtom);
	const setActiveRuns = useSetAtom(activeRunsAtom);
	const activeRunsValue = useAtomValue(activeRunsAtom);
	const activeRunsRef = useRef(activeRunsValue);
	activeRunsRef.current = activeRunsValue;
	const setResumeRunBySession = useSetAtom(resumeRunBySessionAtom);
	const setAbandonedSessionIds = useSetAtom(abandonedSessionIdsAtom);
	const [abandonedRuns, setAbandonedRuns] = useState<ChatRun[]>([]);
	const attachToRunRef = useRef<((run: ChatRun) => Promise<void>) | null>(null);
	const abandonedRunsRef = useRef(abandonedRuns);
	abandonedRunsRef.current = abandonedRuns;
	// 11-1 AC#6: Connection-lost banner — surfaces stream max-retries / unrecoverable disconnect
	const [streamConnectionLost, setStreamConnectionLost] = useState<{ runId: string } | null>(null);

	// Get current user for author info in shared chats
	const { data: currentUser } = useAtomValue(currentUserAtom);

	// Live collaboration: sync session state and messages via Zero
	useChatSessionStateSync(threadId);
	const { data: membersData } = useAtomValue(membersAtom);

	const handleSyncedMessagesUpdate = useCallback(
		(
			syncedMessages: {
				id: number;
				thread_id: number;
				role: string;
				content: unknown;
				author_id: string | null;
				created_at: string;
			}[]
		) => {
			if (isRunning) {
				return;
			}

			setMessages((prev) => {
				if (syncedMessages.length < prev.length) {
					return prev;
				}

				const memberById = new Map(membersData?.map((m) => [m.user_id, m]) ?? []);
				const prevById = new Map(prev.map((m) => [m.id, m]));

				return syncedMessages.map((msg) => {
					const member = msg.author_id ? (memberById.get(msg.author_id) ?? null) : null;

					// Preserve existing author info if member lookup fails (e.g., cloned chats)
					const existingMsg = prevById.get(`msg-${msg.id}`);
					const existingAuthor = existingMsg?.metadata?.custom?.author as
						| { displayName?: string | null; avatarUrl?: string | null }
						| undefined;

					return convertToThreadMessage({
						id: msg.id,
						thread_id: msg.thread_id,
						role: msg.role.toLowerCase() as "user" | "assistant" | "system",
						content: msg.content,
						author_id: msg.author_id,
						created_at: msg.created_at,
						author_display_name: member?.user_display_name ?? existingAuthor?.displayName ?? null,
						author_avatar_url: member?.user_avatar_url ?? existingAuthor?.avatarUrl ?? null,
					});
				});
			});
		},
		[isRunning, membersData]
	);

	useMessagesSync(threadId, handleSyncedMessagesUpdate);

	// Extract search_space_id from URL params
	const searchSpaceId = useMemo(() => {
		const id = params.search_space_id;
		const parsed = typeof id === "string" ? Number.parseInt(id, 10) : 0;
		return Number.isNaN(parsed) ? 0 : parsed;
	}, [params.search_space_id]);

	// Extract chat_id from URL params
	const urlChatId = useMemo(() => {
		const id = params.chat_id;
		let parsed = 0;
		if (Array.isArray(id) && id.length > 0) {
			parsed = Number.parseInt(id[0], 10);
		} else if (typeof id === "string") {
			parsed = Number.parseInt(id, 10);
		}
		return Number.isNaN(parsed) ? 0 : parsed;
	}, [params.chat_id]);

	// Initialize thread and load messages
	// For new chats (no urlChatId), we use lazy creation - thread is created on first message
	const initializeThread = useCallback(async () => {
		setIsInitializing(true);

		// Reset all state when switching between chats/search spaces to prevent stale data
		setMessages([]);
		setThreadId(null);
		setCurrentThread(null);
		setMentionedDocuments([]);
		setSidebarDocuments([]);
		setMessageDocumentsMap({});
		clearPlanOwnerRegistry();
		closeReportPanel();
		closeEditorPanel();

		try {
			if (urlChatId > 0) {
				// Thread exists - load thread data and messages
				setThreadId(urlChatId);

				// Load thread data (for visibility info) and messages in parallel
				const [threadData, messagesResponse] = await Promise.all([
					getThreadFull(urlChatId),
					getThreadMessages(urlChatId),
				]);

				setCurrentThread(threadData);

				if (messagesResponse.messages && messagesResponse.messages.length > 0) {
					const loadedMessages = messagesResponse.messages.map(convertToThreadMessage);
					setMessages(loadedMessages);

					const restoredDocsMap: Record<string, MentionedDocumentInfo[]> = {};
					for (const msg of messagesResponse.messages) {
						if (msg.role === "user") {
							const docs = extractMentionedDocuments(msg.content);
							if (docs.length > 0) {
								restoredDocsMap[`msg-${msg.id}`] = docs;
							}
						}
					}
					if (Object.keys(restoredDocsMap).length > 0) {
						setMessageDocumentsMap(restoredDocsMap);
					}
				}
			}
			// For new chats (urlChatId === 0), don't create thread yet
			// Thread will be created lazily when user sends first message
			// This improves UX (instant load) and avoids orphan threads
		} catch (error) {
			console.error("[NewChatPage] Failed to initialize thread:", error);
			if (urlChatId > 0 && error instanceof NotFoundError) {
				removeChatTab(urlChatId);
				if (typeof window !== "undefined") {
					window.history.replaceState(null, "", `/dashboard/${searchSpaceId}/new-chat`);
				}
				toast.error("This chat was deleted.");
				return;
			}
			// Keep threadId as null - don't use Date.now() as it creates an invalid ID
			// that will cause 404 errors on subsequent API calls
			setThreadId(null);
			setCurrentThread(null);
			toast.error("Failed to load chat. Please try again.");
		} finally {
			setIsInitializing(false);
		}
	}, [
		urlChatId,
		setMessageDocumentsMap,
		setMentionedDocuments,
		setSidebarDocuments,
		closeReportPanel,
		closeEditorPanel,
		removeChatTab,
		searchSpaceId,
	]);

	// Initialize on mount, and re-init when switching search spaces (even if urlChatId is the same)
	useEffect(() => {
		initializeThread();
	}, [initializeThread]);

	// Prefetch document titles for @ mention picker
	// Runs when user lands on page so data is ready when they type @
	useEffect(() => {
		if (!searchSpaceId) return;

		const prefetchParams = {
			search_space_id: searchSpaceId,
			page: 0,
			page_size: 20,
		};

		queryClient.prefetchQuery({
			queryKey: ["document-titles", prefetchParams],
			queryFn: () => documentsApiService.searchDocumentTitles({ queryParams: prefetchParams }),
			staleTime: 60 * 1000,
		});

		queryClient.prefetchQuery({
			queryKey: ["nowing-docs-mention", "", false],
			queryFn: () =>
				documentsApiService.getNowingDocs({
					queryParams: { page: 0, page_size: 20 },
				}),
			staleTime: 3 * 60 * 1000,
		});
	}, [searchSpaceId, queryClient]);

	// Handle scroll to comment from URL query params (e.g., from inbox item click)
	// Read from window.location.search inside the effect instead of subscribing via
	// useSearchParams() — avoids re-rendering this heavy component tree on every
	// unrelated query-string change. (Vercel Best Practice: rerender-defer-reads 5.2)
	useEffect(() => {
		const readAndApplyCommentId = () => {
			const params = new URLSearchParams(window.location.search);
			const raw = params.get("commentId");
			if (raw && !isInitializing) {
				const commentId = Number.parseInt(raw, 10);
				if (!Number.isNaN(commentId)) {
					setTargetCommentId(commentId);
				}
			}
		};

		readAndApplyCommentId();

		// Also respond to SPA navigations (back/forward) that change the query string
		window.addEventListener("popstate", readAndApplyCommentId);

		// Cleanup on unmount or when navigating away
		return () => {
			window.removeEventListener("popstate", readAndApplyCommentId);
			clearTargetCommentId();
		};
	}, [isInitializing, setTargetCommentId, clearTargetCommentId]);

	// Sync current thread state to atom
	useEffect(() => {
		setCurrentThreadState((prev) => ({
			...prev,
			id: currentThread?.id ?? null,
			visibility: currentThread?.visibility ?? null,
			hasComments: currentThread?.has_comments ?? false,
		}));
	}, [currentThread, setCurrentThreadState]);

	// Cleanup on unmount - abort any in-flight requests
	useEffect(() => {
		return () => {
			if (abortControllerRef.current) {
				abortControllerRef.current.abort();
				abortControllerRef.current = null;
			}
		};
	}, []);

	// On thread load: fetch active runs and re-attach SSE for any running ones (9-UX-1b)
	useEffect(() => {
		if (!threadId) return;
		const abortControllers: AbortController[] = [];
		const readers: Array<ReadableStreamDefaultReader<Uint8Array>> = [];
		// M7: track per-run lastSeq so reconnects don't replay from 0
		const lastSeqByRun = new Map<string, number>();

		const attachToRun = async (run: ChatRun) => {
			const ac = new AbortController();
			abortControllers.push(ac);
			try {
				const resumeFrom = lastSeqByRun.get(run.id) ?? -1;
				// Add placeholder assistant message so OrchestraStrip has a mounting point
				const placeholderMsgId = `msg-assistant-resume-${run.id}`;
				setMessages((prev) => {
					if (prev.some((m) => m.id === placeholderMsgId)) return prev;
					return [
						...prev,
						{
							id: placeholderMsgId,
							role: "assistant" as const,
							content: [{ type: "text" as const, text: "" }],
							createdAt: new Date(),
						},
					];
				});

				for await (const parsed of streamRun(threadId, run.id, resumeFrom, ac.signal)) {
					// M7: update lastSeq for next reconnect attempt
					// biome-ignore lint/suspicious/noExplicitAny: SSEEvent might have seq
					const anyParsed = parsed as any;
					if (anyParsed.seq != null && typeof anyParsed.seq === "number") {
						lastSeqByRun.set(run.id, anyParsed.seq);
					}

					// T22: handle _marker sentinels (replace old event: run-replay-end)
					if (anyParsed && anyParsed._marker) {
						if (anyParsed._marker === "replay-start") {
							// entering replay — future: suppress animation
						} else if (anyParsed._marker === "replay-end") {
							if (anyParsed.status !== "live") {
								setActiveRuns((prev) => removeRun(prev, run.id, threadId));
								if (anyParsed.status === "abandoned") {
									// keep in abandonedRuns / abandonedSessionIds for Resume UI
									setAbandonedSessionIds((prev) => new Set([...prev, run.langgraph_thread_id]));
								} else {
									// completed / failed / cancelled — fully done
									setAbandonedRuns((prev) => prev.filter((r) => r.id !== run.id));
									setAbandonedSessionIds((prev) => {
										const s = new Set(prev);
										s.delete(run.langgraph_thread_id);
										return s;
									});
								}
								return;
							}
							// status === "live": transitioning to live tail
						} else if (anyParsed._marker === "run-end") {
							setActiveRuns((prev) => removeRun(prev, run.id, threadId));
							setAbandonedRuns((prev) => prev.filter((r) => r.id !== run.id));
							setAbandonedSessionIds((prev) => {
								const s = new Set(prev);
								s.delete(run.langgraph_thread_id);
								return s;
							});
							setMessages((prev) => prev.filter((m) => m.id !== `msg-assistant-resume-${run.id}`));
							return;
						}
						continue; // marker events don't reach the orchestra reducer
					}
					if (anyParsed && anyParsed.type) {
						setOrchestraState((prev: unknown) =>
							applyOrchestraEvent(prev as never, anyParsed as never)
						);
					}
				}
			} catch (err) {
				if (ac.signal.aborted) return;
				if (err instanceof QuotaExceededError) {
					toast.error("Token quota exceeded. Please upgrade your plan.");
					return;
				}
				if (err instanceof StreamMaxRetriesError) {
					setStreamConnectionLost({ runId: run.id });
					return;
				}
				console.warn(`[attachToRun] Run ${run.id} failed:`, err);
			}
		};

		attachToRunRef.current = attachToRun;

		getActiveRuns(threadId)
			.then((runs) => {
				const running = runs.filter((r) => r.status === "running");
				const abandoned = runs.filter((r) => r.status === "abandoned");
				setActiveRuns((prev) => {
					let next = prev;
					for (const r of runs) next = upsertRun(next, r);
					return next;
				});
				setAbandonedRuns(abandoned);
				setAbandonedSessionIds(new Set(abandoned.map((r) => r.langgraph_thread_id)));
				for (const run of running) {
					attachToRun(run);
				}
			})
			.catch(() => {
				// Silently ignore — feature degrades gracefully
			});

		return () => {
			// M6: cancel readers in addition to abort, so pending reader.read() resolves immediately
			for (const reader of readers) {
				reader.cancel().catch(() => undefined);
			}
			for (const ac of abortControllers) ac.abort();
		};
	}, [threadId, setActiveRuns, setOrchestraState, setAbandonedSessionIds]);

	// T21: register resume handler so OrchestraStrip can resume by sessionId
	useEffect(() => {
		if (!threadId) return;
		setResumeRunBySession(() => async (langgraphThreadId: string) => {
			const run = abandonedRunsRef.current.find((r) => r.langgraph_thread_id === langgraphThreadId);
			if (!run) {
				toast.error("Run no longer available. Please refresh the page.");
				return;
			}
			try {
				const resumed = await resumeRun(threadId, run.id);
				setAbandonedRuns((prev) => prev.filter((r) => r.id !== run.id));
				setAbandonedSessionIds((prev) => {
					const s = new Set(prev);
					s.delete(run.langgraph_thread_id);
					return s;
				});
				setActiveRuns((prev) => upsertRun(prev, resumed));
				attachToRunRef.current?.(resumed);
			} catch {
				toast.error("Failed to resume run");
			}
		});
		return () => setResumeRunBySession(null);
	}, [threadId, setResumeRunBySession, setAbandonedRuns, setAbandonedSessionIds, setActiveRuns]);

	// Cancel ongoing request
	const cancelRun = useCallback(async () => {
		if (abortControllerRef.current) {
			abortControllerRef.current.abort();
			abortControllerRef.current = null;
		}
		setIsRunning(false);
	}, []);

	// Handle new message from user
	const onNew = useCallback(
		async (message: AppendMessage) => {
			// Abort any previous streaming request to prevent race conditions
			// when user sends a second query while the first is still streaming
			if (abortControllerRef.current) {
				abortControllerRef.current.abort();
				abortControllerRef.current = null;
			}

			// Extract user query text from content parts
			let userQuery = "";
			for (const part of message.content) {
				if (part.type === "text") {
					userQuery += part.text;
				}
			}

			if (!userQuery.trim()) return;

			// Check if podcast is already generating
			if (isPodcastGenerating() && looksLikePodcastRequest(userQuery)) {
				toast.warning("A podcast is already being generated.");
				return;
			}

			// Lazy thread creation: create thread on first message if it doesn't exist
			let currentThreadId = threadId;
			let isNewThread = false;
			if (!currentThreadId) {
				try {
					const newThread = await createThread(searchSpaceId, "New Chat");
					currentThreadId = newThread.id;
					setThreadId(currentThreadId);
					// Set currentThread so share button in header appears immediately
					setCurrentThread(newThread);

					// Track chat creation
					trackChatCreated(searchSpaceId, currentThreadId);

					isNewThread = true;
					// Update URL silently using browser API (not router.replace) to avoid
					// interrupting the ongoing fetch/streaming with React navigation
					window.history.replaceState(
						null,
						"",
						`/dashboard/${searchSpaceId}/new-chat/${currentThreadId}`
					);
				} catch (error) {
					console.error("[NewChatPage] Failed to create thread:", error);
					toast.error("Failed to start chat. Please try again.");
					return;
				}
			}

			// Add user message to state
			const userMsgId = `msg-user-${Date.now()}`;

			// Always include author metadata so the UI layer can decide visibility
			const authorMetadata = currentUser
				? {
						custom: {
							author: {
								displayName: currentUser.display_name ?? null,
								avatarUrl: currentUser.avatar_url ?? null,
							},
						},
					}
				: undefined;

			const userMessage: ThreadMessageLike = {
				id: userMsgId,
				role: "user",
				content: message.content,
				createdAt: new Date(),
				metadata: authorMetadata,
			};
			setMessages((prev) => [...prev, userMessage]);

			// Track message sent
			trackChatMessageSent(searchSpaceId, currentThreadId, {
				hasAttachments: false,
				hasMentionedDocuments:
					mentionedDocumentIds.nowing_doc_ids.length > 0 ||
					mentionedDocumentIds.document_ids.length > 0,
				messageLength: userQuery.length,
			});

			// Combine @-mention chips + sidebar selections for display & persistence
			const allMentionedDocs: MentionedDocumentInfo[] = [];
			const seenDocKeys = new Set<string>();
			for (const doc of [...mentionedDocuments, ...sidebarDocuments]) {
				const key = `${doc.document_type}:${doc.id}`;
				if (!seenDocKeys.has(key)) {
					seenDocKeys.add(key);
					allMentionedDocs.push({ id: doc.id, title: doc.title, document_type: doc.document_type });
				}
			}

			if (allMentionedDocs.length > 0) {
				setMessageDocumentsMap((prev) => ({
					...prev,
					[userMsgId]: allMentionedDocs,
				}));
			}

			const persistContent: unknown[] = [...message.content];

			if (allMentionedDocs.length > 0) {
				persistContent.push({
					type: "mentioned-documents",
					documents: allMentionedDocs,
				});
			}

			appendMessage(currentThreadId, {
				role: "user",
				content: persistContent,
			})
				.then((savedMessage) => {
					const newUserMsgId = `msg-${savedMessage.id}`;
					setMessages((prev) =>
						prev.map((m) => (m.id === userMsgId ? { ...m, id: newUserMsgId } : m))
					);
					setMessageDocumentsMap((prev) => {
						const docs = prev[userMsgId];
						if (!docs) return prev;
						const { [userMsgId]: _, ...rest } = prev;
						return { ...rest, [newUserMsgId]: docs };
					});
					if (isNewThread) {
						queryClient.invalidateQueries({ queryKey: ["threads", String(searchSpaceId)] });
					}
				})
				.catch((err) => console.error("Failed to persist user message:", err));

			// Start streaming response
			setIsRunning(true);
			const controller = new AbortController();
			abortControllerRef.current = controller;

			// Prepare assistant message
			const assistantMsgId = `msg-assistant-${Date.now()}`;
			const currentThinkingSteps = new Map<string, ThinkingStepData>();
			const batcher = new FrameBatchedUpdater();

			const contentPartsState: ContentPartsState = {
				contentParts: [],
				currentTextPartIndex: -1,
				toolCallIndices: new Map(),
			};
			const { contentParts, toolCallIndices } = contentPartsState;
			let wasInterrupted = false;
			let activeRun: ChatRun | null = null;
			const collectedAgentResults: Array<{
				agentId: string;
				resultText: string;
				truncated: boolean;
			}> = [];

			// Add placeholder assistant message
			setMessages((prev) => [
				...prev,
				{
					id: assistantMsgId,
					role: "assistant",
					content: [{ type: "text", text: "" }],
					createdAt: new Date(),
				},
			]);

			try {
				// Get mentioned document IDs for context (separate fields for backend)
				const hasDocumentIds = mentionedDocumentIds.document_ids.length > 0;
				const hasNowingDocIds = mentionedDocumentIds.nowing_doc_ids.length > 0;

				// Clear mentioned documents after capturing them
				if (hasDocumentIds || hasNowingDocIds) {
					setMentionedDocuments([]);
					setSidebarDocuments([]);
				}

				const run = await startRun(currentThreadId, {
					search_space_id: searchSpaceId,
					user_query: userQuery.trim(),
					mentioned_document_ids: hasDocumentIds ? mentionedDocumentIds.document_ids : undefined,
					mentioned_nowing_doc_ids: hasNowingDocIds
						? mentionedDocumentIds.nowing_doc_ids
						: undefined,
					disabled_tools: disabledTools.length > 0 ? disabledTools : undefined,
					...(isCloud() && selectedSystemModelId != null && { model_id: selectedSystemModelId }),
				});
				activeRun = run;
				setActiveRuns((prev) => upsertRun(prev, run));

				const flushMessages = () => {
					setMessages((prev) =>
						prev.map((m) =>
							m.id === assistantMsgId
								? { ...m, content: buildContentForUI(contentPartsState, TOOLS_WITH_UI) }
								: m
						)
					);
				};
				const scheduleFlush = () => batcher.schedule(flushMessages);

				for await (const parsed of streamRun(currentThreadId, run.id, -1, controller.signal)) {
					switch (parsed.type) {
						case "text-delta":
							appendText(contentPartsState, parsed.delta);
							scheduleFlush();
							break;

						case "tool-input-start":
							addToolCall(contentPartsState, TOOLS_WITH_UI, parsed.toolCallId, parsed.toolName, {});
							batcher.flush();
							break;

						case "tool-input-available": {
							if (toolCallIndices.has(parsed.toolCallId)) {
								updateToolCall(contentPartsState, parsed.toolCallId, { args: parsed.input || {} });
							} else {
								addToolCall(
									contentPartsState,
									TOOLS_WITH_UI,
									parsed.toolCallId,
									parsed.toolName,
									parsed.input || {}
								);
							}
							batcher.flush();
							break;
						}

						case "tool-output-available": {
							updateToolCall(contentPartsState, parsed.toolCallId, { result: parsed.output });
							markInterruptsCompleted(contentParts);
							if (parsed.output?.status === "pending" && parsed.output?.podcast_id) {
								const idx = toolCallIndices.get(parsed.toolCallId);
								if (idx !== undefined) {
									const part = contentParts[idx];
									if (part?.type === "tool-call" && part.toolName === "generate_podcast") {
										setActivePodcastTaskId(String(parsed.output.podcast_id));
									}
								}
							}
							batcher.flush();
							break;
						}

						case "data-thinking-step": {
							const stepData = parsed.data as ThinkingStepData;
							if (stepData?.id) {
								currentThinkingSteps.set(stepData.id, stepData);
								const didUpdate = updateThinkingSteps(contentPartsState, currentThinkingSteps);
								if (didUpdate) {
									scheduleFlush();
								}
							}
							break;
						}

						case "data-thread-title-update": {
							const titleData = parsed.data as { threadId: number; title: string };
							if (titleData?.title && titleData?.threadId === currentThreadId) {
								setCurrentThread((prev) => (prev ? { ...prev, title: titleData.title } : prev));
								updateChatTabTitle({ chatId: currentThreadId, title: titleData.title });
								queryClient.invalidateQueries({
									queryKey: ["threads", String(searchSpaceId)],
								});
							}
							break;
						}

						case "data-documents-updated": {
							const docEvent = parsed.data as {
								action: string;
								document: AgentCreatedDocument;
							};
							if (docEvent?.document?.id) {
								setAgentCreatedDocuments((prev) => {
									if (prev.some((d) => d.id === docEvent.document.id)) return prev;
									return [...prev, docEvent.document];
								});
							}
							break;
						}

						case "data-interrupt-request": {
							wasInterrupted = true;
							const interruptData = parsed.data as Record<string, unknown>;
							const actionRequests = (interruptData.action_requests ?? []) as Array<{
								name: string;
								args: Record<string, unknown>;
							}>;
							for (const action of actionRequests) {
								const existingIdx = Array.from(toolCallIndices.entries()).find(([, idx]) => {
									const part = contentParts[idx];
									return part?.type === "tool-call" && part.toolName === action.name;
								});
								if (existingIdx) {
									updateToolCall(contentPartsState, existingIdx[0], {
										result: { __interrupt__: true, ...interruptData },
									});
								} else {
									const tcId = `interrupt-${action.name}`;
									addToolCall(contentPartsState, TOOLS_WITH_UI, tcId, action.name, action.args);
									updateToolCall(contentPartsState, tcId, {
										result: { __interrupt__: true, ...interruptData },
									});
								}
							}
							setMessages((prev) =>
								prev.map((m) =>
									m.id === assistantMsgId
										? { ...m, content: buildContentForUI(contentPartsState, TOOLS_WITH_UI) }
										: m
								)
							);
							if (currentThreadId) {
								setPendingInterrupt({
									threadId: currentThreadId,
									assistantMsgId,
									interruptData,
								});
							}
							break;
						}

						case "data-token-usage": {
							const usageData = parsed.data as {
								tokens_this_request: number;
								tokens_used_total: number;
								monthly_limit: number;
								tokens_remaining: number;
							};
							// Attach usage to the assistant message so it renders under that
							// specific response (footer), not floating over the composer.
							setMessages((prev) =>
								prev.map((m) =>
									m.id === assistantMsgId
										? {
												...m,
												metadata: {
													...(m.metadata as Record<string, unknown> | undefined),
													custom: {
														...((m.metadata as { custom?: Record<string, unknown> })?.custom ??
															{}),
														token_usage: usageData,
													},
												},
											}
										: m
								)
							);
							break;
						}

						case "data-citation-map": {
							const citationData = parsed.data as { citation_map: Record<string, unknown> };
							if (citationData?.citation_map) {
								// Persist citation_map in contentPartsState so buildContentForPersistence
								// saves it to DB — enables citation chips to render after page reload
								contentPartsState.contentParts.push({
									type: "data-citation-map",
									data: { citation_map: citationData.citation_map },
								});
								setMessages((prev) =>
									prev.map((m) =>
										m.id === assistantMsgId
											? {
													...m,
													metadata: {
														...(m.metadata as Record<string, unknown> | undefined),
														custom: {
															...((m.metadata as { custom?: Record<string, unknown> })?.custom ??
																{}),
															citation_map: citationData.citation_map,
														},
													},
												}
											: m
									)
								);
							}
							break;
						}

						case "data-follow-ups": {
							const followUpsData = parsed.data as { follow_ups: string[] };
							if (followUpsData?.follow_ups?.length) {
								setMessages((prev) =>
									prev.map((m) =>
										m.id === assistantMsgId
											? {
													...m,
													metadata: {
														...(m.metadata as Record<string, unknown> | undefined),
														custom: {
															...((
																m.metadata as {
																	custom?: Record<string, unknown>;
																}
															)?.custom ?? {}),
															follow_ups: followUpsData.follow_ups,
															thread_id: currentThreadId,
														},
													},
												}
											: m
									)
								);
							}
							break;
						}

						case "data-token-meta": {
							const tokenMetaData = parsed.data as {
								token_symbol: string;
								token_name: string;
								coingecko_id: string;
							};
							if (tokenMetaData?.token_symbol) {
								setMessages((prev) =>
									prev.map((m) =>
										m.id === assistantMsgId
											? {
													...m,
													metadata: {
														...(m.metadata as Record<string, unknown> | undefined),
														custom: {
															...((
																m.metadata as {
																	custom?: Record<string, unknown>;
																}
															)?.custom ?? {}),
															token_symbol: tokenMetaData.token_symbol,
															token_name: tokenMetaData.token_name,
															coingecko_id: tokenMetaData.coingecko_id,
														},
													},
												}
											: m
									)
								);
							}
							break;
						}

						case "data-smart-money-flow": {
							console.log("data-smart-money-flow event:", parsed.data);
							const flowData = parseSmartMoneyFlow(parsed.data);
							console.log("flowData parsed:", flowData);
							if (flowData) {
								applySmartMoneyFlowUpdate(flowData, assistantMsgId, contentPartsState, setMessages);
							}
							break;
						}

						case "data-report-type": {
							const reportTypeData = parsed.data as { report_type: string };
							if (reportTypeData?.report_type) {
								setMessages((prev) =>
									prev.map((m) =>
										m.id === assistantMsgId
											? {
													...m,
													metadata: {
														...(m.metadata as Record<string, unknown> | undefined),
														custom: {
															...((
																m.metadata as {
																	custom?: Record<string, unknown>;
																}
															)?.custom ?? {}),
															report_type: reportTypeData.report_type,
														},
													},
												}
											: m
									)
								);
							}
							break;
						}

						case "orchestra-spawn":
						case "orchestra-update":
						case "orchestra-done":
						case "orchestra-fail":
						case "orchestra-cancel":
						case "orchestra-complete":
						case "data-orchestra-narration":
						case "data-orchestra-source-fetched":
						case "data-orchestra-fact-captured":
						case "data-orchestra-model-attribution":
						case "data-orchestra-rate-gate-wait":
						case "data-orchestra-llm-call":
						case "data-agent-result": {
							handleOrchestraEvent(
								parsed as { type: string; data?: Record<string, unknown> },
								setOrchestraState as (fn: (prev: unknown) => unknown) => void
							);
							const arData = (parsed as { data?: Record<string, unknown> }).data;
							if (arData?.agentId && arData?.resultText) {
								collectedAgentResults.push({
									agentId: String(arData.agentId),
									resultText: String(arData.resultText),
									truncated: Boolean(arData.truncated),
								});
							}
							break;
						}
						case "error":
							if (
								parsed.errorText?.includes("quota") ||
								parsed.errorText?.includes("token_quota_exceeded")
							) {
								throw new QuotaExceededError();
							}
							throw new Error(parsed.errorText || "Server error");
					}
				}

				batcher.flush();

				if (collectedAgentResults.length > 0) {
					contentPartsState.contentParts.push({
						type: "data-agent-results",
						data: { results: collectedAgentResults },
					});
				}

				// Skip persistence for interrupted messages -- handleResume will persist the final version
				const finalContent = buildContentForPersistence(contentPartsState, TOOLS_WITH_UI);
				if (contentParts.length > 0 && !wasInterrupted) {
					try {
						const savedMessage = await appendMessage(currentThreadId, {
							role: "assistant",
							content: finalContent,
						});

						// Update message ID from temporary to database ID so comments work immediately
						const newMsgId = `msg-${savedMessage.id}`;
						setMessages((prev) =>
							prev.map((m) => (m.id === assistantMsgId ? { ...m, id: newMsgId } : m))
						);

						// Update pending interrupt with the new persisted message ID
						setPendingInterrupt((prev) =>
							prev && prev.assistantMsgId === assistantMsgId
								? { ...prev, assistantMsgId: newMsgId }
								: prev
						);
					} catch (err) {
						console.error("Failed to persist assistant message:", err);
					}

					// Track successful response
					trackChatResponseReceived(searchSpaceId, currentThreadId);
				}
			} catch (error) {
				batcher.dispose();
				if (error instanceof Error && error.name === "AbortError") {
					// Request was cancelled by user - persist partial response if any content was received
					const hasContent = contentParts.some(
						(part) =>
							(part.type === "text" && part.text.length > 0) ||
							(part.type === "tool-call" && TOOLS_WITH_UI.has(part.toolName))
					);
					if (hasContent && currentThreadId) {
						const partialContent = buildContentForPersistence(contentPartsState, TOOLS_WITH_UI);
						try {
							const savedMessage = await appendMessage(currentThreadId, {
								role: "assistant",
								content: partialContent,
							});

							// Update message ID from temporary to database ID
							const newMsgId = `msg-${savedMessage.id}`;
							setMessages((prev) =>
								prev.map((m) => (m.id === assistantMsgId ? { ...m, id: newMsgId } : m))
							);
						} catch (err) {
							console.error("Failed to persist partial assistant message:", err);
						}
					}
					return;
				}
				if (error instanceof QuotaExceededError) {
					toast.error("Monthly token quota exceeded. Upgrade your plan to continue.", {
						action: {
							label: "Upgrade",
							onClick: () => window.open("/pricing", "_blank"),
						},
					});
					return;
				}
				if (error instanceof StreamMaxRetriesError) {
					setStreamConnectionLost({ runId: activeRun?.id ?? "current" });
					return;
				}
				console.error("[NewChatPage] Chat error:", error);

				// Track chat error
				trackChatError(
					searchSpaceId,
					currentThreadId,
					error instanceof Error ? error.message : "Unknown error"
				);

				toast.error("Failed to get response. Please try again.");
				// Update assistant message with error
				setMessages((prev) =>
					prev.map((m) =>
						m.id === assistantMsgId
							? {
									...m,
									content: [
										{
											type: "text",
											text: "Sorry, there was an error. Please try again.",
										},
									],
								}
							: m
					)
				);
			} finally {
				setIsRunning(false);
				abortControllerRef.current = null;
				if (activeRun && currentThreadId) {
					setActiveRuns((prev) => removeRun(prev, activeRun!.id, currentThreadId));
				}
			}
		},
		[
			threadId,
			searchSpaceId,
			messages,
			mentionedDocumentIds,
			mentionedDocuments,
			sidebarDocuments,
			setMentionedDocuments,
			setSidebarDocuments,
			setMessageDocumentsMap,
			setAgentCreatedDocuments,
			queryClient,
			currentUser,
			disabledTools,
			updateChatTabTitle,
			selectedSystemModelId,
			setActiveRuns,
		]
	);

	const handleResume = useCallback(
		async (
			decisions: Array<{
				type: string;
				message?: string;
				edited_action?: { name: string; args: Record<string, unknown> };
			}>
		) => {
			if (!pendingInterrupt) return;
			const { threadId: resumeThreadId, assistantMsgId } = pendingInterrupt;
			setPendingInterrupt(null);
			setIsRunning(true);

			const token = getBearerToken();
			if (!token) {
				toast.error("Not authenticated. Please log in again.");
				setIsRunning(false);
				return;
			}

			const controller = new AbortController();
			abortControllerRef.current = controller;

			const currentThinkingSteps = new Map<string, ThinkingStepData>();
			const batcher = new FrameBatchedUpdater();

			const contentPartsState: ContentPartsState = {
				contentParts: [],
				currentTextPartIndex: -1,
				toolCallIndices: new Map(),
			};
			const { contentParts, toolCallIndices } = contentPartsState;
			const collectedAgentResults: Array<{
				agentId: string;
				resultText: string;
				truncated: boolean;
			}> = [];

			const existingMsg = messages.find((m) => m.id === assistantMsgId);
			if (existingMsg && Array.isArray(existingMsg.content)) {
				for (const part of existingMsg.content) {
					if (typeof part === "object" && part !== null) {
						const p = part as Record<string, unknown>;
						if (p.type === "text") {
							contentParts.push({ type: "text", text: String(p.text ?? "") });
							contentPartsState.currentTextPartIndex = contentParts.length - 1;
						} else if (p.type === "tool-call") {
							toolCallIndices.set(String(p.toolCallId), contentParts.length);
							contentParts.push({
								type: "tool-call",
								toolCallId: String(p.toolCallId),
								toolName: String(p.toolName),
								args: (p.args as Record<string, unknown>) ?? {},
								result: p.result as unknown,
							});
							contentPartsState.currentTextPartIndex = -1;
						} else if (p.type === "data-thinking-steps") {
							const stepsData = p.data as { steps: ThinkingStepData[] } | undefined;
							contentParts.push({
								type: "data-thinking-steps",
								data: { steps: stepsData?.steps ?? [] },
							});
							for (const step of stepsData?.steps ?? []) {
								currentThinkingSteps.set(step.id, step);
							}
						}
					}
				}
			}

			// Merge edited args if present to fix race condition
			if (decisions.length > 0 && decisions[0].type === "edit" && decisions[0].edited_action) {
				const editedAction = decisions[0].edited_action;
				for (const part of contentParts) {
					if (part.type === "tool-call" && part.toolName === editedAction.name) {
						part.args = { ...part.args, ...editedAction.args };
						break;
					}
				}
			}

			const decisionType = decisions[0]?.type as "approve" | "reject" | undefined;
			if (decisionType) {
				for (const part of contentParts) {
					if (
						part.type === "tool-call" &&
						typeof part.result === "object" &&
						part.result !== null &&
						"__interrupt__" in (part.result as Record<string, unknown>)
					) {
						part.result = {
							...(part.result as Record<string, unknown>),
							__decided__: decisionType,
						};
					}
				}
			}

			try {
				const backendUrl = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || "http://localhost:8000";
				const response = await fetch(`${backendUrl}/api/v1/threads/${resumeThreadId}/resume`, {
					method: "POST",
					headers: {
						"Content-Type": "application/json",
						Authorization: `Bearer ${token}`,
					},
					body: JSON.stringify({
						search_space_id: searchSpaceId,
						decisions,
						...(isCloud() && selectedSystemModelId != null && { model_id: selectedSystemModelId }),
					}),
					signal: controller.signal,
				});

				if (!response.ok) {
					if (response.status === 402) throw new QuotaExceededError();
					throw new Error(`Backend error: ${response.status}`);
				}

				const flushMessages = () => {
					setMessages((prev) =>
						prev.map((m) =>
							m.id === assistantMsgId
								? { ...m, content: buildContentForUI(contentPartsState, TOOLS_WITH_UI) }
								: m
						)
					);
				};
				const scheduleFlush = () => batcher.schedule(flushMessages);

				for await (const parsed of readSSEStream(response)) {
					switch (parsed.type) {
						case "text-delta":
							appendText(contentPartsState, parsed.delta);
							scheduleFlush();
							break;

						case "tool-input-start":
							addToolCall(contentPartsState, TOOLS_WITH_UI, parsed.toolCallId, parsed.toolName, {});
							batcher.flush();
							break;

						case "tool-input-available":
							if (toolCallIndices.has(parsed.toolCallId)) {
								updateToolCall(contentPartsState, parsed.toolCallId, {
									args: parsed.input || {},
								});
							} else {
								addToolCall(
									contentPartsState,
									TOOLS_WITH_UI,
									parsed.toolCallId,
									parsed.toolName,
									parsed.input || {}
								);
							}
							batcher.flush();
							break;

						case "tool-output-available":
							updateToolCall(contentPartsState, parsed.toolCallId, {
								result: parsed.output,
							});
							markInterruptsCompleted(contentParts);
							batcher.flush();
							break;

						case "data-thinking-step": {
							const stepData = parsed.data as ThinkingStepData;
							if (stepData?.id) {
								currentThinkingSteps.set(stepData.id, stepData);
								const didUpdate = updateThinkingSteps(contentPartsState, currentThinkingSteps);
								if (didUpdate) {
									scheduleFlush();
								}
							}
							break;
						}

						case "data-interrupt-request": {
							const interruptData = parsed.data as Record<string, unknown>;
							const actionRequests = (interruptData.action_requests ?? []) as Array<{
								name: string;
								args: Record<string, unknown>;
							}>;
							for (const action of actionRequests) {
								const existingIdx = Array.from(toolCallIndices.entries()).find(([, idx]) => {
									const part = contentParts[idx];
									return part?.type === "tool-call" && part.toolName === action.name;
								});
								if (existingIdx) {
									updateToolCall(contentPartsState, existingIdx[0], {
										result: {
											__interrupt__: true,
											...interruptData,
										},
									});
								} else {
									const tcId = `interrupt-${action.name}`;
									addToolCall(contentPartsState, TOOLS_WITH_UI, tcId, action.name, action.args);
									updateToolCall(contentPartsState, tcId, {
										result: {
											__interrupt__: true,
											...interruptData,
										},
									});
								}
							}
							setMessages((prev) =>
								prev.map((m) =>
									m.id === assistantMsgId
										? { ...m, content: buildContentForUI(contentPartsState, TOOLS_WITH_UI) }
										: m
								)
							);
							setPendingInterrupt({
								threadId: resumeThreadId,
								assistantMsgId,
								interruptData,
							});
							break;
						}

						case "data-token-usage": {
							const usageData = parsed.data as {
								tokens_this_request: number;
								tokens_used_total: number;
								monthly_limit: number;
								tokens_remaining: number;
							};
							// Attach usage to the assistant message so it renders under that
							// specific response (footer), not floating over the composer.
							setMessages((prev) =>
								prev.map((m) =>
									m.id === assistantMsgId
										? {
												...m,
												metadata: {
													...(m.metadata as Record<string, unknown> | undefined),
													custom: {
														...((m.metadata as { custom?: Record<string, unknown> })?.custom ??
															{}),
														token_usage: usageData,
													},
												},
											}
										: m
								)
							);
							break;
						}

						case "data-token-meta": {
							const tokenMetaData = parsed.data as {
								token_symbol: string;
								token_name: string;
								coingecko_id: string;
							};
							if (tokenMetaData?.token_symbol) {
								setMessages((prev) =>
									prev.map((m) =>
										m.id === assistantMsgId
											? {
													...m,
													metadata: {
														...(m.metadata as Record<string, unknown> | undefined),
														custom: {
															...((
																m.metadata as {
																	custom?: Record<string, unknown>;
																}
															)?.custom ?? {}),
															token_symbol: tokenMetaData.token_symbol,
															token_name: tokenMetaData.token_name,
															coingecko_id: tokenMetaData.coingecko_id,
														},
													},
												}
											: m
									)
								);
							}
							break;
						}

						case "data-smart-money-flow": {
							console.log("data-smart-money-flow event:", parsed.data);
							const flowData = parseSmartMoneyFlow(parsed.data);
							console.log("flowData parsed:", flowData);
							if (flowData) {
								applySmartMoneyFlowUpdate(flowData, assistantMsgId, contentPartsState, setMessages);
							}
							break;
						}

						case "data-report-type": {
							const reportTypeData = parsed.data as { report_type: string };
							if (reportTypeData?.report_type) {
								setMessages((prev) =>
									prev.map((m) =>
										m.id === assistantMsgId
											? {
													...m,
													metadata: {
														...(m.metadata as Record<string, unknown> | undefined),
														custom: {
															...((
																m.metadata as {
																	custom?: Record<string, unknown>;
																}
															)?.custom ?? {}),
															report_type: reportTypeData.report_type,
														},
													},
												}
											: m
									)
								);
							}
							break;
						}

						case "orchestra-spawn":
						case "orchestra-update":
						case "orchestra-done":
						case "orchestra-fail":
						case "orchestra-cancel":
						case "orchestra-complete":
						case "data-orchestra-narration":
						case "data-orchestra-source-fetched":
						case "data-orchestra-fact-captured":
						case "data-orchestra-model-attribution":
						case "data-orchestra-rate-gate-wait":
						case "data-orchestra-llm-call":
						case "data-agent-result": {
							handleOrchestraEvent(
								parsed as { type: string; data?: Record<string, unknown> },
								setOrchestraState as (fn: (prev: unknown) => unknown) => void
							);
							const arData = (parsed as { data?: Record<string, unknown> }).data;
							if (arData?.agentId && arData?.resultText) {
								collectedAgentResults.push({
									agentId: String(arData.agentId),
									resultText: String(arData.resultText),
									truncated: Boolean(arData.truncated),
								});
							}
							break;
						}
						case "error":
							if (
								parsed.errorText?.includes("quota") ||
								parsed.errorText?.includes("token_quota_exceeded")
							) {
								throw new QuotaExceededError();
							}
							throw new Error(parsed.errorText || "Server error");
					}
				}

				batcher.flush();

				if (collectedAgentResults.length > 0) {
					contentPartsState.contentParts.push({
						type: "data-agent-results",
						data: { results: collectedAgentResults },
					});
				}

				const finalContent = buildContentForPersistence(contentPartsState, TOOLS_WITH_UI);
				if (contentParts.length > 0) {
					try {
						const savedMessage = await appendMessage(resumeThreadId, {
							role: "assistant",
							content: finalContent,
						});
						const newMsgId = `msg-${savedMessage.id}`;
						setMessages((prev) =>
							prev.map((m) => (m.id === assistantMsgId ? { ...m, id: newMsgId } : m))
						);
					} catch (err) {
						console.error("Failed to persist resumed assistant message:", err);
					}
				}
			} catch (error) {
				batcher.dispose();
				if (error instanceof Error && error.name === "AbortError") {
					return;
				}
				if (error instanceof QuotaExceededError) {
					toast.error("Monthly token quota exceeded. Upgrade your plan to continue.", {
						action: {
							label: "Upgrade",
							onClick: () => window.open("/pricing", "_blank"),
						},
					});
					return;
				}
				console.error("[NewChatPage] Resume error:", error);
				toast.error("Failed to resume. Please try again.");
			} finally {
				setIsRunning(false);
				abortControllerRef.current = null;
			}
		},
		[pendingInterrupt, messages, searchSpaceId]
	);

	useEffect(() => {
		const handler = (e: Event) => {
			const detail = (e as CustomEvent).detail as {
				decisions: Array<{
					type: string;
					message?: string;
					edited_action?: { name: string; args: Record<string, unknown> };
				}>;
			};
			if (detail?.decisions && pendingInterrupt) {
				const decision = detail.decisions[0];
				const decisionType = decision?.type as "approve" | "reject" | "edit";

				setMessages((prev) =>
					prev.map((m) => {
						if (m.id !== pendingInterrupt.assistantMsgId) return m;
						const parts = m.content as unknown as Array<Record<string, unknown>>;
						const newContent = parts.map((part) => {
							if (
								part.type === "tool-call" &&
								typeof part.result === "object" &&
								part.result !== null &&
								"__interrupt__" in part.result
							) {
								// For edit decisions, also update the displayed args
								if (decisionType === "edit" && decision.edited_action) {
									return {
										...part,
										args: decision.edited_action.args, // Update displayed args
										result: {
											...(part.result as Record<string, unknown>),
											__decided__: decisionType,
										},
									};
								}
								return {
									...part,
									result: {
										...(part.result as Record<string, unknown>),
										__decided__: decisionType,
									},
								};
							}
							return part;
						});
						return { ...m, content: newContent as unknown as ThreadMessageLike["content"] };
					})
				);
				handleResume(detail.decisions);
			}
		};
		window.addEventListener("hitl-decision", handler);
		return () => window.removeEventListener("hitl-decision", handler);
	}, [handleResume, pendingInterrupt]);

	// Convert message (pass through since already in correct format)
	const convertMessage = useCallback(
		(message: ThreadMessageLike): ThreadMessageLike => message,
		[]
	);

	/**
	 * Handle regeneration (edit or reload) by calling the regenerate endpoint
	 * and streaming the response. This rewinds the LangGraph checkpointer state.
	 *
	 * @param newUserQuery - The new user query (for edit). Pass null/undefined for reload.
	 */
	const handleRegenerate = useCallback(
		async (newUserQuery?: string | null) => {
			if (!threadId) {
				toast.error("Cannot regenerate: no active chat thread");
				return;
			}

			// Abort any previous streaming request
			if (abortControllerRef.current) {
				abortControllerRef.current.abort();
				abortControllerRef.current = null;
			}

			const token = getBearerToken();
			if (!token) {
				toast.error("Not authenticated. Please log in again.");
				return;
			}

			// Extract the original user query BEFORE removing messages (for reload mode)
			let userQueryToDisplay = newUserQuery;
			let originalUserMessageContent: ThreadMessageLike["content"] | null = null;
			let originalUserMessageMetadata: ThreadMessageLike["metadata"] | undefined;

			if (!newUserQuery) {
				// Reload mode - find and preserve the last user message content
				const lastUserMessage = [...messages].reverse().find((m) => m.role === "user");
				if (lastUserMessage) {
					originalUserMessageContent = lastUserMessage.content;
					originalUserMessageMetadata = lastUserMessage.metadata;
					// Extract text for the API request
					for (const part of lastUserMessage.content) {
						if (typeof part === "object" && part.type === "text" && "text" in part) {
							userQueryToDisplay = part.text;
							break;
						}
					}
				}
			}

			// Remove the last two messages (user + assistant) from the UI immediately
			// The backend will also delete them from the database
			setMessages((prev) => {
				if (prev.length >= 2) {
					return prev.slice(0, -2);
				}
				return prev;
			});

			// Start streaming
			setIsRunning(true);
			const controller = new AbortController();
			abortControllerRef.current = controller;

			// Add placeholder user message if we have a new query (edit mode)
			const userMsgId = `msg-user-${Date.now()}`;
			const assistantMsgId = `msg-assistant-${Date.now()}`;
			const currentThinkingSteps = new Map<string, ThinkingStepData>();

			const contentPartsState: ContentPartsState = {
				contentParts: [],
				currentTextPartIndex: -1,
				toolCallIndices: new Map(),
			};
			const { contentParts, toolCallIndices } = contentPartsState;
			const batcher = new FrameBatchedUpdater();
			const collectedAgentResults: Array<{
				agentId: string;
				resultText: string;
				truncated: boolean;
			}> = [];

			// Add placeholder messages to UI
			// Always add back the user message (with new query for edit, or original content for reload)
			const userMessage: ThreadMessageLike = {
				id: userMsgId,
				role: "user",
				content: newUserQuery
					? [{ type: "text", text: newUserQuery }]
					: originalUserMessageContent || [{ type: "text", text: userQueryToDisplay || "" }],
				createdAt: new Date(),
				metadata: newUserQuery ? undefined : originalUserMessageMetadata,
			};
			setMessages((prev) => [...prev, userMessage]);

			// Add placeholder assistant message
			setMessages((prev) => [
				...prev,
				{
					id: assistantMsgId,
					role: "assistant",
					content: [{ type: "text", text: "" }],
					createdAt: new Date(),
				},
			]);

			try {
				const response = await fetch(getRegenerateUrl(threadId), {
					method: "POST",
					headers: {
						"Content-Type": "application/json",
						Authorization: `Bearer ${token}`,
					},
					body: JSON.stringify({
						search_space_id: searchSpaceId,
						user_query: newUserQuery || null,
						disabled_tools: disabledTools.length > 0 ? disabledTools : undefined,
						...(isCloud() && selectedSystemModelId != null && { model_id: selectedSystemModelId }),
					}),
					signal: controller.signal,
				});

				if (!response.ok) {
					if (response.status === 402) throw new QuotaExceededError();
					throw new Error(`Backend error: ${response.status}`);
				}

				const flushMessages = () => {
					setMessages((prev) =>
						prev.map((m) =>
							m.id === assistantMsgId
								? { ...m, content: buildContentForUI(contentPartsState, TOOLS_WITH_UI) }
								: m
						)
					);
				};
				const scheduleFlush = () => batcher.schedule(flushMessages);

				for await (const parsed of readSSEStream(response)) {
					switch (parsed.type) {
						case "text-delta":
							appendText(contentPartsState, parsed.delta);
							scheduleFlush();
							break;

						case "tool-input-start":
							addToolCall(contentPartsState, TOOLS_WITH_UI, parsed.toolCallId, parsed.toolName, {});
							batcher.flush();
							break;

						case "tool-input-available":
							if (toolCallIndices.has(parsed.toolCallId)) {
								updateToolCall(contentPartsState, parsed.toolCallId, { args: parsed.input || {} });
							} else {
								addToolCall(
									contentPartsState,
									TOOLS_WITH_UI,
									parsed.toolCallId,
									parsed.toolName,
									parsed.input || {}
								);
							}
							batcher.flush();
							break;

						case "tool-output-available":
							updateToolCall(contentPartsState, parsed.toolCallId, { result: parsed.output });
							markInterruptsCompleted(contentParts);
							if (parsed.output?.status === "pending" && parsed.output?.podcast_id) {
								const idx = toolCallIndices.get(parsed.toolCallId);
								if (idx !== undefined) {
									const part = contentParts[idx];
									if (part?.type === "tool-call" && part.toolName === "generate_podcast") {
										setActivePodcastTaskId(String(parsed.output.podcast_id));
									}
								}
							}
							batcher.flush();
							break;

						case "data-thinking-step": {
							const stepData = parsed.data as ThinkingStepData;
							if (stepData?.id) {
								currentThinkingSteps.set(stepData.id, stepData);
								const didUpdate = updateThinkingSteps(contentPartsState, currentThinkingSteps);
								if (didUpdate) {
									scheduleFlush();
								}
							}
							break;
						}

						case "data-token-usage": {
							const usageData = parsed.data as {
								tokens_this_request: number;
								tokens_used_total: number;
								monthly_limit: number;
								tokens_remaining: number;
							};
							// Attach usage to the assistant message so it renders under that
							// specific response (footer), not floating over the composer.
							setMessages((prev) =>
								prev.map((m) =>
									m.id === assistantMsgId
										? {
												...m,
												metadata: {
													...(m.metadata as Record<string, unknown> | undefined),
													custom: {
														...((m.metadata as { custom?: Record<string, unknown> })?.custom ??
															{}),
														token_usage: usageData,
													},
												},
											}
										: m
								)
							);
							break;
						}

						case "data-token-meta": {
							const tokenMetaData = parsed.data as {
								token_symbol: string;
								token_name: string;
								coingecko_id: string;
							};
							if (tokenMetaData?.token_symbol) {
								setMessages((prev) =>
									prev.map((m) =>
										m.id === assistantMsgId
											? {
													...m,
													metadata: {
														...(m.metadata as Record<string, unknown> | undefined),
														custom: {
															...((
																m.metadata as {
																	custom?: Record<string, unknown>;
																}
															)?.custom ?? {}),
															token_symbol: tokenMetaData.token_symbol,
															token_name: tokenMetaData.token_name,
															coingecko_id: tokenMetaData.coingecko_id,
														},
													},
												}
											: m
									)
								);
							}
							break;
						}

						case "data-smart-money-flow": {
							console.log("data-smart-money-flow event:", parsed.data);
							const flowData = parseSmartMoneyFlow(parsed.data);
							console.log("flowData parsed:", flowData);
							if (flowData) {
								applySmartMoneyFlowUpdate(flowData, assistantMsgId, contentPartsState, setMessages);
							}
							break;
						}

						case "data-report-type": {
							const reportTypeData = parsed.data as { report_type: string };
							if (reportTypeData?.report_type) {
								setMessages((prev) =>
									prev.map((m) =>
										m.id === assistantMsgId
											? {
													...m,
													metadata: {
														...(m.metadata as Record<string, unknown> | undefined),
														custom: {
															...((
																m.metadata as {
																	custom?: Record<string, unknown>;
																}
															)?.custom ?? {}),
															report_type: reportTypeData.report_type,
														},
													},
												}
											: m
									)
								);
							}
							break;
						}

						case "orchestra-spawn":
						case "orchestra-update":
						case "orchestra-done":
						case "orchestra-fail":
						case "orchestra-cancel":
						case "orchestra-complete":
						case "data-orchestra-narration":
						case "data-orchestra-source-fetched":
						case "data-orchestra-fact-captured":
						case "data-orchestra-model-attribution":
						case "data-orchestra-rate-gate-wait":
						case "data-orchestra-llm-call":
						case "data-agent-result": {
							handleOrchestraEvent(
								parsed as { type: string; data?: Record<string, unknown> },
								setOrchestraState as (fn: (prev: unknown) => unknown) => void
							);
							const arData = (parsed as { data?: Record<string, unknown> }).data;
							if (arData?.agentId && arData?.resultText) {
								collectedAgentResults.push({
									agentId: String(arData.agentId),
									resultText: String(arData.resultText),
									truncated: Boolean(arData.truncated),
								});
							}
							break;
						}
						case "error":
							if (
								parsed.errorText?.includes("quota") ||
								parsed.errorText?.includes("token_quota_exceeded")
							) {
								throw new QuotaExceededError();
							}
							throw new Error(parsed.errorText || "Server error");
					}
				}

				batcher.flush();

				if (collectedAgentResults.length > 0) {
					contentPartsState.contentParts.push({
						type: "data-agent-results",
						data: { results: collectedAgentResults },
					});
				}

				// Persist messages after streaming completes
				const finalContent = buildContentForPersistence(contentPartsState, TOOLS_WITH_UI);
				if (contentParts.length > 0) {
					try {
						// Persist user message (for both edit and reload modes, since backend deleted it)
						const userContentToPersist = newUserQuery
							? [{ type: "text", text: newUserQuery }]
							: originalUserMessageContent || [{ type: "text", text: userQueryToDisplay || "" }];

						const savedUserMessage = await appendMessage(threadId, {
							role: "user",
							content: userContentToPersist,
						});

						// Update user message ID to database ID
						const newUserMsgId = `msg-${savedUserMessage.id}`;
						setMessages((prev) =>
							prev.map((m) => (m.id === userMsgId ? { ...m, id: newUserMsgId } : m))
						);

						// Persist assistant message
						const savedMessage = await appendMessage(threadId, {
							role: "assistant",
							content: finalContent,
						});

						// Update assistant message ID to database ID
						const newMsgId = `msg-${savedMessage.id}`;
						setMessages((prev) =>
							prev.map((m) => (m.id === assistantMsgId ? { ...m, id: newMsgId } : m))
						);

						trackChatResponseReceived(searchSpaceId, threadId);
					} catch (err) {
						console.error("Failed to persist regenerated message:", err);
					}
				}
			} catch (error) {
				if (error instanceof Error && error.name === "AbortError") {
					return;
				}
				batcher.dispose();
				if (error instanceof QuotaExceededError) {
					toast.error("Monthly token quota exceeded. Upgrade your plan to continue.", {
						action: {
							label: "Upgrade",
							onClick: () => window.open("/pricing", "_blank"),
						},
					});
					return;
				}
				console.error("[NewChatPage] Regeneration error:", error);
				trackChatError(
					searchSpaceId,
					threadId,
					error instanceof Error ? error.message : "Unknown error"
				);
				toast.error("Failed to regenerate response. Please try again.");
				setMessages((prev) =>
					prev.map((m) =>
						m.id === assistantMsgId
							? {
									...m,
									content: [{ type: "text", text: "Sorry, there was an error. Please try again." }],
								}
							: m
					)
				);
			} finally {
				setIsRunning(false);
				abortControllerRef.current = null;
			}
		},
		[threadId, searchSpaceId, messages, disabledTools, selectedSystemModelId]
	);

	// Handle editing a message - truncates history and regenerates with new query
	const onEdit = useCallback(
		async (message: AppendMessage) => {
			// Extract the new user query from the message content
			let newUserQuery = "";
			for (const part of message.content) {
				if (part.type === "text") {
					newUserQuery += part.text;
				}
			}

			if (!newUserQuery.trim()) {
				toast.error("Cannot edit with empty message");
				return;
			}

			// Call regenerate with the new query
			await handleRegenerate(newUserQuery.trim());
		},
		[handleRegenerate]
	);

	// Handle reloading/refreshing the last AI response
	const onReload = useCallback(async () => {
		// parentId is the ID of the message to reload from (the user message)
		// We call regenerate without a query to use the same query
		await handleRegenerate(null);
	}, [handleRegenerate]);

	// Create external store runtime
	const runtime = useExternalStoreRuntime({
		messages,
		isRunning,
		onNew,
		onEdit,
		onReload,
		convertMessage,
		onCancel: cancelRun,
	});

	// Show loading state only when loading an existing thread
	if (isInitializing) {
		return <Loading />;
	}

	// Show error state only if we tried to load an existing thread but failed
	// For new chats (urlChatId === 0), threadId being null is expected (lazy creation)
	if (!threadId && urlChatId > 0) {
		return (
			<div className="flex h-full flex-col items-center justify-center gap-4">
				<div className="text-destructive">Failed to load chat</div>
				<button
					type="button"
					onClick={() => {
						setIsInitializing(true);
						initializeThread();
					}}
					className="rounded-md bg-primary px-4 py-2 text-primary-foreground hover:bg-primary/90"
				>
					Try Again
				</button>
			</div>
		);
	}

	return (
		<AssistantRuntimeProvider runtime={runtime}>
			<ThinkingStepsDataUI />
			<GeneratePodcastToolUI />
			<LinkPreviewToolUI />
			<DisplayImageToolUI />
			<ScrapeWebpageToolUI />
			<SaveMemoryToolUI />
			<RecallMemoryToolUI />
			{/* Crypto Tool UI Components - Conversational Crypto Advisor */}
			<TokenAnalysisToolUI />
			<WatchlistDisplayToolUI />
			<ActionConfirmationToolUI />
			<AlertConfigurationToolUI />
			<ProactiveAlertToolUI />
			<TrendingTokensToolUI />
			<WhaleActivityToolUI />
			<MarketOverviewToolUI />
			<HolderAnalysisToolUI />
			<PortfolioDisplayToolUI />
			<UserProfileToolUI />
			{/* Real-time Crypto Tools - Hybrid approach (RAG + Real-time) */}
			<LiveTokenPriceToolUI />
			<LiveTokenDataToolUI />
			{/* <WriteTodosToolUI /> Disabled for now */}
			<div key={searchSpaceId} className="flex h-full overflow-hidden">
				<div className="flex-1 flex flex-col min-w-0 overflow-hidden relative">
					{/* T21: Resume banner removed — Resume button is now in OrchestraStrip header */}
					{/* 11-1 AC#6: Connection-lost banner — surfaces stream max-retries exhaustion */}
					{streamConnectionLost && (
						<div className="absolute top-2 left-0 right-0 flex justify-center pointer-events-none px-4 z-20">
							<div className="bg-destructive/10 border border-destructive/40 text-destructive rounded-lg px-4 py-2 text-sm flex items-center gap-3 shadow-sm pointer-events-auto">
								<span>Connection lost — stream stopped after multiple retry attempts.</span>
								<button
									type="button"
									onClick={() => {
										const lostRunId = streamConnectionLost.runId;
										setStreamConnectionLost(null);
										let run: ChatRun | undefined;
										for (const runs of activeRunsRef.current.values()) {
											run = runs.find((r) => r.id === lostRunId);
											if (run) break;
										}
										if (run && attachToRunRef.current) {
											attachToRunRef.current(run);
										}
									}}
									className="font-medium underline hover:no-underline"
								>
									Click to retry
								</button>
								<button
									type="button"
									onClick={() => setStreamConnectionLost(null)}
									aria-label="Dismiss"
									className="ml-2 text-destructive/60 hover:text-destructive"
								>
									✕
								</button>
							</div>
						</div>
					)}
					<Thread />
				</div>
				<MobileReportPanel />
				<MobileEditorPanel />
				<MobileHitlEditPanel />
			</div>
		</AssistantRuntimeProvider>
	);
}

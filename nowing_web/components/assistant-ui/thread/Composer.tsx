"use client";

import { ComposerPrimitive, useAui, useAuiState } from "@assistant-ui/react";
import { useAtom, useAtomValue, useSetAtom } from "jotai";
import { Sparkles, X } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { type FC, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { chatSessionStateAtom } from "@/atoms/chat/chat-session-state.atom";
import {
	type MentionedDocumentInfo,
	mentionedDocumentsAtom,
	submittedMentionsAtom,
} from "@/atoms/chat/mentioned-documents.atom";
import { selectedLeadContextAtom } from "@/atoms/leads/leads-canvas.atoms";
import { membersAtom } from "@/atoms/members/members-query.atoms";
import { llmSetupStatusAtomFamily } from "@/atoms/model-connections/model-connections-query.atoms";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { ChatSessionStatus } from "@/components/assistant-ui/chat-session-status";
import {
	InlineMentionEditor,
	type InlineMentionEditorRef,
	type MentionedDocument,
	type SuggestionTriggerInfo,
} from "@/components/assistant-ui/inline-mention-editor";
import { ComposerSuggestionPopoverContent } from "@/components/new-chat/composer-suggestion-popup";
import {
	DocumentMentionPicker,
	type DocumentMentionPickerRef,
	promoteRecentMention,
} from "@/components/new-chat/document-mention-picker";
import { PromptPicker, type PromptPickerRef } from "@/components/new-chat/prompt-picker";
import { Popover } from "@/components/ui/popover";
import { useBatchCommentsPreload } from "@/hooks/use-comments";
import { useCommentsSync } from "@/hooks/use-comments-sync";
import { useMediaQuery } from "@/hooks/use-media-query";
import { useElectronAPI } from "@/hooks/use-platform";
import { getMentionDocKey } from "@/lib/chat/mention-doc-key";
import { slideoutOpenedTickAtom } from "@/lib/layout-events";
import { getWorkspaceIdNumber } from "@/lib/route-params";
import { cn } from "@/lib/utils";
import { ChatUnavailableNotice } from "./ChatUnavailableNotice";
import { ClipboardChip } from "./ClipboardChip";
import { ComposerAction } from "./ComposerAction";
import { ComposerSuggestionAnchor } from "./ComposerSuggestionAnchor";
import { ConnectToolsBanner } from "./ConnectToolsBanner";
import { PendingScreenImageStrip } from "./PendingScreenImageStrip";
import type { ComposerSuggestionAnchorPoint } from "./types";
import { getComposerSuggestionAnchorPoint } from "./utils";

export const Composer: FC<{ initialPrompt?: string; hasActiveThread?: boolean }> = ({
	initialPrompt,
	hasActiveThread,
}) => {
	const [mentionedDocuments, setMentionedDocuments] = useAtom(mentionedDocumentsAtom);
	const setSubmittedMentions = useSetAtom(submittedMentionsAtom);
	const [showDocumentPopover, setShowDocumentPopover] = useState(false);
	const [showPromptPicker, setShowPromptPicker] = useState(false);
	const [mentionQuery, setMentionQuery] = useState("");
	const [actionQuery, setActionQuery] = useState("");
	const [suggestionAnchorPoint, setSuggestionAnchorPoint] =
		useState<ComposerSuggestionAnchorPoint | null>(null);
	const [suggestedCardDismissed, setSuggestedCardDismissed] = useState(false);
	const [_isComposerInputEmpty, setIsComposerInputEmpty] = useState(true);
	const editorRef = useRef<InlineMentionEditorRef>(null);
	const prevMentionedDocsRef = useRef<Map<string, MentionedDocumentInfo>>(new Map());
	const documentPickerRef = useRef<DocumentMentionPickerRef>(null);
	const promptPickerRef = useRef<PromptPickerRef>(null);
	const params = useParams();
	const router = useRouter();
	const workspaceId = getWorkspaceIdNumber(params);
	const chat_id = params.chat_id;
	const aui = useAui();
	// Desktop-only auto-focus; on mobile, programmatic focus would
	// summon the soft keyboard on every picker close / thread switch.
	const isDesktop = useMediaQuery("(min-width: 640px)");

	const electronAPI = useElectronAPI();
	const [clipboardInitialText, setClipboardInitialText] = useState<string | undefined>();
	const clipboardLoadedRef = useRef(false);
	useEffect(() => {
		if (!electronAPI || clipboardLoadedRef.current) return;
		clipboardLoadedRef.current = true;
		electronAPI.getQuickAskText().then((text: string) => {
			if (text) {
				setClipboardInitialText(text);
			}
		});
	}, [electronAPI]);

	const initialPromptAppliedRef = useRef(false);
	useEffect(() => {
		if (
			!initialPrompt ||
			initialPromptAppliedRef.current ||
			hasActiveThread ||
			!editorRef.current
		) {
			return;
		}
		const text = initialPrompt.trim();
		if (!text) return;
		initialPromptAppliedRef.current = true;
		editorRef.current.setText(text);
		aui.composer().setText(text);
		setIsComposerInputEmpty(false);
		if (isDesktop) {
			editorRef.current.focus();
		}
	}, [initialPrompt, hasActiveThread, aui, isDesktop]);

	const tChat = useTranslations("chat");
	const isThreadEmpty = useAuiState(({ thread }) => thread.isEmpty);
	const isThreadRunning = useAuiState(({ thread }) => thread.isRunning);
	const [connectToolsTrayVisible, setConnectToolsTrayVisible] = useState(false);
	const [selectedLeadContext, setSelectedLeadContext] = useAtom(selectedLeadContextAtom);

	const { data: chatSetupStatus } = useAtomValue(llmSetupStatusAtomFamily(workspaceId ?? 0));
	const isChatUnavailable = !!chatSetupStatus && chatSetupStatus.status !== "ready";

	const currentPlaceholder = tChat("composer_placeholder");

	const { data: currentUser } = useAtomValue(currentUserAtom);
	const { data: members } = useAtomValue(membersAtom);
	const threadId = useMemo(() => {
		if (Array.isArray(chat_id) && chat_id.length > 0) {
			return Number.parseInt(chat_id[0], 10) || null;
		}
		return typeof chat_id === "string" ? Number.parseInt(chat_id, 10) || null : null;
	}, [chat_id]);
	const sessionState = useAtomValue(chatSessionStateAtom);
	const isAiResponding = sessionState?.isAiResponding ?? false;
	const respondingToUserId = sessionState?.respondingToUserId ?? null;
	const isBlockedByOtherUser = isAiResponding && respondingToUserId !== currentUser?.id;

	// One Zero subscription per thread for comment sync.
	useCommentsSync(threadId);

	// Batch-prefetch assistant message comments to avoid N+1 fetches.
	// Returns a primitive string so useSyncExternalStore can compare by value.
	const assistantIdsKey = useAuiState(({ thread }) =>
		thread.messages
			.filter((m) => m.role === "assistant" && m.id?.startsWith("msg-"))
			.map((m) => m.id?.replace("msg-", ""))
			.join(",")
	);
	const assistantDbMessageIds = useMemo(
		() => (assistantIdsKey ? assistantIdsKey.split(",").map(Number) : []),
		[assistantIdsKey]
	);
	useBatchCommentsPreload(assistantDbMessageIds);

	// Always-focused composer: refocus whenever no picker has taken
	// over input. ``threadId`` is in the deps so the effect re-fires
	// on thread switch (Composer instance is reused).
	useEffect(() => {
		if (!isDesktop) return;
		if (showDocumentPopover || showPromptPicker) return;
		void threadId;
		editorRef.current?.focus();
	}, [isDesktop, showDocumentPopover, showPromptPicker, threadId]);

	const handleChatModelSelected = useCallback(() => {
		if (!isDesktop) return;
		editorRef.current?.focus();
	}, [isDesktop]);

	// Close document picker when a sidebar slide-out panel (inbox, etc.) opens.
	// React only on changes to the tick — comparing against the previously-seen
	// value preserves the one-shot semantics of the prior window-event approach
	// (no retroactive close on mount if a panel had already opened earlier).
	const slideoutOpenedTick = useAtomValue(slideoutOpenedTickAtom);
	const lastSeenSlideoutTickRef = useRef(slideoutOpenedTick);
	useEffect(() => {
		if (lastSeenSlideoutTickRef.current === slideoutOpenedTick) return;
		lastSeenSlideoutTickRef.current = slideoutOpenedTick;
		setShowDocumentPopover(false);
		setMentionQuery("");
		setSuggestionAnchorPoint(null);
	}, [slideoutOpenedTick]);

	// Sync editor text into assistant-ui's composer and mirror the chip
	// atom from the editor's reported ``docs``. The editor is the
	// single source of truth, so this catches every Plate deletion path
	// (Backspace, X button, Cmd+Backspace, range-delete, cut,
	// paste-over) without per-keybinding plumbing. The ``prev``
	// short-circuit keeps pure-text keystrokes from churning the atom.
	const handleEditorChange = useCallback(
		(text: string, docs: MentionedDocument[]) => {
			setIsComposerInputEmpty(text.trim().length === 0 && docs.length === 0);
			aui.composer().setText(text);
			setMentionedDocuments((prev) => {
				if (prev.length === docs.length) {
					const editorKeys = new Set(docs.map((d) => getMentionDocKey(d)));
					if (prev.every((d) => editorKeys.has(getMentionDocKey(d)))) {
						return prev;
					}
				}
				return docs.map<MentionedDocumentInfo>((d) => {
					if (d.kind === "connector") {
						return {
							id: d.id,
							title: d.title,
							kind: "connector",
							connector_type: d.connector_type ?? "UNKNOWN",
							account_name: d.account_name ?? d.title,
						};
					}
					if (d.kind === "folder") {
						return {
							id: d.id,
							title: d.title,
							kind: "folder",
						};
					}
					if (d.kind === "thread") {
						return {
							id: d.id,
							title: d.title,
							kind: "thread",
						};
					}
					return {
						id: d.id,
						title: d.title,
						document_type: d.document_type ?? "UNKNOWN",
						kind: "doc",
					};
				});
			});
		},
		[aui, setMentionedDocuments]
	);

	const handleMentionTrigger = useCallback((trigger: SuggestionTriggerInfo) => {
		const anchorPoint = getComposerSuggestionAnchorPoint(trigger.anchorRect, "top");
		if (!anchorPoint) {
			setShowDocumentPopover(false);
			setMentionQuery("");
			setSuggestionAnchorPoint(null);
			return;
		}
		setSuggestionAnchorPoint((current) => current ?? anchorPoint);
		setShowDocumentPopover(true);
		setMentionQuery(trigger.query);
	}, []);

	const handleMentionClose = useCallback(() => {
		if (showDocumentPopover) {
			setShowDocumentPopover(false);
			setMentionQuery("");
			setSuggestionAnchorPoint(null);
		}
	}, [showDocumentPopover]);

	const handleDocumentPopoverOpenChange = useCallback((open: boolean) => {
		setShowDocumentPopover(open);
		if (!open) {
			setMentionQuery("");
			setSuggestionAnchorPoint(null);
		}
	}, []);

	const handleActionTrigger = useCallback(
		(trigger: SuggestionTriggerInfo) => {
			const anchorPoint = getComposerSuggestionAnchorPoint(
				trigger.anchorRect,
				clipboardInitialText ? "bottom" : "top"
			);
			if (!anchorPoint) {
				setShowPromptPicker(false);
				setActionQuery("");
				setSuggestionAnchorPoint(null);
				return;
			}
			setSuggestionAnchorPoint((current) => current ?? anchorPoint);
			setShowPromptPicker(true);
			setActionQuery(trigger.query);
		},
		[clipboardInitialText]
	);

	const handleActionClose = useCallback(() => {
		if (showPromptPicker) {
			setShowPromptPicker(false);
			setActionQuery("");
			setSuggestionAnchorPoint(null);
		}
	}, [showPromptPicker]);

	const handlePromptPickerOpenChange = useCallback((open: boolean) => {
		setShowPromptPicker(open);
		if (!open) {
			setActionQuery("");
			setSuggestionAnchorPoint(null);
		}
	}, []);

	const handleActionSelect = useCallback(
		(action: {
			name: string;
			prompt: string;
			mode: "transform" | "explore";
			chatMode?: "web_builder" | "presentation_studio" | "meeting_minutes";
		}) => {
			let userText = editorRef.current?.getText() ?? "";
			const trigger = `/${actionQuery}`;
			if (userText.endsWith(trigger)) {
				userText = userText.slice(0, -trigger.length).trimEnd();
			}
			const finalPrompt = action.prompt.includes("{selection}")
				? action.prompt.replace("{selection}", () => userText)
				: userText
					? `${action.prompt}\n\n${userText}`
					: action.prompt;
			editorRef.current?.setText(finalPrompt);
			aui.composer().setText(finalPrompt);
			setIsComposerInputEmpty(false);
			setShowPromptPicker(false);
			setActionQuery("");
			setSuggestionAnchorPoint(null);

			const targetWs = workspaceId ?? 1;
			if (action.chatMode === "web_builder") {
				router.replace(`/dashboard/${targetWs}/new-chat?mode=web_builder`, { scroll: false });
			} else if (action.chatMode === "presentation_studio") {
				router.replace(`/dashboard/${targetWs}/new-chat?mode=presentation_studio`, {
					scroll: false,
				});
			} else if (action.chatMode === "meeting_minutes") {
				router.replace(`/dashboard/${targetWs}/new-chat?mode=meeting_minutes`, { scroll: false });
			}
		},
		[actionQuery, aui, router, workspaceId]
	);

	const _handleExampleSelect = useCallback(
		(prompt: string) => {
			editorRef.current?.setText(prompt);
			aui.composer().setText(prompt);
			setIsComposerInputEmpty(false);
			editorRef.current?.focus();
		},
		[aui]
	);

	const handleQuickAskSelect = useCallback(
		(action: { name: string; prompt: string; mode: "transform" | "explore" }) => {
			if (!clipboardInitialText) return;
			electronAPI?.setQuickAskMode(action.mode);
			const finalPrompt = action.prompt.includes("{selection}")
				? action.prompt.replace("{selection}", () => clipboardInitialText)
				: `${action.prompt}\n\n${clipboardInitialText}`;
			editorRef.current?.setText(finalPrompt);
			aui.composer().setText(finalPrompt);
			setIsComposerInputEmpty(false);
			setShowPromptPicker(false);
			setActionQuery("");
			setSuggestionAnchorPoint(null);
			setClipboardInitialText(undefined);
		},
		[clipboardInitialText, electronAPI, aui]
	);

	// Arrow / Enter / Escape navigation for the active picker.
	const handleKeyDown = useCallback(
		(e: React.KeyboardEvent) => {
			// While an IME composition is active (e.g. confirming a Japanese/Chinese/
			// Korean conversion), let the Enter/Arrow keys reach the IME instead of
			// driving picker navigation/selection.
			if (e.nativeEvent.isComposing) return;
			if (showPromptPicker) {
				if (e.key === "ArrowDown") {
					e.preventDefault();
					promptPickerRef.current?.moveDown();
					return;
				}
				if (e.key === "ArrowUp") {
					e.preventDefault();
					promptPickerRef.current?.moveUp();
					return;
				}
				if (e.key === "Enter") {
					e.preventDefault();
					promptPickerRef.current?.selectHighlighted();
					return;
				}
				if (e.key === "Escape") {
					e.preventDefault();
					setShowPromptPicker(false);
					setActionQuery("");
					setSuggestionAnchorPoint(null);
					return;
				}
			}
			if (showDocumentPopover) {
				if (e.key === "ArrowDown") {
					e.preventDefault();
					documentPickerRef.current?.moveDown();
					return;
				}
				if (e.key === "ArrowUp") {
					e.preventDefault();
					documentPickerRef.current?.moveUp();
					return;
				}
				if (e.key === "Enter") {
					e.preventDefault();
					documentPickerRef.current?.selectHighlighted();
					return;
				}
				if (e.key === "Escape") {
					e.preventDefault();
					if (documentPickerRef.current?.goBack()) {
						return;
					}
					setShowDocumentPopover(false);
					setMentionQuery("");
					setSuggestionAnchorPoint(null);
					return;
				}
			}
		},
		[showDocumentPopover, showPromptPicker]
	);

	const handleSubmit = useCallback(() => {
		if (isThreadRunning || isBlockedByOtherUser) return;
		if (showDocumentPopover || showPromptPicker) return;

		if (clipboardInitialText) {
			const userText = editorRef.current?.getText() ?? "";
			const combined = userText ? `${userText}\n\n${clipboardInitialText}` : clipboardInitialText;
			aui.composer().setText(combined);
			setClipboardInitialText(undefined);
		}

		// Capture chips before the reset below clears the live atom, so
		// the async ``onNew`` still sees them.
		setSubmittedMentions(mentionedDocuments);

		aui.composer().send();
		editorRef.current?.clear();
		setIsComposerInputEmpty(true);
		setMentionedDocuments([]);
	}, [
		showDocumentPopover,
		showPromptPicker,
		isThreadRunning,
		isBlockedByOtherUser,
		clipboardInitialText,
		aui,
		mentionedDocuments,
		setSubmittedMentions,
		setMentionedDocuments,
	]);

	const handleDocumentRemove = useCallback(
		(
			docId: number,
			docType?: string,
			kind?: "doc" | "folder" | "connector" | "thread",
			connectorType?: string
		) => {
			setMentionedDocuments((prev) => {
				const removedKey = getMentionDocKey({
					id: docId,
					document_type: docType,
					kind,
					connector_type: connectorType,
				});
				return prev.filter((doc) => getMentionDocKey(doc) !== removedKey);
			});
		},
		[setMentionedDocuments]
	);

	const handleDocumentsMention = useCallback(
		(mentions: MentionedDocumentInfo[]) => {
			const editorMentionedDocs = editorRef.current?.getMentionedDocuments() ?? [];
			const editorDocKeys = new Set(editorMentionedDocs.map((doc) => getMentionDocKey(doc)));

			for (const mention of mentions) {
				const key = getMentionDocKey(mention);
				if (editorDocKeys.has(key)) continue;
				editorRef.current?.insertMentionChip(mention);
				if (workspaceId) {
					promoteRecentMention(workspaceId, mention);
				}
				// Track within the loop so a duplicate-in-batch can't double-insert.
				editorDocKeys.add(key);
			}

			// Atom is reconciled by ``handleEditorChange`` via the editor's
			// onChange — no second write path here.
			setMentionQuery("");
			setSuggestionAnchorPoint(null);
		},
		[workspaceId]
	);

	useEffect(() => {
		const editor = editorRef.current;
		const nextDocsMap = new Map(mentionedDocuments.map((doc) => [getMentionDocKey(doc), doc]));
		const prevDocsMap = prevMentionedDocsRef.current;

		if (!editor) {
			prevMentionedDocsRef.current = nextDocsMap;
			return;
		}

		const editorKeys = new Set(editor.getMentionedDocuments().map(getMentionDocKey));

		for (const [key, doc] of nextDocsMap) {
			if (prevDocsMap.has(key) || editorKeys.has(key)) continue;
			editor.insertMentionChip(doc, { removeTriggerText: false });
		}

		for (const [key, doc] of prevDocsMap) {
			if (!nextDocsMap.has(key)) {
				editor.removeDocumentChip(
					doc.id,
					doc.kind === "doc" ? doc.document_type : undefined,
					doc.kind,
					doc.kind === "connector" ? doc.connector_type : undefined
				);
			}
		}

		prevMentionedDocsRef.current = nextDocsMap;
	}, [mentionedDocuments]);

	const handleApplySuggestedAction = useCallback(
		(promptText: string) => {
			if (editorRef.current) {
				editorRef.current.setText(promptText);
				aui.composer().setText(promptText);
				setIsComposerInputEmpty(false);
				editorRef.current.focus();
			}
		},
		[aui]
	);

	const threadMessages = useAuiState(({ thread }) => thread.messages);

	const dynamicSuggestedActions = useMemo(() => {
		if (!threadMessages || threadMessages.length === 0) return [];

		let lastAssistantMsg = null;
		for (let i = threadMessages.length - 1; i >= 0; i--) {
			if (threadMessages[i].role === "assistant") {
				lastAssistantMsg = threadMessages[i];
				break;
			}
		}
		if (!lastAssistantMsg) return [];

		// 1. Check data-suggested-actions part
		if (Array.isArray(lastAssistantMsg.content)) {
			for (const part of lastAssistantMsg.content) {
				if (part.type === "data-suggested-actions" && "data" in part) {
					const d = part.data as
						| { actions?: Array<{ label?: string; text?: string; title?: string }> }
						| Array<{ label?: string; text?: string; title?: string }>;
					const arr = Array.isArray(d) ? d : Array.isArray(d?.actions) ? d.actions : [];
					if (arr.length > 0) {
						return arr
							.map((item) =>
								typeof item === "string" ? item : item.label || item.text || item.title
							)
							.filter(Boolean) as string[];
					}
				}
			}

			// 2. Parse suggestions from text
			for (const part of lastAssistantMsg.content) {
				if (part.type === "text" && typeof part.text === "string") {
					const text = part.text;
					const match = text.match(
						/(?:\r?\n|^)#{1,4}\s*(?:Gợi ý bước tiếp theo|Bước tiếp theo đề xuất|Gợi ý hành động|Next steps|Suggested next steps|Next Actions)([\s\S]*)/i
					);
					if (match?.[1]) {
						const lines = match[1].split("\n");
						const extracted: string[] = [];
						for (const line of lines) {
							const trimmed = line.trim();
							if (
								trimmed.startsWith("- ") ||
								trimmed.startsWith("* ") ||
								/^\d+\.\s/.test(trimmed)
							) {
								const clean = trimmed
									.replace(/^[-*]|\d+\.\s*/, "")
									.replace(/\*\*(.*?)\*\*/g, "$1")
									.trim();
								if (clean && clean.length > 5) {
									extracted.push(clean);
								}
							}
						}
						if (extracted.length > 0) return extracted.slice(0, 3);
					}
				}
			}
		}

		// 3. Fallback high-value proactive suggestions for active thread
		return [tChat("default_action_1"), tChat("default_action_2"), tChat("default_action_3")];
	}, [threadMessages, tChat]);

	// Reset dismissal when the assistant emits new suggestions.
	useEffect(() => {
		if (dynamicSuggestedActions.length > 0) {
			setSuggestedCardDismissed(false);
		}
	}, [dynamicSuggestedActions]);

	return (
		<ComposerPrimitive.Root className="aui-composer-root relative flex w-full flex-col gap-2 rounded-2xl">
			<ChatSessionStatus
				isAiResponding={isAiResponding}
				respondingToUserId={respondingToUserId}
				currentUserId={currentUser?.id ?? null}
				members={members ?? []}
			/>

			{/* Nowing: Dynamic Suggested Next Actions Card */}
			{hasActiveThread && dynamicSuggestedActions.length > 0 && !suggestedCardDismissed && (
				<section
					className="rounded-xl border border-border/70 bg-card/95 p-1.5 shadow-2xs transition-all backdrop-blur-xs"
					aria-label={tChat("suggested_actions_title")}
				>
					<div className="flex items-center justify-between px-1.5 pb-1 gap-2">
						<div className="flex items-center gap-1.5 text-[10.5px] font-bold uppercase tracking-wider text-muted-foreground">
							<span className="text-amber-500" aria-hidden="true">
								💡
							</span>
							<span>{tChat("suggested_actions_title")}</span>
						</div>
						<div className="flex items-center gap-1">
							<Sparkles className="size-3 text-muted-foreground opacity-60" aria-hidden="true" />
							<button
								type="button"
								onClick={() => setSuggestedCardDismissed(true)}
								className="rounded p-0.5 text-muted-foreground hover:text-foreground hover:bg-muted/80 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
								aria-label={tChat("dismiss_suggested_actions")}
								title={tChat("dismiss_suggested_actions")}
							>
								<X className="size-3" aria-hidden="true" />
							</button>
						</div>
					</div>
					<ul className="space-y-1 list-none">
						{dynamicSuggestedActions.slice(0, 4).map((actionText, idx) => {
							const icon = idx === 0 ? "🚀" : idx === 1 ? "💼" : idx === 2 ? "📱" : "✨";
							return (
								<li key={actionText}>
									<button
										type="button"
										onClick={() => handleApplySuggestedAction(actionText)}
										className="w-full text-left flex items-center gap-2 px-2.5 py-1.5 rounded-lg hover:bg-muted/70 transition-colors text-xs text-foreground group cursor-pointer border border-transparent hover:border-border/50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
										title={tChat("click_to_prompt_tooltip", { action: actionText })}
									>
										<span
											className="size-4.5 rounded-md bg-muted/80 text-foreground flex items-center justify-center text-[10px] font-bold shrink-0"
											aria-hidden="true"
										>
											{icon}
										</span>
										<span className="leading-tight font-medium text-foreground truncate">
											{actionText}
										</span>
									</button>
								</li>
							);
						})}
					</ul>
				</section>
			)}
			<Popover open={showDocumentPopover} onOpenChange={handleDocumentPopoverOpenChange}>
				{suggestionAnchorPoint ? (
					<>
						<ComposerSuggestionAnchor point={suggestionAnchorPoint} />
						<ComposerSuggestionPopoverContent side="top">
							<DocumentMentionPicker
								ref={documentPickerRef}
								workspaceId={workspaceId ?? 0}
								enableChatMentions
								currentChatId={threadId}
								onSelectionChange={handleDocumentsMention}
								onDone={() => {
									setShowDocumentPopover(false);
									setMentionQuery("");
									setSuggestionAnchorPoint(null);
								}}
								initialSelectedDocuments={mentionedDocuments}
								externalSearch={mentionQuery}
							/>
						</ComposerSuggestionPopoverContent>
					</>
				) : null}
			</Popover>
			<Popover open={showPromptPicker} onOpenChange={handlePromptPickerOpenChange}>
				{suggestionAnchorPoint ? (
					<>
						<ComposerSuggestionAnchor point={suggestionAnchorPoint} />
						<ComposerSuggestionPopoverContent side={clipboardInitialText ? "bottom" : "top"}>
							<PromptPicker
								ref={promptPickerRef}
								onSelect={clipboardInitialText ? handleQuickAskSelect : handleActionSelect}
								onDone={() => {
									setShowPromptPicker(false);
									setActionQuery("");
									setSuggestionAnchorPoint(null);
								}}
								externalSearch={actionQuery}
							/>
						</ComposerSuggestionPopoverContent>
					</>
				) : null}
			</Popover>
			<div className="relative flex w-full flex-col">
				{isChatUnavailable ? (
					<ChatUnavailableNotice
						workspaceId={workspaceId ?? 0}
						canConfigure={chatSetupStatus?.can_configure ?? false}
					/>
				) : null}
				<div
					className={cn(
						"aui-composer-attachment-dropzone relative z-10 flex w-full flex-col overflow-hidden rounded-3xl border border-input/20 bg-muted pt-2 shadow-sm shadow-black/5 outline-none transition-[border-color,box-shadow] hover:border-input/60 focus-within:border-input/60 focus-within:ring-2 focus-within:ring-ring/50 dark:shadow-black/10",
						connectToolsTrayVisible && "rounded-b-3xl shadow-none dark:shadow-none",
						isChatUnavailable && "shadow-none dark:shadow-none"
					)}
				>
					<PendingScreenImageStrip />
					{selectedLeadContext && (
						<div className="mx-4 mt-2 flex items-center justify-between gap-2 rounded-xl bg-emerald-500/10 border border-emerald-500/25 px-3 py-1.5 text-xs text-emerald-800 dark:text-emerald-300 animate-in fade-in slide-in-from-top-1 duration-150">
							<div className="flex items-center gap-2 truncate">
								<span className="font-semibold text-emerald-600 dark:text-emerald-400 shrink-0">
									🎯 Lead Context:
								</span>
								<span className="truncate font-medium">
									{selectedLeadContext.company_name || selectedLeadContext.contact_name}
									{selectedLeadContext.contact_title
										? ` (${selectedLeadContext.contact_title})`
										: ""}
								</span>
								{selectedLeadContext.fit_score !== undefined && (
									<span className="shrink-0 rounded bg-emerald-500/20 px-1.5 py-0.5 text-[10px] font-mono font-bold text-emerald-700 dark:text-emerald-300">
										Fit {selectedLeadContext.fit_score}%
									</span>
								)}
							</div>
							<button
								type="button"
								onClick={() => setSelectedLeadContext(null)}
								className="hover:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 p-1 rounded-md transition-colors"
								title={tChat("dismiss_lead_context")}
								aria-label={tChat("dismiss_lead_context")}
							>
								<X className="w-3.5 h-3.5" aria-hidden="true" />
							</button>
						</div>
					)}
					{clipboardInitialText && (
						<ClipboardChip
							text={clipboardInitialText}
							onDismiss={() => setClipboardInitialText(undefined)}
						/>
					)}
					<div className="aui-composer-input-wrapper px-4 pt-3 pb-2 sm:pb-6">
						<InlineMentionEditor
							ref={editorRef}
							placeholder={currentPlaceholder}
							onMentionTrigger={handleMentionTrigger}
							onMentionClose={handleMentionClose}
							onActionTrigger={handleActionTrigger}
							onActionClose={handleActionClose}
							onChange={handleEditorChange}
							onDocumentRemove={handleDocumentRemove}
							onSubmit={handleSubmit}
							onKeyDown={handleKeyDown}
							data-testid="chat-composer-input"
							className="min-h-[48px] sm:min-h-[24px] **:data-slate-placeholder:font-normal"
						/>
					</div>
					<ComposerAction
						isBlockedByOtherUser={isBlockedByOtherUser}
						workspaceId={workspaceId ?? 0}
						onChatModelSelected={handleChatModelSelected}
					/>
				</div>
				<ConnectToolsBanner
					isThreadEmpty={isThreadEmpty}
					onVisibleChange={setConnectToolsTrayVisible}
				/>
			</div>
		</ComposerPrimitive.Root>
	);
};

"use client";

import { MarkdownPlugin, remarkMdx } from "@platejs/markdown";
import { slateToHtml } from "@slate-serializers/html";
import type { AnyPluginConfig, Descendant, Value } from "platejs";
import { createPlatePlugin, Key, Plate, useEditorReadOnly, usePlateEditor } from "platejs/react";
import { useEffect, useMemo, useRef } from "react";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import { EditorSaveContext } from "@/components/editor/editor-save-context";
import { CitationKit, injectCitationNodes } from "@/components/editor/plugins/citation-kit";
import { type EditorPreset, presetMap } from "@/components/editor/presets";
import { escapeMdxExpressions } from "@/components/editor/utils/escape-mdx";
import { safeDeserializeMarkdown } from "@/components/editor/utils/safe-deserialize";
import { Editor, EditorContainer } from "@/components/ui/editor";
import { preprocessCitationMarkdown } from "@/lib/citations/citation-parser";

/** Live editor instance returned by `usePlateEditor`. */
export type PlateEditorInstance = ReturnType<typeof usePlateEditor>;

export interface PlateEditorProps {
	/** Markdown string to load as initial content */
	markdown?: string;
	/** HTML string to load as initial content. Takes precedence over `markdown`. */
	html?: string;
	/** Called when the editor content changes, with serialized markdown */
	onMarkdownChange?: (markdown: string) => void;
	/** Called when the editor content changes, with serialized HTML. Use with the `html` prop. */
	onHtmlChange?: (html: string) => void;
	/**
	 * Force permanent read-only mode (e.g. public/shared view).
	 * When true, the editor cannot be toggled to editing mode.
	 * When false (default), the editor starts in viewing mode but
	 * the user can switch to editing via the mode toolbar button.
	 */
	readOnly?: boolean;
	/** Placeholder text */
	placeholder?: string;
	/** Editor container variant */
	variant?: "default" | "demo" | "comment" | "select";
	/** Editor text variant */
	editorVariant?: "default" | "demo" | "fullWidth" | "none";
	/** Additional className for the container */
	className?: string;
	/** Save callback. When provided, ⌘+Shift+S / Ctrl+Shift+S shortcut is registered (avoiding the browser's ⌘+S / Ctrl+S "Save Page As" conflict) and a save button appears in the toolbar. */
	onSave?: () => void;
	/** Whether there are unsaved changes */
	hasUnsavedChanges?: boolean;
	/** Whether a save is in progress */
	isSaving?: boolean;
	/** Whether edit/view mode toggle UI should be available in toolbars. */
	allowModeToggle?: boolean;
	/** Reserve fixed-toolbar vertical space even when controls are hidden. */
	reserveToolbarSpace?: boolean;
	/** Start the editor in editing mode instead of viewing mode. Ignored when readOnly is true. */
	defaultEditing?: boolean;
	/**
	 * Plugin preset to use. Controls which plugin kits are loaded.
	 * - "full"     – all plugins (toolbars, slash commands, DnD, etc.)
	 * - "minimal"  – core formatting only (no fixed toolbar, slash commands, DnD, block selection)
	 * - "readonly" – rendering support for all rich content, no editing UI
	 * @default "full"
	 */
	preset?: EditorPreset;
	/**
	 * Additional plugins to append after the preset plugins.
	 * Use this to inject feature-specific plugins (e.g. approve/reject blocks)
	 * without modifying the core editor component.
	 */
	extraPlugins?: AnyPluginConfig[];
	/**
	 * Render `[citation:N]` and `[citation:URL]` tokens in the deserialized
	 * markdown as interactive citation badges/popovers (mirrors chat). Only
	 * meant for read-only views — when true, `onMarkdownChange` is suppressed
	 * because the in-memory tree contains custom inline-void elements that
	 * have no markdown serialize rule.
	 */
	enableCitations?: boolean;
	/** Text to scroll into view and highlight (best-effort via DOM selection). */
	highlightText?: string;
	/** Optional proportional position for fallback scrolling when the exact text is not found. */
	highlightPosition?: number;
	/** Total chunk count used with highlightPosition. */
	totalChunks?: number;
}

function PlateEditorContent({
	editorVariant,
	placeholder,
}: {
	editorVariant: PlateEditorProps["editorVariant"];
	placeholder?: string;
}) {
	const isReadOnly = useEditorReadOnly();

	return (
		<Editor
			variant={editorVariant}
			placeholder={isReadOnly ? undefined : placeholder}
			className="min-h-full"
		/>
	);
}

export function PlateEditor({
	markdown,
	html,
	onMarkdownChange,
	onHtmlChange,
	readOnly = false,
	placeholder = "Type...",
	variant = "default",
	editorVariant = "default",
	className,
	onSave,
	hasUnsavedChanges = false,
	isSaving = false,
	allowModeToggle = true,
	reserveToolbarSpace = false,
	defaultEditing = false,
	preset = "full",
	extraPlugins = [],
	enableCitations = false,
	highlightText,
	highlightPosition,
	totalChunks,
}: PlateEditorProps) {
	const lastMarkdownRef = useRef(markdown);
	const lastHtmlRef = useRef(html);
	const highlightContainerRef = useRef<HTMLDivElement>(null);
	const highlightTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
	const highlightedElementRef = useRef<HTMLElement | null>(null);

	// Keep a stable ref to the latest onSave callback so the plugin shortcut
	// always calls the most recent version without re-creating the editor.
	const onSaveRef = useRef(onSave);
	useEffect(() => {
		onSaveRef.current = onSave;
	}, [onSave]);

	const SaveShortcutPlugin = useMemo(
		() =>
			createPlatePlugin({
				key: "save-shortcut",
				shortcuts: {
					save: {
						keys: [[Key.Mod, Key.Shift, "s"]],
						handler: () => {
							onSaveRef.current?.();
						},
						preventDefault: true,
					},
				},
			}),
		[]
	);

	// ponytail: DOM-based highlight/scroll for a citation chunk. This is a
	// best-effort heuristic: the chunk text is the raw source substring, but
	// Plate deserializes markdown into Slate text nodes, so markers like `#`
	// are stripped. We search rendered text nodes; if found, select and scroll.
	// A more robust mapping would require Slate-aware chunk offsets (upgrade path).
	useEffect(() => {
		if (!highlightText || !highlightContainerRef.current) return;
		const target = highlightText.trim();
		if (!target) return;
		const container = highlightContainerRef.current;

		const clearHighlight = () => {
			if (highlightTimeoutRef.current) {
				clearTimeout(highlightTimeoutRef.current);
				highlightTimeoutRef.current = null;
			}
			if (highlightedElementRef.current) {
				highlightedElementRef.current.classList.remove("bg-yellow-200", "dark:bg-yellow-800");
				highlightedElementRef.current = null;
			}
			const selection = window.getSelection();
			if (selection) selection.removeAllRanges();
		};

		let timeoutId: ReturnType<typeof setTimeout> | null = null;
		let attempts = 0;
		const MAX_ATTEMPTS = 20;

		const tryHighlight = () => {
			timeoutId = setTimeout(() => {
				const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
				let matchNode: Text | null = null;
				let matchOffset = -1;
				while (walker.nextNode()) {
					const node = walker.currentNode as Text;
					const text = node.textContent ?? "";
					const idx = text.indexOf(target);
					if (idx >= 0) {
						matchNode = node;
						matchOffset = idx;
						break;
					}
				}

				if (!matchNode) {
					// Proportional fallback: scroll to the text node nearest the expected position.
					if (highlightPosition === undefined || totalChunks === undefined || totalChunks <= 0)
						return;
					const fullText = container.textContent ?? "";
					if (!fullText) {
						if (attempts < MAX_ATTEMPTS) {
							attempts += 1;
							timeoutId = setTimeout(tryHighlight, 50);
						}
						return;
					}
					const safePosition = Math.max(0, highlightPosition);
					const safeTotal = Math.max(1, totalChunks - 1);
					const targetRatio = Math.max(0, Math.min(1, safePosition / safeTotal));
					const targetOffset = Math.floor(targetRatio * (fullText.length - 1));
					let accumulated = 0;
					walker.currentNode = container; // reset walker
					while (walker.nextNode()) {
						const node = walker.currentNode as Text;
						const text = node.textContent ?? "";
						if (accumulated + text.length > targetOffset) {
							matchNode = node;
							matchOffset = Math.max(0, targetOffset - accumulated);
							break;
						}
						accumulated += text.length;
					}
				}

				if (!matchNode) return;
				const range = document.createRange();
				range.setStart(matchNode, matchOffset);
				range.setEnd(
					matchNode,
					Math.min(matchOffset + target.length, matchNode.textContent?.length ?? 0)
				);
				const selection = window.getSelection();
				if (selection) {
					selection.removeAllRanges();
					selection.addRange(range);
				}

				const element = matchNode.parentElement;
				if (element) {
					element.scrollIntoView({ behavior: "auto", block: "center" });
					element.classList.add("bg-yellow-200", "dark:bg-yellow-800");
					highlightedElementRef.current = element;
				}

				highlightTimeoutRef.current = setTimeout(() => {
					clearHighlight();
				}, 3000);
			}, 0);
		};

		timeoutId = setTimeout(tryHighlight, 100);

		return () => {
			if (timeoutId) {
				clearTimeout(timeoutId);
			}
			clearHighlight();
		};
	}, [highlightText, highlightPosition, totalChunks]);

	// Resolve the plugin set from the chosen preset
	const presetPlugins = presetMap[preset];

	// When readOnly is forced, always start in readOnly.
	// Otherwise, respect defaultEditing to decide initial mode.
	// The user can still toggle between editing/viewing via ModeToolbarButton.
	const editor = usePlateEditor({
		readOnly: readOnly || !defaultEditing,
		plugins: [
			...presetPlugins,
			// Only register save shortcut when a save handler is provided
			...(onSave ? [SaveShortcutPlugin] : []),
			// Consumer-provided extra plugins
			...extraPlugins,
			// Citation void inline element (read-only document viewer).
			...(enableCitations ? CitationKit : []),
			MarkdownPlugin.configure({
				options: {
					remarkPlugins: [remarkGfm, remarkMath, remarkMdx],
				},
			}),
		],
		value: html
			? (editor) => editor.api.html.deserialize({ element: html }) as Value
			: markdown
				? (editor) => {
						if (!enableCitations) {
							return safeDeserializeMarkdown(editor, escapeMdxExpressions(markdown)) as Value;
						}
						const { content: rewritten, urlMap } = preprocessCitationMarkdown(markdown);
						const value = safeDeserializeMarkdown(editor, escapeMdxExpressions(rewritten));
						return injectCitationNodes(value, urlMap) as Value;
					}
				: undefined,
	});

	// Update editor content when html prop changes externally
	useEffect(() => {
		if (html !== undefined && html !== lastHtmlRef.current) {
			lastHtmlRef.current = html;
			const newValue = editor.api.html.deserialize({ element: html });
			editor.tf.reset();
			editor.tf.setValue(newValue);
		}
	}, [html, editor]);

	// Update editor content when markdown prop changes externally
	// (e.g., version switching in report panel)
	useEffect(() => {
		if (!html && markdown !== undefined && markdown !== lastMarkdownRef.current) {
			lastMarkdownRef.current = markdown;
			let newValue: Descendant[];
			if (enableCitations) {
				const { content: rewritten, urlMap } = preprocessCitationMarkdown(markdown);
				const deserialized = safeDeserializeMarkdown(editor, escapeMdxExpressions(rewritten));
				newValue = injectCitationNodes(deserialized, urlMap);
			} else {
				newValue = safeDeserializeMarkdown(editor, escapeMdxExpressions(markdown));
			}
			editor.tf.reset();
			editor.tf.setValue(newValue as Value);
		}
	}, [html, markdown, editor, enableCitations]);

	// When not forced read-only, the user can toggle between editing/viewing.
	const canToggleMode = !readOnly && allowModeToggle;

	const contextProviderValue = useMemo(
		() => ({
			onSave,
			hasUnsavedChanges,
			isSaving,
			canToggleMode,
			reserveToolbarSpace,
		}),
		[onSave, hasUnsavedChanges, isSaving, canToggleMode, reserveToolbarSpace]
	);

	return (
		<EditorSaveContext.Provider value={contextProviderValue}>
			<div ref={highlightContainerRef} className="h-full min-h-0">
				<Plate
					editor={editor}
					// Only pass readOnly as a controlled prop when forced (permanently read-only).
					// For non-forced mode, the Plate store manages readOnly internally
					// (initialized to true via usePlateEditor, toggled via ModeToolbarButton).
					{...(readOnly ? { readOnly: true } : {})}
					onChange={({ value }) => {
						// View-only citation mode: skip serialization. The custom
						// `citation` inline-void element has no markdown serialize
						// rule, so emitting changes here would overwrite
						// `lastMarkdownRef.current` (and downstream copy-to-clipboard
						// state in EditorPanelContent) with a tree that loses every
						// citation token. `enableCitations` is only ever set in
						// read-only paths, so user input cannot reach this branch
						// in practice — the guard exists for the initial Plate
						// normalize emit.
						if (enableCitations) return;
						if (onHtmlChange && html) {
							const serialized = slateToHtml(value as Descendant[]);
							onHtmlChange(serialized);
						} else if (onMarkdownChange) {
							const md = editor.getApi(MarkdownPlugin).markdown.serialize({ value });
							lastMarkdownRef.current = md;
							onMarkdownChange(md);
						}
					}}
				>
					<EditorContainer variant={variant} className={className}>
						<PlateEditorContent editorVariant={editorVariant} placeholder={placeholder} />
					</EditorContainer>
				</Plate>
			</div>
		</EditorSaveContext.Provider>
	);
}

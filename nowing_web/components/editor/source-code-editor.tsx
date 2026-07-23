"use client";

import dynamic from "next/dynamic";
import { useTheme } from "next-themes";
import { useCallback, useEffect, useRef } from "react";
import { Spinner } from "@/components/ui/spinner";

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), {
	ssr: false,
});

interface SourceCodeEditorProps {
	value: string;
	onChange: (next: string) => void;
	path?: string;
	language?: string;
	readOnly?: boolean;
	fontSize?: number;
	onSave?: () => Promise<void> | void;
	highlightText?: string;
	highlightOffset?: number;
	highlightLength?: number;
	highlightPosition?: number;
	totalChunks?: number;
}

function offsetToLineColumn(text: string, offset: number): { line: number; column: number } {
	let line = 1;
	let column = 1;
	for (let i = 0; i < offset && i < text.length; i++) {
		const char = text[i];
		if (char === "\n" || char === "\r") {
			line++;
			column = 1;
			if (char === "\r" && text[i + 1] === "\n") {
				i++;
			}
		} else {
			column++;
		}
	}
	return { line, column };
}

export function SourceCodeEditor({
	value,
	onChange,
	path,
	language = "plaintext",
	readOnly = false,
	fontSize = 12,
	onSave,
	highlightText,
	highlightOffset,
	highlightLength,
	highlightPosition,
	totalChunks,
}: SourceCodeEditorProps) {
	const { resolvedTheme } = useTheme();
	const onSaveRef = useRef(onSave);
	const monacoRef = useRef<any>(null);
	const editorRef = useRef<any>(null);
	const highlightDecorationRef = useRef<string[]>([]);
	const highlightTextRef = useRef(highlightText);
	const highlightOffsetRef = useRef(highlightOffset);
	const highlightLengthRef = useRef(highlightLength);
	const highlightPositionRef = useRef(highlightPosition);
	const totalChunksRef = useRef(totalChunks);
	const layoutListenerRef = useRef<{ dispose: () => void } | null>(null);
	const highlightTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
	const normalizedModelPath = (() => {
		const raw = (path || "local-file.txt").trim();
		const withLeadingSlash = raw.startsWith("/") ? raw : `/${raw}`;
		// Monaco model paths should be stable and POSIX-like across platforms.
		return withLeadingSlash.replace(/\\/g, "/").replace(/\/{2,}/g, "/");
	})();

	useEffect(() => {
		onSaveRef.current = onSave;
	}, [onSave]);

	const resolveCssColorToHex = (cssColorValue: string): string | null => {
		if (typeof document === "undefined") return null;
		const probe = document.createElement("div");
		probe.style.color = cssColorValue;
		probe.style.position = "absolute";
		probe.style.pointerEvents = "none";
		probe.style.opacity = "0";
		document.body.appendChild(probe);
		const computedColor = getComputedStyle(probe).color;
		probe.remove();
		const match = computedColor.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
		if (!match) return null;
		const toHex = (value: string) => Number(value).toString(16).padStart(2, "0");
		return `#${toHex(match[1])}${toHex(match[2])}${toHex(match[3])}`;
	};

	const applySidebarTheme = (monaco: any) => {
		const isDark = resolvedTheme === "dark";
		const themeName = isDark ? "nowing-dark" : "nowing-light";
		const fallbackBg = isDark ? "#1e1e1e" : "#ffffff";
		const sidebarBgHex = resolveCssColorToHex("var(--sidebar)") ?? fallbackBg;
		monaco.editor.defineTheme(themeName, {
			base: isDark ? "vs-dark" : "vs",
			inherit: true,
			rules: [],
			colors: {
				"editor.background": sidebarBgHex,
				"editorGutter.background": sidebarBgHex,
				"minimap.background": sidebarBgHex,
				"editorLineNumber.background": sidebarBgHex,
				"editor.lineHighlightBackground": "#00000000",
			},
		});
		monaco.editor.setTheme(themeName);
	};

	useEffect(() => {
		if (!monacoRef.current) return;
		applySidebarTheme(monacoRef.current);
	}, [resolvedTheme]);

	const clearHighlight = useCallback((editor: any, monaco: any) => {
		if (!editor || !monaco) return;
		if (highlightTimeoutRef.current) {
			clearTimeout(highlightTimeoutRef.current);
			highlightTimeoutRef.current = null;
		}
		highlightDecorationRef.current = editor.deltaDecorations(highlightDecorationRef.current, []);
	}, []);

	const applyHighlight = useCallback((editor: any, monaco: any, { layoutOnly = false }: { layoutOnly?: boolean } = {}) => {
		if (!editor || !monaco) return;
		const model = editor.getModel();
		if (!model) return;

		// Layout-only re-applications should not resurrect a highlight that has already
		// auto-cleared.
		if (layoutOnly && highlightTimeoutRef.current === null) {
			return;
		}

		const currentHighlightText = highlightTextRef.current ?? "";
		const currentHighlightOffset = highlightOffsetRef.current ?? -1;
		const currentHighlightLength = highlightLengthRef.current ?? 0;
		const currentHighlightPosition = highlightPositionRef.current;
		const currentTotalChunks = totalChunksRef.current;

		const hasHighlight =
			currentHighlightOffset >= 0 ||
			(currentHighlightText.length > 0 &&
				(currentHighlightPosition === undefined || currentTotalChunks === undefined || currentTotalChunks > 0));
		if (!hasHighlight) {
			clearHighlight(editor, monaco);
			return;
		}

		// On a real highlight change, reset the auto-clear timer and clear old decoration.
		if (!layoutOnly) {
			if (highlightTimeoutRef.current) {
				clearTimeout(highlightTimeoutRef.current);
			}
			highlightDecorationRef.current = editor.deltaDecorations(highlightDecorationRef.current, []);
		}

		const text = model.getValue();

		let startLine = 1;
		let startColumn = 1;
		let endLine = 1;
		let endColumn = 1;

		if (currentHighlightOffset >= 0) {
			({ line: startLine, column: startColumn } = offsetToLineColumn(text, currentHighlightOffset));
			if (currentHighlightLength > 0) {
				({ line: endLine, column: endColumn } = offsetToLineColumn(
					text,
					currentHighlightOffset + currentHighlightLength
				));
			} else {
				endLine = startLine;
				endColumn = startColumn;
			}
		} else if (currentHighlightText.length > 0) {
			const idx = text.indexOf(currentHighlightText);
			if (idx >= 0) {
				({ line: startLine, column: startColumn } = offsetToLineColumn(text, idx));
				({ line: endLine, column: endColumn } = offsetToLineColumn(
					text,
					idx + currentHighlightText.length
				));
			} else if (
				currentHighlightPosition !== undefined &&
				currentTotalChunks !== undefined &&
				currentTotalChunks > 0
			) {
				const lineCount = model.getLineCount() ?? 1;
				const safePosition = Math.max(0, currentHighlightPosition);
				const safeTotal = Math.max(1, currentTotalChunks - 1);
				startLine = Math.max(
					1,
					Math.min(
						lineCount,
						Math.floor((safePosition / safeTotal) * (lineCount - 1)) + 1
					)
				);
				endLine = startLine;
				endColumn = startColumn;
			} else {
				// Highlight target is not present in the current model value yet.
				return;
			}
		}

		const range = new monaco.Range(startLine, startColumn, endLine, endColumn);

		if (!layoutOnly) {
			editor.revealRangeInCenter(range);
			editor.setSelection(range);
		}

		const isCollapsed = range.startLineNumber === range.endLineNumber && range.startColumn === range.endColumn;
		highlightDecorationRef.current = editor.deltaDecorations(highlightDecorationRef.current, [
			{
				range,
				options: {
					className: "bg-yellow-200 dark:bg-yellow-800",
					isWholeLine: isCollapsed,
					inlineClassName: "bg-yellow-200 dark:bg-yellow-800",
				},
			},
		]);

		if (!layoutOnly) {
			highlightTimeoutRef.current = setTimeout(() => {
				clearHighlight(editor, monaco);
				highlightTimeoutRef.current = null;
			}, 3000);
		}
	}, [clearHighlight]);

	useEffect(() => {
		highlightTextRef.current = highlightText;
		highlightOffsetRef.current = highlightOffset;
		highlightLengthRef.current = highlightLength;
		highlightPositionRef.current = highlightPosition;
		totalChunksRef.current = totalChunks;

		const editor = editorRef.current;
		const monaco = monacoRef.current;
		if (editor && monaco) {
			applyHighlight(editor, monaco);
		}
	}, [highlightText, highlightOffset, highlightLength, highlightPosition, totalChunks, applyHighlight]);

	useEffect(() => {
		return () => {
			layoutListenerRef.current?.dispose();
			layoutListenerRef.current = null;
			if (highlightTimeoutRef.current) {
				clearTimeout(highlightTimeoutRef.current);
				highlightTimeoutRef.current = null;
			}
		};
	}, []);

	const isManualSaveEnabled = !!onSave && !readOnly;

	return (
		<div className="h-full w-full overflow-hidden bg-sidebar [&_.monaco-editor]:!bg-sidebar [&_.monaco-editor_.margin]:!bg-sidebar [&_.monaco-editor_.monaco-editor-background]:!bg-sidebar [&_.monaco-editor-background]:!bg-sidebar [&_.monaco-scrollable-element_.scrollbar_.slider]:rounded-full [&_.monaco-scrollable-element_.scrollbar_.slider]:bg-foreground/25 [&_.monaco-scrollable-element_.scrollbar_.slider:hover]:bg-foreground/40">
			<MonacoEditor
				path={normalizedModelPath}
				language={language}
				value={value}
				theme={resolvedTheme === "dark" ? "nowing-dark" : "nowing-light"}
				onChange={(next) => onChange(next ?? "")}
				loading={
					<div className="flex h-full w-full items-center justify-center">
						<Spinner size="md" className="text-muted-foreground" />
					</div>
				}
				beforeMount={(monaco) => {
					monacoRef.current = monaco;
					applySidebarTheme(monaco);
				}}
				onMount={(editor, monaco) => {
					editorRef.current = editor;
					monacoRef.current = monaco;
					applySidebarTheme(monaco);

					layoutListenerRef.current = editor.onDidLayoutChange(() => {
						applyHighlight(editor, monaco, { layoutOnly: true });
					});
					applyHighlight(editor, monaco);

					if (!isManualSaveEnabled) return;
					editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
						void onSaveRef.current?.();
					});
				}}
				options={{
					automaticLayout: true,
					minimap: { enabled: false },
					lineNumbers: "on",
					lineNumbersMinChars: 4,
					lineDecorationsWidth: 20,
					glyphMargin: false,
					folding: false,
					overviewRulerLanes: 0,
					hideCursorInOverviewRuler: true,
					scrollBeyondLastLine: false,
					renderLineHighlight: "none",
					selectionHighlight: false,
					occurrencesHighlight: "off",
					quickSuggestions: false,
					suggestOnTriggerCharacters: false,
					acceptSuggestionOnEnter: "off",
					parameterHints: { enabled: false },
					wordBasedSuggestions: "off",
					wordWrap: "off",
					scrollbar: {
						vertical: "auto",
						horizontal: "auto",
						verticalScrollbarSize: 8,
						horizontalScrollbarSize: 8,
						alwaysConsumeMouseWheel: false,
					},
					tabSize: 2,
					insertSpaces: true,
					fontSize,
					fontFamily:
						"ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, Liberation Mono, monospace",
					renderWhitespace: "none",
					renderValidationDecorations: "off",
					colorDecorators: false,
					codeLens: false,
					hover: { enabled: false },
					stickyScroll: { enabled: false },
					unicodeHighlight: {
						ambiguousCharacters: false,
						invisibleCharacters: false,
						nonBasicASCII: false,
					},
					smoothScrolling: true,
					readOnly,
				}}
			/>
		</div>
	);
}

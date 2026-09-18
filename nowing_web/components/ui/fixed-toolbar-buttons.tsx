import { useTranslations } from "next-intl";
"use client";

import {
	BoldIcon,
	Code2Icon,
	HighlighterIcon,
	ItalicIcon,
	RedoIcon,
	SaveIcon,
	StrikethroughIcon,
	UnderlineIcon,
	UndoIcon,
} from "lucide-react";
import { KEYS } from "platejs";
import { useEditorReadOnly, useEditorRef } from "platejs/react";

import { useEditorSave } from "@/components/editor/editor-save-context";
import { ShortcutKbd } from "@/components/ui/shortcut-kbd";
import { Spinner } from "@/components/ui/spinner";
import { usePlatformShortcut } from "@/hooks/use-platform-shortcut";

import { InsertToolbarButton } from "./insert-toolbar-button";
import { LinkToolbarButton } from "./link-toolbar-button";
import { MarkToolbarButton } from "./mark-toolbar-button";
import { ModeToolbarButton } from "./mode-toolbar-button";
import { ToolbarButton, ToolbarGroup } from "./toolbar";
import { TurnIntoToolbarButton } from "./turn-into-toolbar-button";

function TooltipWithShortcut({ label, keys }: { label: string; keys: string[] }) {
	const t = useTranslations("ui");
	return (
		<span className="flex items-center">
			{label}
			<ShortcutKbd keys={keys} />
		</span>
	);
}

export function FixedToolbarButtons() {
	const t = useTranslations("ui");	const readOnly = useEditorReadOnly();
	const editor = useEditorRef();
	const { onSave, hasUnsavedChanges, isSaving, canToggleMode } = useEditorSave();
	const { shortcutKeys } = usePlatformShortcut();

	return (
		<div className="flex w-full items-center">
			{/* Scrollable editing buttons */}
			<div className="flex flex-1 min-w-0 overflow-x-auto scrollbar-hide">
				{!readOnly && (
					<>
						<ToolbarGroup>
							<ToolbarButton
								tooltip={<TooltipWithShortcut label={t("ui_undo")} keys={shortcutKeys("Mod", "Z")} />}
								onClick={() => {
									editor.undo();
									editor.tf.focus();
								}}
							>
								<UndoIcon />
							</ToolbarButton>

							<ToolbarButton
								tooltip={
									<TooltipWithShortcut label={t("ui_redo")} keys={shortcutKeys("Mod", "Shift", "Z")} />
								}
								onClick={() => {
									editor.redo();
									editor.tf.focus();
								}}
							>
								<RedoIcon />
							</ToolbarButton>
						</ToolbarGroup>

						<ToolbarGroup>
							<InsertToolbarButton />
							<TurnIntoToolbarButton />
						</ToolbarGroup>

						<ToolbarGroup>
							<MarkToolbarButton
								nodeType={KEYS.bold}
								tooltip={<TooltipWithShortcut label={t("ui_bold")} keys={shortcutKeys("Mod", "B")} />}
							>
								<BoldIcon />
							</MarkToolbarButton>

							<MarkToolbarButton
								nodeType={KEYS.italic}
								tooltip={<TooltipWithShortcut label={t("ui_italic")} keys={shortcutKeys("Mod", "I")} />}
							>
								<ItalicIcon />
							</MarkToolbarButton>

							<MarkToolbarButton
								nodeType={KEYS.underline}
								tooltip={<TooltipWithShortcut label={t("ui_underline")} keys={shortcutKeys("Mod", "U")} />}
							>
								<UnderlineIcon />
							</MarkToolbarButton>

							<MarkToolbarButton
								nodeType={KEYS.strikethrough}
								tooltip={
									<TooltipWithShortcut
										label={t("ui_strikethrough")}
										keys={shortcutKeys("Mod", "Shift", "X")}
									/>
								}
							>
								<StrikethroughIcon />
							</MarkToolbarButton>

							<MarkToolbarButton
								nodeType={KEYS.code}
								tooltip={<TooltipWithShortcut label={t("ui_code")} keys={shortcutKeys("Mod", "E")} />}
							>
								<Code2Icon />
							</MarkToolbarButton>

							<MarkToolbarButton
								nodeType={KEYS.highlight}
								tooltip={
									<TooltipWithShortcut label={t("ui_highlight")} keys={shortcutKeys("Mod", "Shift", "H")} />
								}
							>
								<HighlighterIcon />
							</MarkToolbarButton>
						</ToolbarGroup>

						<ToolbarGroup>
							<LinkToolbarButton />
						</ToolbarGroup>
					</>
				)}
			</div>

			{/* Fixed right-side buttons (Save + Mode) */}
			<div className="flex shrink-0 items-center">
				{/* Save button — only in edit mode with unsaved changes */}
				{!readOnly && onSave && hasUnsavedChanges && (
					<ToolbarGroup>
						<ToolbarButton
							tooltip={
								isSaving ? (
									"Saving..."
								) : (
									<TooltipWithShortcut label={t("ui_save")} keys={shortcutKeys("Mod", "Shift", "S")} />
								)
							}
							onClick={onSave}
							disabled={isSaving}
							className="bg-primary text-primary-foreground hover:bg-primary/90"
						>
							{isSaving ? <Spinner size="xs" /> : <SaveIcon />}
						</ToolbarButton>
					</ToolbarGroup>
				)}

				{/* Mode toggle */}
				{canToggleMode && (
					<ToolbarGroup>
						<ModeToolbarButton />
					</ToolbarGroup>
				)}
			</div>
		</div>
	);
}

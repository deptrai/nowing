"use client";
import { useTranslations } from "next-intl";

import type { DropdownMenuProps } from "@radix-ui/react-dropdown-menu";
import {
	ChevronRightIcon,
	FileCodeIcon,
	Heading1Icon,
	Heading2Icon,
	Heading3Icon,
	InfoIcon,
	ListIcon,
	ListOrderedIcon,
	MinusIcon,
	PilcrowIcon,
	PlusIcon,
	QuoteIcon,
	RadicalIcon,
	SquareIcon,
	SubscriptIcon,
	SuperscriptIcon,
	TableIcon,
} from "lucide-react";
import { KEYS } from "platejs";
import { type PlateEditor, useEditorRef } from "platejs/react";
import * as React from "react";
import { insertBlock, insertInlineElement } from "@/components/editor/transforms";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

import { ToolbarButton, ToolbarMenuGroup } from "./toolbar";

type Group = {
	group: string;
	items: Item[];
};

type Item = {
	icon: React.ReactNode;
	value: string;
	onSelect: (editor: PlateEditor, value: string) => void;
	focusEditor?: boolean;
	label?: string;
};

const getGroups = (t: (k: string) => string): Group[] => [
	{
		group: t("group_basic"),
		items: [
			{
				icon: <PilcrowIcon />,
				label: t("ui_paragraph"),
				value: KEYS.p,
			},
			{
				icon: <Heading1Icon />,
				label: t("ui_heading_1"),
				value: "h1",
			},
			{
				icon: <Heading2Icon />,
				label: t("ui_heading_2"),
				value: "h2",
			},
			{
				icon: <Heading3Icon />,
				label: t("ui_heading_3"),
				value: "h3",
			},
			{
				icon: <TableIcon />,
				label: t("ui_table"),
				value: KEYS.table,
			},
			{
				icon: <FileCodeIcon />,
				label: t("ui_code_block"),
				value: KEYS.codeBlock,
			},
			{
				icon: <QuoteIcon />,
				label: t("ui_quote"),
				value: KEYS.blockquote,
			},
			{
				icon: <MinusIcon />,
				label: t("ui_divider"),
				value: KEYS.hr,
			},
		].map((item) => ({
			...item,
			onSelect: (editor: PlateEditor, value: string) => {
				insertBlock(editor, value);
			},
		})),
	},
	{
		group: t("group_lists"),
		items: [
			{
				icon: <ListIcon />,
				label: t("ui_bulleted_list"),
				value: KEYS.ul,
			},
			{
				icon: <ListOrderedIcon />,
				label: t("ui_numbered_list"),
				value: KEYS.ol,
			},
			{
				icon: <SquareIcon />,
				label: t("ui_to_do_list"),
				value: KEYS.listTodo,
			},
			{
				icon: <ChevronRightIcon />,
				label: t("ui_toggle_list"),
				value: KEYS.toggle,
			},
		].map((item) => ({
			...item,
			onSelect: (editor: PlateEditor, value: string) => {
				insertBlock(editor, value);
			},
		})),
	},
	{
		group: t("group_advanced"),
		items: [
			{
				icon: <InfoIcon />,
				label: t("ui_callout"),
				value: KEYS.callout,
			},
			{
				focusEditor: false,
				icon: <RadicalIcon />,
				label: t("ui_equation"),
				value: KEYS.equation,
			},
		].map((item) => ({
			...item,
			onSelect: (editor: PlateEditor, value: string) => {
				if (item.value === KEYS.equation) {
					insertInlineElement(editor, value);
				} else {
					insertBlock(editor, value);
				}
			},
		})),
	},
	{
		group: t("group_marks"),
		items: [
			{
				icon: <SuperscriptIcon />,
				label: t("ui_superscript"),
				value: KEYS.sup,
			},
			{
				icon: <SubscriptIcon />,
				label: t("ui_subscript"),
				value: KEYS.sub,
			},
		].map((item) => ({
			...item,
			onSelect: (editor: PlateEditor, value: string) => {
				editor.tf.toggleMark(value, {
					remove: value === KEYS.sup ? KEYS.sub : KEYS.sup,
				});
			},
		})),
	},
];

export function InsertToolbarButton(props: DropdownMenuProps) {
	const t = useTranslations("ui");	const editor = useEditorRef();
	const [open, setOpen] = React.useState(false);

	return (
		<DropdownMenu open={open} onOpenChange={setOpen} modal={false} {...props}>
			<DropdownMenuTrigger asChild>
				<ToolbarButton pressed={open} tooltip={t("ui_insert")} isDropdown>
					<PlusIcon />
				</ToolbarButton>
			</DropdownMenuTrigger>

			<DropdownMenuContent
				className="z-[100] flex max-h-[60vh] min-w-0 flex-col overflow-y-auto"
				align="start"
			>
				{getGroups(t).map(({ group, items }) => (
					<React.Fragment key={group}>
						<ToolbarMenuGroup label={group}>
							{items.map(({ icon, label, value, onSelect, focusEditor }) => (
								<DropdownMenuItem
									key={value}
									onSelect={() => {
										onSelect(editor, value);
										if (focusEditor !== false) {
											editor.tf.focus();
										}
										setOpen(false);
									}}
									className="group"
								>
									<div className="flex items-center text-sm dark:text-white text-muted-foreground focus:text-accent-foreground group-aria-selected:text-accent-foreground">
										{icon}
										<span className="ml-2">{label || value}</span>
									</div>
								</DropdownMenuItem>
							))}
						</ToolbarMenuGroup>
					</React.Fragment>
				))}
			</DropdownMenuContent>
		</DropdownMenu>
	);
}

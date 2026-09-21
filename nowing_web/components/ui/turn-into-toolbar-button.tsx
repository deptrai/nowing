"use client";

import type { DropdownMenuProps } from "@radix-ui/react-dropdown-menu";
import { DropdownMenuItemIndicator } from "@radix-ui/react-dropdown-menu";
import {
	CheckIcon,
	ChevronRightIcon,
	FileCodeIcon,
	Heading1Icon,
	Heading2Icon,
	Heading3Icon,
	Heading4Icon,
	Heading5Icon,
	Heading6Icon,
	InfoIcon,
	ListIcon,
	ListOrderedIcon,
	PilcrowIcon,
	QuoteIcon,
	SquareIcon,
} from "lucide-react";
import { useTranslations } from "next-intl";
import type { TElement } from "platejs";
import { KEYS } from "platejs";
import { useEditorRef, useSelectionFragmentProp } from "platejs/react";
import * as React from "react";
import { getBlockType, setBlockType } from "@/components/editor/transforms";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuRadioItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

import { ToolbarButton, ToolbarMenuGroup } from "./toolbar";

export const getTurnIntoItems = (t: (k: string) => string) => [
	{
		icon: <PilcrowIcon />,
		keywords: ["paragraph"],
		label: t("ui_text"),
		value: KEYS.p,
	},
	{
		icon: <Heading1Icon />,
		keywords: ["title", "h1"],
		label: t("ui_heading_1"),
		value: "h1",
	},
	{
		icon: <Heading2Icon />,
		keywords: ["subtitle", "h2"],
		label: t("ui_heading_2"),
		value: "h2",
	},
	{
		icon: <Heading3Icon />,
		keywords: ["subtitle", "h3"],
		label: t("ui_heading_3"),
		value: "h3",
	},
	{
		icon: <Heading4Icon />,
		keywords: ["subtitle", "h4"],
		label: t("ui_heading_4"),
		value: "h4",
	},
	{
		icon: <Heading5Icon />,
		keywords: ["subtitle", "h5"],
		label: t("ui_heading_5"),
		value: "h5",
	},
	{
		icon: <Heading6Icon />,
		keywords: ["subtitle", "h6"],
		label: t("ui_heading_6"),
		value: "h6",
	},
	{
		icon: <ListIcon />,
		keywords: ["unordered", "ul", "-"],
		label: t("ui_bulleted_list"),
		value: KEYS.ul,
	},
	{
		icon: <ListOrderedIcon />,
		keywords: ["ordered", "ol", "1"],
		label: t("ui_numbered_list"),
		value: KEYS.ol,
	},
	{
		icon: <SquareIcon />,
		keywords: ["checklist", "task", "checkbox", "[]"],
		label: t("ui_to_do_list"),
		value: KEYS.listTodo,
	},
	{
		icon: <FileCodeIcon />,
		keywords: ["```"],
		label: t("ui_code"),
		value: KEYS.codeBlock,
	},
	{
		icon: <QuoteIcon />,
		keywords: ["citation", "blockquote", ">"],
		label: t("ui_quote"),
		value: KEYS.blockquote,
	},
	{
		icon: <InfoIcon />,
		keywords: ["callout", "note", "info", "warning", "tip"],
		label: t("ui_callout"),
		value: KEYS.callout,
	},
	{
		icon: <ChevronRightIcon />,
		keywords: ["toggle", "collapsible", "expand"],
		label: t("ui_toggle"),
		value: KEYS.toggle,
	},
];

export function TurnIntoToolbarButton({
	tooltip,
	...props
}: DropdownMenuProps & { tooltip?: React.ReactNode }) {
	const t = useTranslations("ui");
	const editor = useEditorRef();
	const [open, setOpen] = React.useState(false);

	const value = useSelectionFragmentProp({
		defaultValue: KEYS.p,
		getProp: (node) => getBlockType(node as TElement),
	});
	const selectedItem = React.useMemo(
		() =>
			getTurnIntoItems(t).find((item) => item.value === (value ?? KEYS.p)) ??
			getTurnIntoItems(t)[0],
		[value]
	);

	return (
		<DropdownMenu open={open} onOpenChange={setOpen} modal={false} {...props}>
			<DropdownMenuTrigger asChild>
				<ToolbarButton
					className="min-w-[80px] sm:min-w-[125px]"
					pressed={open}
					tooltip={tooltip ?? t("ui_turn_into")}
					isDropdown
				>
					{selectedItem.label}
				</ToolbarButton>
			</DropdownMenuTrigger>

			<DropdownMenuContent
				className="z-[100] ignore-click-outside/toolbar min-w-0 max-h-[60vh] overflow-y-auto"
				onCloseAutoFocus={(e) => {
					e.preventDefault();
					editor.tf.focus();
				}}
				align="start"
			>
				<ToolbarMenuGroup
					value={value}
					onValueChange={(type) => {
						setBlockType(editor, type);
					}}
					label={t("ui_turn_into")}
				>
					{getTurnIntoItems(t).map(({ icon, label, value: itemValue }) => (
						<DropdownMenuRadioItem
							key={itemValue}
							className="min-w-[180px] pl-2 *:first:[span]:hidden dark:text-white"
							value={itemValue}
						>
							<span className="pointer-events-none absolute right-2 flex size-3.5 items-center justify-center">
								<DropdownMenuItemIndicator>
									<CheckIcon />
								</DropdownMenuItemIndicator>
							</span>
							<span className="text-muted-foreground">{icon}</span>
							{label}
						</DropdownMenuRadioItem>
					))}
				</ToolbarMenuGroup>
			</DropdownMenuContent>
		</DropdownMenu>
	);
}

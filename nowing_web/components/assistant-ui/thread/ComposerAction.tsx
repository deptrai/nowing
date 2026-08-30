"use client";

import { AuiIf, ComposerPrimitive, useAuiState } from "@assistant-ui/react";
import { useAtomValue, useSetAtom } from "jotai";
import {
	ArrowLeft,
	ArrowUpIcon,
	Camera,
	ChevronDown,
	ChevronRight,
	Plus,
	Settings2,
	SquareIcon,
	Unplug,
	Upload,
	Wrench,
} from "lucide-react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { type FC, useCallback, useEffect, useMemo, useState } from "react";
import {
	agentToolsAtom,
	disabledToolsAtom,
	hydrateDisabledToolsAtom,
	toggleToolAtom,
} from "@/atoms/agent-tools/agent-tools.atoms";
import { mentionedDocumentsAtom } from "@/atoms/chat/mentioned-documents.atom";
import { pendingUserImageDataUrlsAtom } from "@/atoms/chat/pending-user-images.atom";
import { importConnectorRequestAtom } from "@/atoms/connector-dialog/connector-dialog.atoms";
import { connectorsAtom } from "@/atoms/connectors/connector-query.atoms";
import { llmSetupStatusAtomFamily } from "@/atoms/model-connections/model-connections-query.atoms";
import { useDocumentUploadDialog } from "@/components/assistant-ui/document-upload-popup";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import { ChatHeader } from "@/components/new-chat/chat-header";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import {
	Drawer,
	DrawerClose,
	DrawerContent,
	DrawerHandle,
	DrawerHeader,
	DrawerTitle,
} from "@/components/ui/drawer";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuPortal,
	DropdownMenuSeparator,
	DropdownMenuSub,
	DropdownMenuSubContent,
	DropdownMenuSubTrigger,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import {
	CONNECTOR_ICON_TO_TYPES,
	CONNECTOR_TOOL_ICON_PATHS,
	getToolDisplayName,
	getToolIcon,
} from "@/contracts/enums/toolIcons";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { useMediaQuery } from "@/hooks/use-media-query";
import { useElectronAPI } from "@/hooks/use-platform";
import { captureDisplayToPngDataUrl } from "@/lib/chat/display-media-capture";
import { groupConnectorsByType } from "@/lib/connectors/group-connectors-by-type";
import { cn } from "@/lib/utils";
import { ConnectedScraperIcons } from "./ConnectedScraperIcons";
import { TOOL_GROUPS } from "./constants";

export interface ComposerActionProps {
	isBlockedByOtherUser?: boolean;
	workspaceId: number;
	onChatModelSelected?: () => void;
}

export const ComposerAction: FC<ComposerActionProps> = ({
	isBlockedByOtherUser = false,
	workspaceId,
	onChatModelSelected,
}) => {
	const mentionedDocuments = useAtomValue(mentionedDocumentsAtom);
	const setImportRequest = useSetAtom(importConnectorRequestAtom);
	const router = useRouter();
	const [toolsPopoverOpen, setToolsPopoverOpen] = useState(false);
	const [mcpDrawerOpen, setMcpDrawerOpen] = useState(false);
	const [openConnectorSubmenu, setOpenConnectorSubmenu] = useState<string | null>(null);
	const [expandedConnectorGroups, setExpandedConnectorGroups] = useState<Set<string>>(
		() => new Set()
	);
	const isDesktop = useMediaQuery("(min-width: 640px)");
	const { openDialog: openUploadDialog } = useDocumentUploadDialog();
	const pendingScreenImages = useAtomValue(pendingUserImageDataUrlsAtom);
	const setPendingScreenImages = useSetAtom(pendingUserImageDataUrlsAtom);
	const electronAPI = useElectronAPI();

	const isComposerTextEmpty = useAuiState(({ composer }) => {
		const text = composer.text?.trim() || "";
		return text.length === 0;
	});
	const isComposerEmpty =
		isComposerTextEmpty && mentionedDocuments.length === 0 && pendingScreenImages.length === 0;

	const handleScreenCapture = useCallback(async () => {
		const url = electronAPI?.captureFullScreen
			? await electronAPI.captureFullScreen()
			: await captureDisplayToPngDataUrl();
		if (url) setPendingScreenImages((prev) => [...prev, url]);
	}, [electronAPI, setPendingScreenImages]);

	const { data: setupStatus } = useAtomValue(llmSetupStatusAtomFamily(workspaceId));

	const { data: agentTools } = useAtomValue(agentToolsAtom);
	const disabledTools = useAtomValue(disabledToolsAtom);
	const disabledToolsSet = useMemo(() => new Set(disabledTools), [disabledTools]);
	const toggleTool = useSetAtom(toggleToolAtom);
	const setDisabledTools = useSetAtom(disabledToolsAtom);
	const hydrateDisabled = useSetAtom(hydrateDisabledToolsAtom);

	const { data: connectors } = useAtomValue(connectorsAtom);
	const connectedTypes = useMemo(
		() => new Set<string>((connectors ?? []).map((c) => c.connector_type)),
		[connectors]
	);

	const toggleToolGroup = useCallback(
		(toolNames: string[]) => {
			const allDisabled = toolNames.every((name) => disabledToolsSet.has(name));
			if (allDisabled) {
				setDisabledTools((prev) => prev.filter((t) => !toolNames.includes(t)));
			} else {
				setDisabledTools((prev) => [...new Set([...prev, ...toolNames])]);
			}
		},
		[disabledToolsSet, setDisabledTools]
	);
	const setConnectorGroupExpanded = useCallback((label: string, expanded: boolean) => {
		setExpandedConnectorGroups((prev) => {
			const next = new Set(prev);
			if (expanded) {
				next.add(label);
			} else {
				next.delete(label);
			}
			return next;
		});
	}, []);

	const filteredTools = agentTools;
	const groupedTools = useMemo(() => {
		if (!filteredTools) return [];
		const toolsByName = new Map(filteredTools.map((t) => [t.name, t]));
		const result: { label: string; tools: typeof filteredTools; connectorIcon?: string }[] = [];
		const placed = new Set<string>();

		for (const group of TOOL_GROUPS) {
			if (group.connectorIcon) {
				const requiredTypes = CONNECTOR_ICON_TO_TYPES[group.connectorIcon];
				const isConnected = requiredTypes?.some((t) => connectedTypes.has(t));
				if (!isConnected) {
					for (const name of group.tools) placed.add(name);
					continue;
				}
			}

			const matched = group.tools.flatMap((name) => {
				const tool = toolsByName.get(name);
				if (!tool) return [];
				placed.add(name);
				return [tool];
			});
			if (matched.length > 0) {
				result.push({ label: group.label, tools: matched, connectorIcon: group.connectorIcon });
			}
		}

		const ungrouped = filteredTools.filter((t) => !placed.has(t.name));
		if (ungrouped.length > 0) {
			result.push({ label: "Other", tools: ungrouped });
		}

		return result;
	}, [filteredTools, connectedTypes]);
	const regularToolGroups = groupedTools.filter((g) => !g.connectorIcon && g.label !== "Other");
	const connectorToolGroups = groupedTools.filter((g) => g.connectorIcon);
	const otherToolGroup = groupedTools.find((g) => !g.connectorIcon && g.label === "Other");

	useEffect(() => {
		hydrateDisabled();
	}, [hydrateDisabled]);

	// A workspace with no usable chat model renders the composer with an inline
	// notice (see ChatUnavailableNotice) rather than being redirected away, so
	// the send button must stay disabled here. The backend also rejects any
	// send that lacks a resolvable model, making this defense-in-depth.
	const isWorkspaceChatReady = setupStatus?.status === "ready";

	const isSendDisabled = isComposerEmpty || !isWorkspaceChatReady || isBlockedByOtherUser;

	return (
		<div className="aui-composer-action-wrapper relative mx-3 mb-3 flex items-center justify-between">
			<div className="flex items-center gap-1">
				{!isDesktop ? (
					<>
						<DropdownMenu>
							<DropdownMenuTrigger asChild>
								<Button
									variant="ghost"
									size="icon"
									className="h-9 w-9 rounded-full p-0 font-semibold text-xs text-muted-foreground transition-colors dark:border-muted-foreground/15 hover:bg-foreground/10 hover:text-foreground"
									aria-label="Upload files, manage tools and more"
									data-joyride="connector-icon"
								>
									<Plus className="size-5" aria-hidden="true" />
								</Button>
							</DropdownMenuTrigger>
							<DropdownMenuContent side="bottom" align="start" sideOffset={8}>
								<DropdownMenuItem onSelect={() => openUploadDialog()}>
									<Upload className="size-4" aria-hidden="true" />
									Upload Files
								</DropdownMenuItem>
								<DropdownMenuItem onSelect={() => setMcpDrawerOpen(true)}>
									<Unplug className="size-4" aria-hidden="true" />
									MCP Connectors
								</DropdownMenuItem>
								<DropdownMenuItem onSelect={() => setToolsPopoverOpen(true)}>
									<Settings2 className="size-4" aria-hidden="true" />
									Manage Tools
								</DropdownMenuItem>
							</DropdownMenuContent>
						</DropdownMenu>
						<Drawer
							open={toolsPopoverOpen}
							onOpenChange={setToolsPopoverOpen}
							shouldScaleBackground={false}
						>
							<DrawerContent className="h-[85vh] max-h-[85vh] z-80" overlayClassName="z-80">
								<DrawerHandle />
								<DrawerHeader className="px-4 pb-3 pt-2">
									<DrawerTitle className="flex items-center justify-center gap-2 text-base font-semibold">
										Manage Tools
									</DrawerTitle>
								</DrawerHeader>
								<div className="min-h-0 flex-1 overflow-y-auto scrollbar-thin pb-6">
									{regularToolGroups.map((group) => (
										<div key={group.label}>
											<div className="px-4 pt-3 pb-1 text-xs text-muted-foreground/80 font-medium select-none">
												{group.label}
											</div>
											{group.tools.map((tool) => {
												const isDisabled = disabledToolsSet.has(tool.name);
												const ToolIcon = getToolIcon(tool.name);
												return (
													<div
														key={tool.name}
														className="flex w-full items-center gap-3 px-4 py-2 hover:bg-accent hover:text-accent-foreground transition-colors"
													>
														<ToolIcon
															className="size-4 shrink-0 text-muted-foreground"
															aria-hidden="true"
														/>
														<span className="flex-1 min-w-0 text-sm font-medium truncate">
															{formatToolName(tool.name)}
														</span>
														<Switch
															checked={!isDisabled}
															onCheckedChange={() => toggleTool(tool.name)}
															className="shrink-0"
														/>
													</div>
												);
											})}
										</div>
									))}
									{connectorToolGroups.length > 0 && (
										<div>
											<div className="px-4 pt-3 pb-1 text-xs text-muted-foreground/80 font-medium select-none">
												Connector Actions
											</div>
											{connectorToolGroups.map((group) => {
												const iconKey = group.connectorIcon ?? "";
												const iconInfo = CONNECTOR_TOOL_ICON_PATHS[iconKey];
												const toolNames = group.tools.map((t) => t.name);
												const allDisabled = toolNames.every((n) => disabledToolsSet.has(n));
												const isExpanded = expandedConnectorGroups.has(group.label);
												return (
													<Collapsible
														key={group.label}
														open={isExpanded}
														onOpenChange={(open) => setConnectorGroupExpanded(group.label, open)}
													>
														<div className="flex w-full items-center gap-3 px-4 py-2 hover:bg-accent hover:text-accent-foreground transition-colors">
															<CollapsibleTrigger asChild>
																<Button
																	type="button"
																	variant="ghost"
																	className="h-auto min-w-0 flex-1 justify-start gap-3 p-0 text-left hover:bg-transparent hover:text-inherit"
																>
																	{iconInfo ? (
																		<Image
																			src={iconInfo.src}
																			alt={iconInfo.alt}
																			width={18}
																			height={18}
																			className="size-[18px] shrink-0 select-none pointer-events-none"
																			draggable={false}
																		/>
																	) : (
																		<Wrench
																			className="size-4 shrink-0 text-muted-foreground"
																			aria-hidden="true"
																		/>
																	)}
																	<span className="min-w-0 flex-1 truncate text-sm font-medium">
																		{group.label}
																	</span>
																	{isExpanded ? (
																		<ChevronDown
																			className="size-4 shrink-0 text-muted-foreground"
																			aria-hidden="true"
																		/>
																	) : (
																		<ChevronRight
																			className="size-4 shrink-0 text-muted-foreground"
																			aria-hidden="true"
																		/>
																	)}
																</Button>
															</CollapsibleTrigger>
															<Switch
																checked={!allDisabled}
																onCheckedChange={() => toggleToolGroup(toolNames)}
																className="shrink-0"
															/>
														</div>
														<CollapsibleContent className="pb-1">
															{group.tools.map((tool) => {
																const isDisabled = disabledToolsSet.has(tool.name);
																return (
																	<div
																		key={tool.name}
																		className={cn(
																			"ml-8 flex items-center gap-3 px-4 py-1.5 rounded-md transition-colors",
																			"hover:bg-accent hover:text-accent-foreground",
																			!isDisabled && "text-primary"
																		)}
																	>
																		<span className="min-w-0 flex-1 truncate text-sm">
																			{formatToolName(tool.name)}
																		</span>
																		<Switch
																			checked={!isDisabled}
																			onCheckedChange={() => toggleTool(tool.name)}
																			className="shrink-0"
																		/>
																	</div>
																);
															})}
														</CollapsibleContent>
													</Collapsible>
												);
											})}
										</div>
									)}
									{otherToolGroup && (
										<div>
											<div className="px-4 pt-3 pb-1 text-xs text-muted-foreground/80 font-medium select-none">
												{otherToolGroup.label}
											</div>
											{otherToolGroup.tools.map((tool) => {
												const isDisabled = disabledToolsSet.has(tool.name);
												const ToolIcon = getToolIcon(tool.name);
												return (
													<div
														key={tool.name}
														className="flex w-full items-center gap-3 px-4 py-2 hover:bg-accent hover:text-accent-foreground transition-colors"
													>
														<ToolIcon
															className="size-4 shrink-0 text-muted-foreground"
															aria-hidden="true"
														/>
														<span className="flex-1 min-w-0 text-sm font-medium truncate">
															{formatToolName(tool.name)}
														</span>
														<Switch
															checked={!isDisabled}
															onCheckedChange={() => toggleTool(tool.name)}
															className="shrink-0"
														/>
													</div>
												);
											})}
										</div>
									)}
									{!filteredTools?.length && (
										<div className="px-4 pt-3 pb-2">
											<Skeleton className="h-3 w-16 mb-2" aria-hidden="true" />
											{["t1", "t2", "t3", "t4"].map((k) => (
												<div key={k} className="flex items-center gap-3 py-2">
													<Skeleton className="size-4 rounded shrink-0" aria-hidden="true" />
													<Skeleton className="h-3.5 flex-1" />
													<Skeleton className="h-5 w-9 rounded-full shrink-0" aria-hidden="true" />
												</div>
											))}
											<Skeleton className="h-3 w-24 mt-3 mb-2" aria-hidden="true" />
											{["c1", "c2", "c3"].map((k) => (
												<div key={k} className="flex items-center gap-3 py-2">
													<Skeleton className="size-4 rounded shrink-0" aria-hidden="true" />
													<Skeleton className="h-3.5 flex-1" />
													<Skeleton className="h-5 w-9 rounded-full shrink-0" aria-hidden="true" />
												</div>
											))}
										</div>
									)}
								</div>
							</DrawerContent>
						</Drawer>
						<Drawer
							open={mcpDrawerOpen}
							onOpenChange={setMcpDrawerOpen}
							shouldScaleBackground={false}
						>
							<DrawerContent className="h-[85vh] max-h-[85vh] z-80" overlayClassName="z-80">
								<DrawerHandle />
								<DrawerHeader className="relative px-4 pb-3 pt-2">
									<DrawerClose asChild>
										<Button
											variant="ghost"
											size="icon"
											className="absolute left-2 top-1/2 -translate-y-1/2 h-8 w-8"
											aria-label="Back"
										>
											<ArrowLeft className="size-5" aria-hidden="true" />
										</Button>
									</DrawerClose>
									<DrawerTitle className="flex items-center justify-center gap-2 text-base font-semibold">
										MCP Connectors
									</DrawerTitle>
								</DrawerHeader>
								<div className="min-h-0 flex-1 overflow-y-auto scrollbar-thin pb-6">
									{groupConnectorsByType((connectors ?? []) as SearchSourceConnector[]).map(
										(group) => (
											<Button
												key={group.connectorType}
												variant="ghost"
												className="flex w-full items-center justify-start gap-3 px-4 py-3 h-auto font-normal"
												onClick={() => {
													setImportRequest({ connectorType: group.connectorType, mode: "auto" });
													setMcpDrawerOpen(false);
												}}
											>
												{getConnectorIcon(group.connectorType, "size-5 shrink-0")}
												<span className="flex-1 truncate text-left text-sm">{group.title}</span>
												{group.connectors.length > 1 && (
													<span className="text-xs text-muted-foreground">
														{group.connectors.length}
													</span>
												)}
											</Button>
										)
									)}
									<div className="mx-4 my-2 h-px bg-border" />
									<Button
										variant="ghost"
										className="flex w-full items-center justify-start gap-3 px-4 py-3 h-auto font-normal"
										onClick={() => {
											if (workspaceId) router.push(`/dashboard/${workspaceId}/connectors`);
											setMcpDrawerOpen(false);
										}}
									>
										<Plus className="size-5 shrink-0" aria-hidden="true" />
										<span className="flex-1 truncate text-left text-sm">
											Browse all integrations
										</span>
									</Button>
								</div>
							</DrawerContent>
						</Drawer>
					</>
				) : (
					<DropdownMenu
						onOpenChange={(open) => {
							if (!open) {
								setToolsPopoverOpen(false);
								setOpenConnectorSubmenu(null);
							}
						}}
					>
						<DropdownMenuTrigger asChild>
							<TooltipIconButton
								tooltip="Upload files, manage tools and more"
								side="bottom"
								disableTooltip={toolsPopoverOpen}
								variant="ghost"
								size="icon"
								className="h-7 w-7 rounded-full p-0 font-semibold text-xs text-muted-foreground transition-colors dark:border-muted-foreground/15 hover:bg-foreground/10 hover:text-foreground"
								aria-label="Upload files, manage tools and more"
								data-joyride="connector-icon"
							>
								<Plus className="size-4" aria-hidden="true" />
							</TooltipIconButton>
						</DropdownMenuTrigger>
						<DropdownMenuContent
							className="w-48"
							side="bottom"
							align="start"
							sideOffset={8}
							onCloseAutoFocus={(event) => event.preventDefault()}
						>
							<DropdownMenuItem onSelect={() => openUploadDialog()}>
								<Upload className="h-4 w-4" aria-hidden="true" />
								Upload Files
							</DropdownMenuItem>
							<DropdownMenuItem onSelect={() => void handleScreenCapture()}>
								<Camera className="h-4 w-4" aria-hidden="true" />
								Take a screenshot
							</DropdownMenuItem>
							<DropdownMenuSub>
								<DropdownMenuSubTrigger>
									<Unplug className="h-4 w-4" aria-hidden="true" />
									MCP Connectors
								</DropdownMenuSubTrigger>
								<DropdownMenuPortal>
									<DropdownMenuSubContent className="w-56 max-h-64 overflow-y-auto">
										{groupConnectorsByType((connectors ?? []) as SearchSourceConnector[]).map(
											(group) => (
												<DropdownMenuItem
													key={group.connectorType}
													onSelect={() =>
														setImportRequest({ connectorType: group.connectorType, mode: "auto" })
													}
												>
													{getConnectorIcon(group.connectorType, "size-4 shrink-0")}
													<span className="flex-1 truncate">{group.title}</span>
													{group.connectors.length > 1 && (
														<span className="text-xs text-muted-foreground">
															{group.connectors.length}
														</span>
													)}
												</DropdownMenuItem>
											)
										)}
										<DropdownMenuSeparator />
										<DropdownMenuItem
											onSelect={() => {
												if (workspaceId) router.push(`/dashboard/${workspaceId}/connectors`);
											}}
										>
											<Plus className="size-4" aria-hidden="true" />
											Browse all integrations
										</DropdownMenuItem>
									</DropdownMenuSubContent>
								</DropdownMenuPortal>
							</DropdownMenuSub>
							<DropdownMenuSub
								open={toolsPopoverOpen}
								onOpenChange={(open) => {
									setToolsPopoverOpen(open);
									if (!open) setOpenConnectorSubmenu(null);
								}}
							>
								<DropdownMenuSubTrigger>
									<Settings2 className="h-4 w-4" aria-hidden="true" />
									Manage Tools
								</DropdownMenuSubTrigger>
								<DropdownMenuPortal>
									<DropdownMenuSubContent
										alignOffset={-192}
										collisionPadding={8}
										className="w-60 h-56 gap-1 overflow-y-auto overscroll-none"
										onScroll={() => setOpenConnectorSubmenu(null)}
									>
										{regularToolGroups.map((group) => (
											<div key={group.label}>
												<div className="px-2 pt-1.5 pb-0.5 text-[10px] text-muted-foreground/80 font-normal select-none">
													{group.label}
												</div>
												{group.tools.map((tool) => {
													const isDisabled = disabledToolsSet.has(tool.name);
													const ToolIcon = getToolIcon(tool.name);
													return (
														<DropdownMenuItem
															key={tool.name}
															onSelect={(e) => {
																e.preventDefault();
																toggleTool(tool.name);
															}}
															className={cn(
																"mb-1 last:mb-0 transition-all",
																"hover:bg-accent hover:text-accent-foreground",
																!isDisabled && "text-primary"
															)}
														>
															<ToolIcon className="h-4 w-4" aria-hidden="true" />
															<span className="flex-1 min-w-0 truncate">
																{formatToolName(tool.name)}
															</span>
															<Switch
																checked={!isDisabled}
																tabIndex={-1}
																className="pointer-events-none shrink-0 origin-right scale-[0.6]"
															/>
														</DropdownMenuItem>
													);
												})}
											</div>
										))}
										{connectorToolGroups.length > 0 && (
											<div>
												<div className="px-2 pt-1.5 pb-0.5 text-[10px] text-muted-foreground/80 font-normal select-none">
													Connector Actions
												</div>
												{connectorToolGroups.map((group) => {
													const iconKey = group.connectorIcon ?? "";
													const iconInfo = CONNECTOR_TOOL_ICON_PATHS[iconKey];
													const toolNames = group.tools.map((t) => t.name);
													const allDisabled = toolNames.every((n) => disabledToolsSet.has(n));
													return (
														<DropdownMenuSub
															key={group.label}
															open={openConnectorSubmenu === group.label}
															onOpenChange={(open) =>
																setOpenConnectorSubmenu(open ? group.label : null)
															}
														>
															<DropdownMenuSubTrigger
																className={cn(
																	"mb-1 last:mb-0 transition-all",
																	"hover:bg-accent hover:text-accent-foreground",
																	"gap-1 [&>svg:last-child]:ml-0",
																	!allDisabled && "text-primary"
																)}
															>
																{iconInfo ? (
																	<Image
																		src={iconInfo.src}
																		alt={iconInfo.alt}
																		width={16}
																		height={16}
																		className="h-4 w-4 shrink-0 select-none pointer-events-none"
																		draggable={false}
																	/>
																) : (
																	<Wrench className="h-4 w-4" aria-hidden="true" />
																)}
																<span className="min-w-0 flex-1 truncate">{group.label}</span>
																<Switch
																	checked={!allDisabled}
																	tabIndex={-1}
																	onPointerDown={(event) => event.stopPropagation()}
																	onClick={(event) => event.stopPropagation()}
																	onCheckedChange={() => toggleToolGroup(toolNames)}
																	className="mr-2 shrink-0 origin-right scale-[0.6]"
																/>
															</DropdownMenuSubTrigger>
															<DropdownMenuPortal>
																<DropdownMenuSubContent
																	collisionPadding={8}
																	className="w-60 max-h-56 overflow-y-auto overscroll-none"
																>
																	{group.tools.map((tool) => {
																		const isDisabled = disabledToolsSet.has(tool.name);
																		return (
																			<DropdownMenuItem
																				key={tool.name}
																				onSelect={(e) => {
																					e.preventDefault();
																					toggleTool(tool.name);
																				}}
																				className={cn(
																					"mb-1 last:mb-0 transition-all",
																					"hover:bg-accent hover:text-accent-foreground",
																					!isDisabled && "text-primary"
																				)}
																			>
																				<span className="min-w-0 flex-1 truncate">
																					{formatToolName(tool.name)}
																				</span>
																				<Switch
																					checked={!isDisabled}
																					tabIndex={-1}
																					className="pointer-events-none shrink-0 origin-right scale-[0.6]"
																				/>
																			</DropdownMenuItem>
																		);
																	})}
																</DropdownMenuSubContent>
															</DropdownMenuPortal>
														</DropdownMenuSub>
													);
												})}
											</div>
										)}
										{otherToolGroup && (
											<div>
												<div className="px-2 pt-1.5 pb-0.5 text-[10px] text-muted-foreground/80 font-normal select-none">
													{otherToolGroup.label}
												</div>
												{otherToolGroup.tools.map((tool) => {
													const isDisabled = disabledToolsSet.has(tool.name);
													const ToolIcon = getToolIcon(tool.name);
													return (
														<DropdownMenuItem
															key={tool.name}
															onSelect={(e) => {
																e.preventDefault();
																toggleTool(tool.name);
															}}
															className={cn(
																"mb-1 last:mb-0 transition-all",
																"hover:bg-accent hover:text-accent-foreground",
																!isDisabled && "text-primary"
															)}
														>
															<ToolIcon className="h-4 w-4" aria-hidden="true" />
															<span className="flex-1 min-w-0 truncate">
																{formatToolName(tool.name)}
															</span>
															<Switch
																checked={!isDisabled}
																tabIndex={-1}
																className="pointer-events-none shrink-0 origin-right scale-[0.6]"
															/>
														</DropdownMenuItem>
													);
												})}
											</div>
										)}
										{!filteredTools?.length && (
											<div className="px-2 pt-1.5 pb-1">
												<Skeleton className="h-2 w-12 mb-1.5" aria-hidden="true" />
												{["dt1", "dt2", "dt3", "dt4"].map((k) => (
													<div key={k} className="flex items-center gap-2 py-1">
														<Skeleton className="h-4 w-4 rounded shrink-0" aria-hidden="true" />
														<Skeleton className="h-3 flex-1" />
														<Skeleton
															className="h-4 w-8 rounded-full shrink-0"
															aria-hidden="true"
														/>
													</div>
												))}
											</div>
										)}
									</DropdownMenuSubContent>
								</DropdownMenuPortal>
							</DropdownMenuSub>
						</DropdownMenuContent>
					</DropdownMenu>
				)}
				<ConnectedScraperIcons workspaceId={workspaceId} />
			</div>
			<div className="ml-auto flex min-w-0 shrink-0 items-center gap-1.5">
				<ChatHeader
					workspaceId={workspaceId}
					className="h-7 max-w-[44vw] px-1.5 sm:max-w-[160px]"
					onChatModelSelected={onChatModelSelected}
				/>
				<AuiIf condition={({ thread }) => !thread.isRunning}>
					<ComposerPrimitive.Send asChild disabled={isSendDisabled}>
						<TooltipIconButton
							tooltip={
								isBlockedByOtherUser
									? "Wait for AI to finish responding"
									: isComposerEmpty
										? "Enter a message or add a screenshot to send"
										: "Send message"
							}
							side="bottom"
							type="submit"
							variant="default"
							size="icon"
							className={cn(
								"aui-composer-send size-7 shrink-0 rounded-full",
								isSendDisabled && "cursor-not-allowed opacity-50"
							)}
							aria-label="Send message"
							disabled={isSendDisabled}
						>
							<ArrowUpIcon className="aui-composer-send-icon size-3.5" aria-hidden="true" />
						</TooltipIconButton>
					</ComposerPrimitive.Send>
				</AuiIf>

				<AuiIf condition={({ thread }) => thread.isRunning}>
					<ComposerPrimitive.Cancel asChild>
						<Button
							type="button"
							variant="default"
							size="icon"
							className="aui-composer-cancel size-7 shrink-0 rounded-full"
							aria-label="Stop generating"
							title="Stop generating"
						>
							<SquareIcon
								className="aui-composer-cancel-icon size-2.5 fill-current"
								aria-hidden="true"
							/>
						</Button>
					</ComposerPrimitive.Cancel>
				</AuiIf>
			</div>
		</div>
	);
};

/** Friendly tool name (delegates to ``getToolDisplayName``). */
export function formatToolName(name: string): string {
	return getToolDisplayName(name);
}

"use client";

import { useAtom } from "jotai";
import { Folder, FolderPlus, Search, X } from "lucide-react";
import { useCallback, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { localExpandedFolderKeysAtom } from "@/atoms/documents/folder.atoms";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { LocalFilesystemBrowser } from "./LocalFilesystemBrowser";

const getFolderDisplayName = (rootPath: string): string =>
	rootPath.split(/[\\/]/).at(-1) || rootPath;

interface DesktopLocalTabContentProps {
	localRootPaths: string[];
	canAddMoreLocalRoots: boolean;
	maxLocalFilesystemRoots: number;
	workspaceId: number;
	onPickFilesystemRoot: () => Promise<void> | void;
	onRemoveFilesystemRoot: (rootPath: string) => Promise<void> | void;
	onClearFilesystemRoots: () => Promise<void> | void;
	onOpenLocalFile: (localFilePath: string) => void;
	electronAvailable: boolean;
}

export function DesktopLocalTabContent({
	localRootPaths,
	canAddMoreLocalRoots,
	maxLocalFilesystemRoots,
	workspaceId,
	onPickFilesystemRoot,
	onRemoveFilesystemRoot,
	onClearFilesystemRoots,
	onOpenLocalFile,
	electronAvailable,
}: DesktopLocalTabContentProps) {
	const t = useTranslations("layout");
	const [localSearch, setLocalSearch] = useState("");
	const debouncedLocalSearch = useDebouncedValue(localSearch, 250);
	const localSearchInputRef = useRef<HTMLInputElement>(null);
	const [expandedFolderKeyMap, setExpandedFolderKeyMap] = useAtom(localExpandedFolderKeysAtom);
	const expandedFolderKeys = useMemo(
		() => new Set(expandedFolderKeyMap[workspaceId] ?? []),
		[expandedFolderKeyMap, workspaceId]
	);
	const handleExpandedFolderKeysChange = useCallback(
		(nextExpandedKeys: Set<string>) => {
			setExpandedFolderKeyMap((prev) => ({
				...prev,
				[workspaceId]: Array.from(nextExpandedKeys),
			}));
		},
		[workspaceId, setExpandedFolderKeyMap]
	);

	return (
		<div className="flex min-h-0 flex-1 flex-col select-none">
			<div className="mx-4 mt-4 mb-3">
				<div className="flex h-7 w-full items-stretch rounded-lg border-0 bg-muted text-[11px] text-muted-foreground">
					{localRootPaths.length > 0 ? (
						<DropdownMenu>
							<DropdownMenuTrigger asChild>
								<Button
									type="button"
									variant="ghost"
									size="sm"
									className="min-w-0 flex-1 h-full justify-start gap-1 px-2 text-left text-[11px] text-muted-foreground"
									title={localRootPaths.join("\n")}
									aria-label={t("manage_selected_folders")}
								>
									<Folder className="size-3 shrink-0" />
									<span className="truncate">
										{localRootPaths.length === 1
											? t("one_folder_selected") : t("folders_selected", { count: localRootPaths.length })}
									</span>
								</Button>
							</DropdownMenuTrigger>
							<DropdownMenuContent align="start" className="w-56 select-none p-0.5">
								<DropdownMenuLabel className="px-1.5 pt-1.5 pb-0.5 text-xs font-medium text-muted-foreground">
									{t("selected_folders")}
								</DropdownMenuLabel>
								{localRootPaths.map((rootPath) => (
									<DropdownMenuItem
										key={rootPath}
										onSelect={(event) => event.preventDefault()}
										className="group h-8 gap-1.5 px-1.5 text-sm text-foreground"
									>
										<Folder className="size-3.5 text-muted-foreground" />
										<span className="min-w-0 flex-1 truncate">
											{getFolderDisplayName(rootPath)}
										</span>
										<Button
											type="button"
											variant="ghost"
											size="icon"
											className="size-5 text-muted-foreground hover:text-accent-foreground"
											onClick={(event) => {
												event.stopPropagation();
												void onRemoveFilesystemRoot(rootPath);
											}}
											aria-label={t("remove_folder", { name: getFolderDisplayName(rootPath) })}
										>
											<X className="size-3" />
										</Button>
									</DropdownMenuItem>
								))}
								<DropdownMenuItem
									variant="destructive"
									className="h-8 px-1.5 text-xs text-destructive focus:text-destructive"
									onClick={() => {
										void onClearFilesystemRoots();
									}}
								>
									{t("clear_all_folders")}
								</DropdownMenuItem>
							</DropdownMenuContent>
						</DropdownMenu>
					) : (
						<div
							className="min-w-0 flex-1 flex items-center gap-1 px-2 transition-colors hover:bg-accent hover:text-accent-foreground"
							title={t("no_local_folders_selected")}
						>
							<Folder className="size-3 shrink-0" />
							<span className="truncate">{t("no_local_folders_selected")}</span>
						</div>
					)}
					<Separator
						orientation="vertical"
						className="data-[orientation=vertical]:h-3 self-center bg-border/60 dark:bg-white/10"
					/>
					{electronAvailable ? (
						<Tooltip>
							<TooltipTrigger asChild>
								<span className="inline-flex">
									<Button
										type="button"
										variant="ghost"
										size="icon"
										className="h-full w-8 text-muted-foreground hover:text-accent-foreground"
										onClick={() => {
											void onPickFilesystemRoot();
										}}
										disabled={!canAddMoreLocalRoots}
										aria-label={t("add_folder")}
									>
										<FolderPlus className="size-3.5" />
									</Button>
								</span>
							</TooltipTrigger>
							<TooltipContent side="top" className="text-xs">
								{canAddMoreLocalRoots ? t("add_folder") : t("max_folders_limit", { max: maxLocalFilesystemRoots })}
							</TooltipContent>
						</Tooltip>
					) : null}
				</div>
			</div>
			<div className="mx-4 mb-2">
				<div className="relative flex-1 min-w-0">
					<div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-muted-foreground">
						<Search size={13} aria-hidden="true" />
					</div>
					<Input
						ref={localSearchInputRef}
						className="peer h-8 w-full border-0 bg-muted pl-8 pr-8 text-sm shadow-none select-none focus:select-text"
						value={localSearch}
						onChange={(e) => setLocalSearch(e.target.value)}
						placeholder={t("search_local_files")}
						type="text"
						aria-label={t("search_local_files")}
					/>
					{Boolean(localSearch) && (
						<Button
							type="button"
							variant="ghost"
							size="icon"
							className="absolute inset-y-0 right-0 h-full w-8 text-muted-foreground hover:text-accent-foreground"
							aria-label={t("clear_local_search")}
							onClick={() => {
								setLocalSearch("");
								localSearchInputRef.current?.focus();
							}}
						>
							<X size={13} strokeWidth={2} aria-hidden="true" />
						</Button>
					)}
				</div>
			</div>
			<LocalFilesystemBrowser
				rootPaths={localRootPaths}
				workspaceId={workspaceId}
				active
				searchQuery={debouncedLocalSearch.trim() || undefined}
				onOpenFile={onOpenLocalFile}
				expandedFolderKeys={expandedFolderKeys}
				onExpandedFolderKeysChange={handleExpandedFolderKeysChange}
			/>
		</div>
	);
}

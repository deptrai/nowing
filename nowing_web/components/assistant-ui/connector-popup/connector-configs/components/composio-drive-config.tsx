"use client";

import {
	ChevronDown,
	ChevronRight,
	File,
	FileSpreadsheet,
	FileText,
	FolderClosed,
	Image,
	Presentation,
	X,
} from "lucide-react";
import { useTranslations } from "next-intl";
import type { FC } from "react";
import { useCallback, useState } from "react";
import { DriveFolderTree, type SelectedFolder } from "@/components/connectors/drive-folder-tree";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { connectorsApiService } from "@/lib/apis/connectors-api.service";
import type { ConnectorConfigProps } from "../index";

interface IndexingOptions {
	max_files_per_folder: number;
	incremental_sync: boolean;
	include_subfolders: boolean;
}

const DEFAULT_INDEXING_OPTIONS: IndexingOptions = {
	max_files_per_folder: 100,
	incremental_sync: true,
	include_subfolders: true,
};

function getFileIconFromName(fileName: string, className: string = "size-3.5 shrink-0") {
	const lowerName = fileName.toLowerCase();
	if (
		lowerName.endsWith(".xlsx") ||
		lowerName.endsWith(".xls") ||
		lowerName.endsWith(".csv") ||
		lowerName.includes("spreadsheet")
	) {
		return <FileSpreadsheet className={`${className} text-muted-foreground`} />;
	}
	if (
		lowerName.endsWith(".pptx") ||
		lowerName.endsWith(".ppt") ||
		lowerName.includes("presentation")
	) {
		return <Presentation className={`${className} text-muted-foreground`} />;
	}
	if (
		lowerName.endsWith(".docx") ||
		lowerName.endsWith(".doc") ||
		lowerName.endsWith(".txt") ||
		lowerName.includes("document") ||
		lowerName.includes("word") ||
		lowerName.includes("text")
	) {
		return <FileText className={`${className} text-muted-foreground`} />;
	}
	if (
		lowerName.endsWith(".png") ||
		lowerName.endsWith(".jpg") ||
		lowerName.endsWith(".jpeg") ||
		lowerName.endsWith(".gif") ||
		lowerName.endsWith(".webp") ||
		lowerName.endsWith(".svg")
	) {
		return <Image className={`${className} text-muted-foreground`} />;
	}
	return <File className={`${className} text-muted-foreground`} />;
}

export const ComposioDriveConfig: FC<ConnectorConfigProps> = ({ connector, onConfigChange }) => {
	const t = useTranslations("assistant");
	const isIndexable = connector.config?.is_indexable as boolean;

	const existingFolders =
		(connector.config?.selected_folders as SelectedFolder[] | undefined) || [];
	const existingFiles = (connector.config?.selected_files as SelectedFolder[] | undefined) || [];
	const existingIndexingOptions =
		(connector.config?.indexing_options as IndexingOptions | undefined) || DEFAULT_INDEXING_OPTIONS;

	const [selectedFolders, setSelectedFolders] = useState<SelectedFolder[]>(existingFolders);
	const [selectedFiles, setSelectedFiles] = useState<SelectedFolder[]>(existingFiles);
	const [indexingOptions, setIndexingOptions] = useState<IndexingOptions>(existingIndexingOptions);
	const [authError, setAuthError] = useState(false);

	const isAuthExpired = connector.config?.auth_expired === true || authError;

	const handleAuthError = useCallback(() => {
		setAuthError(true);
	}, []);

	const fetchItems = useCallback(
		async (parentId?: string) => {
			return connectorsApiService.listComposioDriveFolders({
				connector_id: connector.id,
				parent_id: parentId,
			});
		},
		[connector.id]
	);

	const [isEditMode] = useState(() => existingFolders.length > 0 || existingFiles.length > 0);
	const [isFolderTreeOpen, setIsFolderTreeOpen] = useState(!isEditMode);

	const updateConfig = (
		folders: SelectedFolder[],
		files: SelectedFolder[],
		options: IndexingOptions
	) => {
		if (onConfigChange) {
			onConfigChange({
				...connector.config,
				selected_folders: folders,
				selected_files: files,
				indexing_options: options,
			});
		}
	};

	const handleSelectFolders = (folders: SelectedFolder[]) => {
		setSelectedFolders(folders);
		updateConfig(folders, selectedFiles, indexingOptions);
	};

	const handleSelectFiles = (files: SelectedFolder[]) => {
		setSelectedFiles(files);
		updateConfig(selectedFolders, files, indexingOptions);
	};

	const handleIndexingOptionChange = (key: keyof IndexingOptions, value: number | boolean) => {
		const newOptions = { ...indexingOptions, [key]: value };
		setIndexingOptions(newOptions);
		updateConfig(selectedFolders, selectedFiles, newOptions);
	};

	const handleRemoveFolder = (folderId: string) => {
		const newFolders = selectedFolders.filter((folder) => folder.id !== folderId);
		setSelectedFolders(newFolders);
		updateConfig(newFolders, selectedFiles, indexingOptions);
	};

	const handleRemoveFile = (fileId: string) => {
		const newFiles = selectedFiles.filter((file) => file.id !== fileId);
		setSelectedFiles(newFiles);
		updateConfig(selectedFolders, newFiles, indexingOptions);
	};

	const totalSelected = selectedFolders.length + selectedFiles.length;

	if (!isIndexable) {
		return <div className="space-y-6" />;
	}

	return (
		<div className="space-y-6">
			{/* {t("folder_file_selection")} */}
			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<div className="space-y-1 sm:space-y-2">
					<h3 className="font-medium text-sm sm:text-base">{t("folder_file_selection")}</h3>
					<p className="text-xs sm:text-sm text-muted-foreground">
						{t("folder_file_selection_desc")}
					</p>
				</div>

				{totalSelected > 0 && (
					<div className="p-2 sm:p-3 bg-muted rounded-lg text-xs sm:text-sm space-y-1 sm:space-y-2">
						<p className="font-medium">
							Selected {totalSelected} item{totalSelected > 1 ? "s" : ""}: {(() => {
								const parts: string[] = [];
								if (selectedFolders.length > 0) {
									parts.push(
										`${selectedFolders.length} folder${selectedFolders.length > 1 ? "s" : ""}`
									);
								}
								if (selectedFiles.length > 0) {
									parts.push(`${selectedFiles.length} file${selectedFiles.length > 1 ? "s" : ""}`);
								}
								return parts.length > 0 ? `(${parts.join(", ")})` : "";
							})()}
						</p>
						<div className="max-h-20 sm:max-h-24 overflow-y-auto space-y-1">
							{selectedFolders.map((folder) => (
								<div
									key={folder.id}
									className="text-xs sm:text-sm text-muted-foreground truncate flex items-center gap-1.5"
									title={folder.name}
								>
									<FolderClosed
										className="size-3.5 shrink-0 text-muted-foreground"
										aria-hidden="true"
									/>
									<span className="flex-1 truncate">{folder.name}</span>
									<Button
										type="button"
										variant="ghost"
										size="icon"
										onClick={() => handleRemoveFolder(folder.id)}
										className="size-5 shrink-0 rounded p-0 hover:bg-accent hover:text-accent-foreground"
										aria-label={`Remove ${folder.name}`}
									>
										<X className="size-3.5" aria-hidden="true" />
									</Button>
								</div>
							))}
							{selectedFiles.map((file) => (
								<div
									key={file.id}
									className="text-xs sm:text-sm text-muted-foreground truncate flex items-center gap-1.5"
									title={file.name}
								>
									{getFileIconFromName(file.name)}
									<span className="flex-1 truncate">{file.name}</span>
									<Button
										type="button"
										variant="ghost"
										size="icon"
										onClick={() => handleRemoveFile(file.id)}
										className="size-5 shrink-0 rounded p-0 hover:bg-accent hover:text-accent-foreground"
										aria-label={`Remove ${file.name}`}
									>
										<X className="size-3.5" aria-hidden="true" />
									</Button>
								</div>
							))}
						</div>
					</div>
				)}

				{isAuthExpired && (
					<p className="text-xs text-amber-600 dark:text-amber-500">
						Your Google Drive authentication has expired. Please re-authenticate using the button
						below.
					</p>
				)}

				{isEditMode ? (
					<div className="space-y-2">
						<Button
							type="button"
							variant="ghost"
							onClick={() => setIsFolderTreeOpen((prev) => !prev)}
							className="h-auto w-fit gap-2 px-0 py-0 text-xs font-normal text-muted-foreground hover:bg-transparent hover:text-accent-foreground sm:text-sm"
						>
							Change Selection
							{isFolderTreeOpen ? (
								<ChevronDown className="size-4" aria-hidden="true" />
							) : (
								<ChevronRight className="size-4" aria-hidden="true" />
							)}
						</Button>
						{isFolderTreeOpen && (
							<DriveFolderTree
								fetchItems={fetchItems}
								selectedFolders={selectedFolders}
								onSelectFolders={handleSelectFolders}
								selectedFiles={selectedFiles}
								onSelectFiles={handleSelectFiles}
								onAuthError={handleAuthError}
								rootLabel="My Drive"
								providerName="Google Drive"
							/>
						)}
					</div>
				) : (
					<DriveFolderTree
						fetchItems={fetchItems}
						selectedFolders={selectedFolders}
						onSelectFolders={handleSelectFolders}
						selectedFiles={selectedFiles}
						onSelectFiles={handleSelectFiles}
						onAuthError={handleAuthError}
						rootLabel="My Drive"
						providerName="Google Drive"
					/>
				)}
			</div>

			{/* {t("indexing_options")} */}
			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-4">
				<div className="space-y-1 sm:space-y-2">
					<h3 className="font-medium text-sm sm:text-base">{t("indexing_options")}</h3>
					<p className="text-xs sm:text-sm text-muted-foreground">{t("indexing_options_desc")}</p>
				</div>

				{/* {t("max_files_per_folder")} */}
				<div className="space-y-2">
					<div className="flex items-center justify-between">
						<div className="space-y-0.5">
							<Label htmlFor="max-files" className="text-sm font-medium">
								{t("max_files_per_folder")}
							</Label>
							<p className="text-xs text-muted-foreground">{t("max_files_per_folder_desc")}</p>
						</div>
						<Select
							value={indexingOptions.max_files_per_folder.toString()}
							onValueChange={(value) =>
								handleIndexingOptionChange("max_files_per_folder", parseInt(value, 10))
							}
						>
							<SelectTrigger
								id="max-files"
								className="w-[140px] bg-slate-400/5 dark:bg-slate-400/5 border-slate-400/20 text-xs sm:text-sm"
							>
								<SelectValue placeholder={t("select_limit")} />
							</SelectTrigger>
							<SelectContent className="z-[100]">
								<SelectItem value="50" className="text-xs sm:text-sm">
									50 files
								</SelectItem>
								<SelectItem value="100" className="text-xs sm:text-sm">
									100 files
								</SelectItem>
								<SelectItem value="250" className="text-xs sm:text-sm">
									250 files
								</SelectItem>
								<SelectItem value="500" className="text-xs sm:text-sm">
									500 files
								</SelectItem>
								<SelectItem value="1000" className="text-xs sm:text-sm">
									1000 files
								</SelectItem>
							</SelectContent>
						</Select>
					</div>
				</div>

				{/* {t("include_subfolders")} toggle */}
				<div className="flex items-center justify-between pt-2 border-t border-slate-400/20">
					<div className="space-y-0.5">
						<Label htmlFor="include-subfolders" className="text-sm font-medium">
							{t("include_subfolders")}
						</Label>
						<p className="text-xs text-muted-foreground">{t("include_subfolders_desc")}</p>
					</div>
					<Switch
						id="include-subfolders"
						checked={indexingOptions.include_subfolders}
						onCheckedChange={(checked) => handleIndexingOptionChange("include_subfolders", checked)}
					/>
				</div>
			</div>
		</div>
	);
};

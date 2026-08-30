"use client";

import { format } from "date-fns";
import { useAtomValue } from "jotai";
import { useCallback, useState } from "react";
import { toast } from "sonner";
import {
	deleteConnectorMutationAtom,
	indexConnectorMutationAtom,
	updateConnectorMutationAtom,
} from "@/atoms/connectors/connector-mutation.atoms";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { searchSourceConnector } from "@/contracts/types/connector.types";
import {
	trackConnectorDeleted,
	trackIndexWithDateRangeOpened,
	trackIndexWithDateRangeStarted,
	trackPeriodicIndexingStarted,
} from "@/lib/posthog/events";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";
import { dateRangeSchema, frequencyMinutesSchema } from "../../constants/connector-popup.schemas";
import { getFrequencyLabel } from "./constants";
import type { UseConnectorDialogEdit } from "./types";
import type { ConnectorBase } from "./use-connector-base";

interface UseConnectorEditOptions {
	base: ConnectorBase;
}

export function useConnectorEdit({ base }: UseConnectorEditOptions): UseConnectorDialogEdit & {
	handleStartEdit: (connector: SearchSourceConnector) => void;
	handleSaveConnector: (refreshConnectors: () => void) => Promise<void>;
	handleDisconnectConnector: (refreshConnectors: () => void) => Promise<void>;
	handleBackFromEdit: () => void;
} {
	const {
		workspaceId,
		setIsOpen,
		viewingMCPList,
		activeTab,
		setViewingMCPList,
		setViewingAccountsType,
		viewingAccountsType,
		setCameFromMCPList,
		setCameFromAccountsList,
		cameFromMCPList,
	} = base;

	const { mutateAsync: updateConnector } = useAtomValue(updateConnectorMutationAtom);
	const { mutateAsync: indexConnector } = useAtomValue(indexConnectorMutationAtom);
	const { mutateAsync: deleteConnector } = useAtomValue(deleteConnectorMutationAtom);

	const [editingConnector, setEditingConnector] = useState<SearchSourceConnector | null>(null);
	const [isSaving, setIsSaving] = useState(false);
	const [isDisconnecting, setIsDisconnecting] = useState(false);
	const [connectorConfig, setConnectorConfig] = useState<Record<string, unknown> | null>(null);
	const [connectorName, setConnectorName] = useState<string | null>(null);
	const [startDate, setStartDate] = useState<Date | undefined>(undefined);
	const [endDate, setEndDate] = useState<Date | undefined>(undefined);
	const [periodicEnabled, setPeriodicEnabled] = useState(false);
	const [frequencyMinutes, setFrequencyMinutes] = useState("1440");
	const [enableVisionLlm, setEnableVisionLlm] = useState(false);

	const handleStartEdit = useCallback(
		(connector: SearchSourceConnector) => {
			if (!workspaceId) return;

			if (connector.connector_type === "MCP_CONNECTOR" && !viewingMCPList && activeTab === "all") {
				setViewingMCPList(true);
				return;
			}

			const connectorValidation = searchSourceConnector.safeParse(connector);
			if (!connectorValidation.success) {
				toast.error("Invalid connector data");
				return;
			}

			if (viewingAccountsType && viewingAccountsType.connectorType === connector.connector_type) {
				setCameFromAccountsList(viewingAccountsType);
			} else {
				setCameFromAccountsList(null);
			}
			setViewingAccountsType(null);

			if (viewingMCPList && connector.connector_type === "MCP_CONNECTOR") {
				setCameFromMCPList(true);
			} else {
				setCameFromMCPList(false);
			}
			setViewingMCPList(false);

			if (connector.is_indexable) {
				trackIndexWithDateRangeOpened(Number(workspaceId), connector.connector_type, connector.id);
			}

			setEditingConnector(connector);
			setConnectorName(connector.name);
			setPeriodicEnabled(!connector.is_indexable ? false : connector.periodic_indexing_enabled);
			setFrequencyMinutes(connector.indexing_frequency_minutes?.toString() || "1440");
			setEnableVisionLlm(connector.enable_vision_llm ?? false);
			setConnectorConfig(connector.config || {});
			setStartDate(undefined);
			setEndDate(undefined);
		},
		[
			workspaceId,
			viewingAccountsType,
			viewingMCPList,
			activeTab,
			setViewingMCPList,
			setViewingAccountsType,
			setCameFromMCPList,
			setCameFromAccountsList,
		]
	);

	const handleBackFromEdit = useCallback(() => {
		if (editingConnector?.connector_type === "MCP_CONNECTOR" && cameFromMCPList) {
			setViewingMCPList(true);
			setCameFromMCPList(false);
			setEditingConnector(null);
			setConnectorName(null);
			setConnectorConfig(null);
			return;
		}

		const cameFromAccounts = base.cameFromAccountsList;
		if (cameFromAccounts && editingConnector) {
			setViewingAccountsType(cameFromAccounts);
			setCameFromAccountsList(null);
		}

		setEditingConnector(null);
		setConnectorName(null);
		setConnectorConfig(null);
	}, [
		editingConnector,
		cameFromMCPList,
		base.cameFromAccountsList,
		setViewingMCPList,
		setCameFromMCPList,
		setViewingAccountsType,
		setCameFromAccountsList,
	]);

	const handleSaveConnector = useCallback(
		async (refreshConnectors: () => void) => {
			if (!editingConnector || !workspaceId || isSaving) return;

			if (
				editingConnector.is_indexable &&
				editingConnector.connector_type !== "GOOGLE_DRIVE_CONNECTOR" &&
				editingConnector.connector_type !== "ONEDRIVE_CONNECTOR" &&
				editingConnector.connector_type !== "DROPBOX_CONNECTOR" &&
				editingConnector.connector_type !== "WEBCRAWLER_CONNECTOR"
			) {
				const dateRangeValidation = dateRangeSchema.safeParse({ startDate, endDate });
				if (!dateRangeValidation.success) {
					toast.error(dateRangeValidation.error.issues[0]?.message || "Invalid date range");
					return;
				}
			}

			if (periodicEnabled && !editingConnector.is_indexable) {
				toast.error("Periodic indexing is not available for this connector type");
				return;
			}

			if (
				periodicEnabled &&
				(editingConnector.connector_type === "GOOGLE_DRIVE_CONNECTOR" ||
					editingConnector.connector_type === "COMPOSIO_GOOGLE_DRIVE_CONNECTOR" ||
					editingConnector.connector_type === "ONEDRIVE_CONNECTOR" ||
					editingConnector.connector_type === "DROPBOX_CONNECTOR")
			) {
				const selectedFolders = (connectorConfig || editingConnector.config)?.selected_folders as
					| Array<{ id: string; name: string }>
					| undefined;
				const selectedFiles = (connectorConfig || editingConnector.config)?.selected_files as
					| Array<{ id: string; name: string }>
					| undefined;
				const hasItemsSelected =
					(selectedFolders && selectedFolders.length > 0) ||
					(selectedFiles && selectedFiles.length > 0);

				if (!hasItemsSelected) {
					toast.error("Select at least one folder or file to enable periodic sync");
					return;
				}
			}

			if (periodicEnabled && editingConnector.is_indexable) {
				const frequencyValidation = frequencyMinutesSchema.safeParse(frequencyMinutes);
				if (!frequencyValidation.success) {
					toast.error("Invalid frequency value");
					return;
				}
			}

			setIsSaving(true);
			try {
				const startDateStr = startDate ? format(startDate, "yyyy-MM-dd") : undefined;
				const endDateStr = endDate ? format(endDate, "yyyy-MM-dd") : undefined;

				const frequency =
					periodicEnabled && editingConnector.is_indexable ? parseInt(frequencyMinutes, 10) : null;
				await updateConnector({
					id: editingConnector.id,
					data: {
						name: connectorName || editingConnector.name,
						enable_vision_llm: enableVisionLlm,
						periodic_indexing_enabled: !editingConnector.is_indexable ? false : periodicEnabled,
						indexing_frequency_minutes: !editingConnector.is_indexable ? null : frequency,
						config: connectorConfig || editingConnector.config,
					},
				});

				let indexingDescription = "Settings saved.";

				if (!editingConnector.is_indexable) {
					indexingDescription = "Settings saved.";
				} else if (
					editingConnector.connector_type === "GOOGLE_DRIVE_CONNECTOR" ||
					editingConnector.connector_type === "COMPOSIO_GOOGLE_DRIVE_CONNECTOR" ||
					editingConnector.connector_type === "ONEDRIVE_CONNECTOR" ||
					editingConnector.connector_type === "DROPBOX_CONNECTOR"
				) {
					const selectedFolders = (connectorConfig || editingConnector.config)?.selected_folders as
						| Array<{ id: string; name: string }>
						| undefined;
					const selectedFiles = (connectorConfig || editingConnector.config)?.selected_files as
						| Array<{ id: string; name: string }>
						| undefined;
					const indexingOptions = (connectorConfig || editingConnector.config)?.indexing_options as
						| {
								max_files_per_folder: number;
								incremental_sync: boolean;
								include_subfolders: boolean;
						  }
						| undefined;
					if (
						(selectedFolders && selectedFolders.length > 0) ||
						(selectedFiles && selectedFiles.length > 0)
					) {
						await indexConnector({
							connector_id: editingConnector.id,
							queryParams: { workspace_id: workspaceId },
							body: {
								folders: selectedFolders || [],
								files: selectedFiles || [],
								indexing_options: indexingOptions || {
									max_files_per_folder: 100,
									incremental_sync: true,
									include_subfolders: true,
								},
							},
						});
						const totalItems = (selectedFolders?.length || 0) + (selectedFiles?.length || 0);
						indexingDescription = `Re-indexing started for ${totalItems} item(s).`;
					}
				} else if (editingConnector.connector_type === "WEBCRAWLER_CONNECTOR") {
					await indexConnector({
						connector_id: editingConnector.id,
						queryParams: { workspace_id: workspaceId },
					});
					indexingDescription = "Re-indexing started with updated configuration.";
				} else if (startDateStr || endDateStr) {
					await indexConnector({
						connector_id: editingConnector.id,
						queryParams: {
							workspace_id: workspaceId,
							start_date: startDateStr,
							end_date: endDateStr,
						},
					});
					indexingDescription = "Re-indexing started with new date range.";
				}

				if (
					editingConnector.is_indexable &&
					(indexingDescription.includes("Re-indexing") || indexingDescription.includes("indexing"))
				) {
					trackIndexWithDateRangeStarted(
						Number(workspaceId),
						editingConnector.connector_type,
						editingConnector.id,
						{ hasStartDate: !!startDateStr, hasEndDate: !!endDateStr }
					);
				}

				if (periodicEnabled && editingConnector.is_indexable) {
					trackPeriodicIndexingStarted(
						Number(workspaceId),
						editingConnector.connector_type,
						editingConnector.id,
						frequency || parseInt(frequencyMinutes, 10)
					);
				}

				const frequencyLabel = getFrequencyLabel(frequencyMinutes);
				const toastTitle = `${editingConnector.name} updated successfully`;
				toast.success(toastTitle, {
					description: periodicEnabled
						? `Periodic sync ${frequency ? `enabled every ${frequencyLabel}` : "enabled"}. ${indexingDescription}`
						: indexingDescription,
				});

				setIsOpen(false);
				setEditingConnector(null);
				setConnectorName(null);
				setConnectorConfig(null);
				setStartDate(undefined);
				setEndDate(undefined);
				setPeriodicEnabled(false);
				setFrequencyMinutes("1440");
				setEnableVisionLlm(false);

				refreshConnectors();
				queryClient.invalidateQueries({
					queryKey: cacheKeys.logs.summary(Number(workspaceId)),
				});
			} catch (error) {
				console.error("Error saving connector:", error);
				toast.error("Failed to save connector changes");
			} finally {
				setIsSaving(false);
			}
		},
		[
			editingConnector,
			workspaceId,
			isSaving,
			startDate,
			endDate,
			indexConnector,
			updateConnector,
			periodicEnabled,
			frequencyMinutes,
			enableVisionLlm,
			connectorConfig,
			connectorName,
			setIsOpen,
		]
	);

	const handleDisconnectConnector = useCallback(
		async (refreshConnectors: () => void) => {
			if (!editingConnector || !workspaceId) return;

			setIsDisconnecting(true);
			try {
				await deleteConnector({ id: editingConnector.id });

				trackConnectorDeleted(
					Number(workspaceId),
					editingConnector.connector_type,
					editingConnector.id
				);

				toast.success(
					editingConnector.connector_type === "MCP_CONNECTOR"
						? `${editingConnector.name} MCP server removed successfully`
						: `${editingConnector.name} disconnected successfully`
				);

				if (editingConnector.connector_type === "MCP_CONNECTOR" && cameFromMCPList) {
					setViewingMCPList(true);
					setEditingConnector(null);
					setConnectorName(null);
					setConnectorConfig(null);
				} else {
					setEditingConnector(null);
					setConnectorName(null);
					setConnectorConfig(null);
					setIsOpen(false);
				}

				refreshConnectors();
				queryClient.invalidateQueries({
					queryKey: cacheKeys.logs.summary(Number(workspaceId)),
				});
			} catch (error) {
				console.error("Error disconnecting connector:", error);
				toast.error("Failed to disconnect connector");
			} finally {
				setIsDisconnecting(false);
			}
		},
		[editingConnector, workspaceId, deleteConnector, cameFromMCPList, setViewingMCPList, setIsOpen]
	);

	return {
		editingConnector,
		setEditingConnector,
		isSaving,
		setIsSaving,
		isDisconnecting,
		setIsDisconnecting,
		connectorConfig,
		setConnectorConfig,
		connectorName,
		setConnectorName,
		handleStartEdit,
		handleSaveConnector,
		handleDisconnectConnector,
		handleBackFromEdit,
	};
}

export type ConnectorEdit = ReturnType<typeof useConnectorEdit>;

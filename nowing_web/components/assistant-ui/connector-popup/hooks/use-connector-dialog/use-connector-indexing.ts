"use client";

import { format } from "date-fns";
import { useAtomValue } from "jotai";
import { useCallback, useRef, useState } from "react";
import { toast } from "sonner";
import {
	indexConnectorMutationAtom,
	updateConnectorMutationAtom,
} from "@/atoms/connectors/connector-mutation.atoms";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import {
	trackIndexWithDateRangeStarted,
	trackPeriodicIndexingStarted,
	trackQuickIndexClicked,
} from "@/lib/posthog/events";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";
import { AUTO_INDEX_DEFAULTS } from "../../constants/connector-constants";
import { dateRangeSchema, frequencyMinutesSchema } from "../../constants/connector-popup.schemas";
import type { IndexingConfigState, UseConnectorDialogIndexing } from "./types";
import type { ConnectorBase } from "./use-connector-base";

interface UseConnectorIndexingOptions {
	base: ConnectorBase;
}

export function useConnectorIndexing({
	base,
}: UseConnectorIndexingOptions): UseConnectorDialogIndexing & {
	handleAutoIndex: (connector: SearchSourceConnector, title: string, type: string) => Promise<void>;
	handleStartIndexing: (refreshConnectors: () => void) => Promise<void>;
	handleSkipIndexing: () => void;
	handleQuickIndexConnector: (
		connectorId: number,
		connectorType?: string,
		stopIndexing?: (id: number) => void,
		startDate?: Date,
		endDate?: Date
	) => Promise<void>;
} {
	const { workspaceId, refetchAllConnectors, setIsOpen } = base;
	const { mutateAsync: updateConnector } = useAtomValue(updateConnectorMutationAtom);
	const { mutateAsync: indexConnector } = useAtomValue(indexConnectorMutationAtom);

	const [indexingConfig, setIndexingConfig] = useState<IndexingConfigState | null>(null);
	const [indexingConnector, setIndexingConnector] = useState<SearchSourceConnector | null>(null);
	const [indexingConnectorConfig, setIndexingConnectorConfig] = useState<Record<
		string,
		unknown
	> | null>(null);
	const [startDate, setStartDate] = useState<Date | undefined>(undefined);
	const [endDate, setEndDate] = useState<Date | undefined>(undefined);
	const [isStartingIndexing, setIsStartingIndexing] = useState(false);
	const [periodicEnabled, setPeriodicEnabled] = useState(false);
	const [frequencyMinutes, setFrequencyMinutes] = useState("1440");
	const [enableVisionLlm, setEnableVisionLlm] = useState(false);
	const [isFromOAuth, setIsFromOAuth] = useState(false);
	const isAutoIndexingRef = useRef(false);

	const handleAutoIndex = useCallback(
		async (connector: SearchSourceConnector, connectorTitle: string, connectorType: string) => {
			if (!workspaceId || isAutoIndexingRef.current) return;
			isAutoIndexingRef.current = true;

			const defaults = AUTO_INDEX_DEFAULTS[connectorType];
			const now = new Date();
			const startDate = new Date(now);
			startDate.setDate(startDate.getDate() - (defaults?.daysBack ?? 365));
			const endDate = new Date(now);
			endDate.setDate(endDate.getDate() + (defaults?.daysForward ?? 0));

			const toastId = "auto-index";
			toast.loading(`Setting up ${connectorTitle}...`, { id: toastId });

			try {
				await updateConnector({
					id: connector.id,
					data: {
						periodic_indexing_enabled: true,
						indexing_frequency_minutes: defaults?.frequencyMinutes ?? 1440,
					},
				});

				await indexConnector({
					connector_id: connector.id,
					queryParams: {
						workspace_id: workspaceId,
						start_date: format(startDate, "yyyy-MM-dd"),
						end_date: format(endDate, "yyyy-MM-dd"),
					},
				});

				trackIndexWithDateRangeStarted(Number(workspaceId), connectorType, connector.id, {
					hasStartDate: true,
					hasEndDate: true,
				});

				toast.success(`${connectorTitle} connected!`, {
					id: toastId,
					description: defaults?.syncDescription ?? "Syncing started.",
				});
			} catch (error) {
				console.error("Auto-index failed:", error);
				toast.error(`${connectorTitle} connected, but sync failed`, {
					id: toastId,
					description: "You can start syncing from settings.",
				});
			} finally {
				queryClient.invalidateQueries({
					queryKey: cacheKeys.logs.summary(Number(workspaceId)),
				});
				await refetchAllConnectors();
				isAutoIndexingRef.current = false;
			}
		},
		[workspaceId, indexConnector, updateConnector, refetchAllConnectors]
	);

	const handleStartIndexing = useCallback(
		async (refreshConnectors: () => void) => {
			if (!indexingConfig || !workspaceId) return;

			if (
				indexingConfig.connectorType !== "GOOGLE_DRIVE_CONNECTOR" &&
				indexingConfig.connectorType !== "COMPOSIO_GOOGLE_DRIVE_CONNECTOR" &&
				indexingConfig.connectorType !== "ONEDRIVE_CONNECTOR" &&
				indexingConfig.connectorType !== "DROPBOX_CONNECTOR" &&
				indexingConfig.connectorType !== "WEBCRAWLER_CONNECTOR"
			) {
				const dateRangeValidation = dateRangeSchema.safeParse({ startDate, endDate });
				if (!dateRangeValidation.success) {
					const firstIssueMsg =
						dateRangeValidation.error.issues?.[0]?.message ?? "Invalid date range";
					toast.error(firstIssueMsg);
					return;
				}
			}

			if (periodicEnabled) {
				const frequencyValidation = frequencyMinutesSchema.safeParse(frequencyMinutes);
				if (!frequencyValidation.success) {
					toast.error("Invalid frequency value");
					return;
				}
			}

			setIsStartingIndexing(true);
			try {
				const startDateStr = startDate ? format(startDate, "yyyy-MM-dd") : undefined;
				const endDateStr = endDate ? format(endDate, "yyyy-MM-dd") : undefined;

				if (enableVisionLlm || periodicEnabled || indexingConnectorConfig) {
					const frequency = periodicEnabled ? parseInt(frequencyMinutes, 10) : undefined;
					await updateConnector({
						id: indexingConfig.connectorId,
						data: {
							enable_vision_llm: enableVisionLlm,
							...(periodicEnabled && {
								periodic_indexing_enabled: true,
								indexing_frequency_minutes: frequency,
							}),
							...(indexingConnectorConfig && {
								config: indexingConnectorConfig,
							}),
						},
					});
				}

				if (
					(indexingConfig.connectorType === "GOOGLE_DRIVE_CONNECTOR" ||
						indexingConfig.connectorType === "COMPOSIO_GOOGLE_DRIVE_CONNECTOR" ||
						indexingConfig.connectorType === "ONEDRIVE_CONNECTOR" ||
						indexingConfig.connectorType === "DROPBOX_CONNECTOR") &&
					indexingConnectorConfig
				) {
					const selectedFolders = indexingConnectorConfig.selected_folders as
						| Array<{ id: string; name: string }>
						| undefined;
					const selectedFiles = indexingConnectorConfig.selected_files as
						| Array<{ id: string; name: string }>
						| undefined;
					const indexingOptions = indexingConnectorConfig.indexing_options as
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
							connector_id: indexingConfig.connectorId,
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
					} else {
						toast.error("Please select at least one folder to index");
						setIsStartingIndexing(false);
						return;
					}
				} else if (indexingConfig.connectorType === "WEBCRAWLER_CONNECTOR") {
					await indexConnector({
						connector_id: indexingConfig.connectorId,
						queryParams: { workspace_id: workspaceId },
					});
				} else {
					await indexConnector({
						connector_id: indexingConfig.connectorId,
						queryParams: {
							workspace_id: workspaceId,
							start_date: startDateStr,
							end_date: endDateStr,
						},
					});
				}

				trackIndexWithDateRangeStarted(
					Number(workspaceId),
					indexingConfig.connectorType,
					indexingConfig.connectorId,
					{ hasStartDate: !!startDate, hasEndDate: !!endDate }
				);

				if (periodicEnabled) {
					trackPeriodicIndexingStarted(
						Number(workspaceId),
						indexingConfig.connectorType,
						indexingConfig.connectorId,
						parseInt(frequencyMinutes, 10)
					);
				}

				toast.success(`${indexingConfig.connectorTitle} indexing started`);

				setIsOpen(false);
				setIsFromOAuth(false);
				setIndexingConfig(null);
				setIndexingConnector(null);
				setIndexingConnectorConfig(null);
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
				console.error("Error starting indexing:", error);
				toast.error("Failed to start indexing");
			} finally {
				setIsStartingIndexing(false);
			}
		},
		[
			indexingConfig,
			workspaceId,
			startDate,
			endDate,
			indexConnector,
			updateConnector,
			periodicEnabled,
			frequencyMinutes,
			enableVisionLlm,
			indexingConnectorConfig,
			setIsOpen,
		]
	);

	const handleSkipIndexing = useCallback(() => {
		setIsOpen(false);
		setIsFromOAuth(false);
		setIndexingConfig(null);
		setIndexingConnector(null);
		setIndexingConnectorConfig(null);
		setStartDate(undefined);
		setEndDate(undefined);
		setPeriodicEnabled(false);
		setFrequencyMinutes("1440");
		setEnableVisionLlm(false);
	}, [setIsOpen]);

	const handleQuickIndexConnector = useCallback(
		async (
			connectorId: number,
			connectorType?: string,
			stopIndexing?: (id: number) => void,
			startDate?: Date,
			endDate?: Date
		) => {
			if (!workspaceId) {
				if (stopIndexing) stopIndexing(connectorId);
				return;
			}

			if (connectorType) {
				trackQuickIndexClicked(Number(workspaceId), connectorType, connectorId);
			}

			try {
				const startDateStr = startDate ? format(startDate, "yyyy-MM-dd") : undefined;
				const endDateStr = endDate ? format(endDate, "yyyy-MM-dd") : undefined;

				await indexConnector({
					connector_id: connectorId,
					queryParams: {
						workspace_id: workspaceId,
						start_date: startDateStr,
						end_date: endDateStr,
					},
				});
				toast.success("Indexing started");

				queryClient.invalidateQueries({
					queryKey: cacheKeys.logs.summary(Number(workspaceId)),
				});
			} catch (error) {
				console.error("Error indexing connector content:", error);
				toast.error(error instanceof Error ? error.message : "Failed to start indexing");
				if (stopIndexing) stopIndexing(connectorId);
			}
		},
		[workspaceId, indexConnector]
	);

	return {
		indexingConfig,
		setIndexingConfig,
		indexingConnector,
		setIndexingConnector,
		indexingConnectorConfig,
		setIndexingConnectorConfig,
		startDate,
		setStartDate,
		endDate,
		setEndDate,
		isStartingIndexing,
		setIsStartingIndexing,
		periodicEnabled,
		setPeriodicEnabled,
		frequencyMinutes,
		setFrequencyMinutes,
		enableVisionLlm,
		setEnableVisionLlm,
		isFromOAuth,
		setIsFromOAuth,
		handleAutoIndex,
		handleStartIndexing,
		handleSkipIndexing,
		handleQuickIndexConnector,
	};
}

export type ConnectorIndexing = ReturnType<typeof useConnectorIndexing>;

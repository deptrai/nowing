"use client";

import { format } from "date-fns";
import { useAtomValue } from "jotai";
import { useCallback } from "react";
import { toast } from "sonner";
import {
	createConnectorMutationAtom,
	indexConnectorMutationAtom,
	updateConnectorMutationAtom,
} from "@/atoms/connectors/connector-mutation.atoms";
import { EnumConnectorName } from "@/contracts/enums/connector";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { searchSourceConnector } from "@/contracts/types/connector.types";
import {
	trackConnectorConnected,
	trackConnectorSetupFailure,
	trackConnectorSetupStarted,
} from "@/lib/posthog/events";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { queryClient } from "@/lib/query-client/client";
import { OTHER_CONNECTORS } from "../../constants/connector-constants";
import { validateIndexingConfigState } from "../../constants/connector-popup.schemas";
import type { ConnectorBase } from "./use-connector-base";
import type { ConnectorEdit } from "./use-connector-edit";
import type { ConnectorIndexing } from "./use-connector-indexing";

interface UseConnectorCreationOptions {
	base: ConnectorBase;
	indexing: ConnectorIndexing;
	edit: ConnectorEdit;
}

export interface UseConnectorCreationResult {
	handleCreateYouTubeCrawler: () => void;
	handleCreateWebcrawler: () => Promise<void>;
	handleConnectNonOAuth: (connectorType: string) => void;
	handleSubmitConnectForm: (
		formData: {
			name: string;
			connector_type: string;
			config: Record<string, unknown>;
			is_indexable: boolean;
			last_indexed_at: null;
			periodic_indexing_enabled: boolean;
			indexing_frequency_minutes: number | null;
			next_scheduled_at: null;
			startDate?: Date;
			endDate?: Date;
			periodicEnabled?: boolean;
			frequencyMinutes?: string;
		},
		onIndexingStart?: (connectorId: number) => void
	) => Promise<void>;
	handleBackFromConnect: () => void;
	handleBackFromYouTube: () => void;
}

export function useConnectorCreation({
	base,
	indexing,
	edit,
}: UseConnectorCreationOptions): UseConnectorCreationResult {
	const {
		workspaceId,
		refetchAllConnectors,
		setIsOpen,
		setConnectingConnectorType,
		connectCameFromMCPList,
		setConnectCameFromMCPList,
		setViewingMCPList,
		setIsYouTubeView,
		setConnectingId,
		isCreatingConnectorRef,
		setIsCreatingConnector,
		connectingConnectorType,
	} = base;

	const {
		setIndexingConfig,
		setIndexingConnector,
		setIndexingConnectorConfig,
		setStartDate,
		setEndDate,
		setPeriodicEnabled,
		setFrequencyMinutes,
		setEnableVisionLlm,
	} = indexing;

	const { setEditingConnector, setConnectorName, setConnectorConfig, setIsSaving } = edit;

	const { mutateAsync: createConnector } = useAtomValue(createConnectorMutationAtom);
	const { mutateAsync: updateConnector } = useAtomValue(updateConnectorMutationAtom);
	const { mutateAsync: indexConnector } = useAtomValue(indexConnectorMutationAtom);

	const handleCreateYouTubeCrawler = useCallback(() => {
		if (!workspaceId) return;
		setIsYouTubeView(true);
	}, [workspaceId, setIsYouTubeView]);

	const handleBackFromYouTube = useCallback(() => {
		setIsYouTubeView(false);
	}, [setIsYouTubeView]);

	const handleCreateWebcrawler = useCallback(async () => {
		if (!workspaceId) return;

		setConnectingId("webcrawler-connector");
		trackConnectorSetupStarted(
			Number(workspaceId),
			EnumConnectorName.WEBCRAWLER_CONNECTOR,
			"webcrawler_quick_add"
		);

		try {
			await createConnector({
				data: {
					name: "Web Pages",
					connector_type: EnumConnectorName.WEBCRAWLER_CONNECTOR,
					config: {},
					is_indexable: true,
					is_active: true,
					last_indexed_at: null,
					periodic_indexing_enabled: false,
					indexing_frequency_minutes: null,
					next_scheduled_at: null,
					enable_vision_llm: false,
				},
				queryParams: { workspace_id: workspaceId },
			});

			const result = (await refetchAllConnectors()) as { data?: SearchSourceConnector[] | null };
			if (result.data) {
				const connector = result.data.find(
					(c: SearchSourceConnector) => c.connector_type === EnumConnectorName.WEBCRAWLER_CONNECTOR
				);
				if (connector) {
					const connectorValidation = searchSourceConnector.safeParse(connector);
					if (connectorValidation.success) {
						trackConnectorConnected(
							Number(workspaceId),
							EnumConnectorName.WEBCRAWLER_CONNECTOR,
							connector.id
						);

						const config = validateIndexingConfigState({
							connectorType: EnumConnectorName.WEBCRAWLER_CONNECTOR,
							connectorId: connector.id,
							connectorTitle: "Web Pages",
						});
						setIndexingConfig(config);
						setIndexingConnector(connector);
						setIndexingConnectorConfig(connector.config || {});
						setIsOpen(true);
					}
				}
			}
		} catch (error) {
			console.error("Error creating webcrawler connector:", error);
			trackConnectorSetupFailure(
				Number(workspaceId),
				EnumConnectorName.WEBCRAWLER_CONNECTOR,
				error instanceof Error ? error.message : "webcrawler_create_failed",
				"webcrawler_quick_add"
			);
			toast.error("Failed to create web crawler connector");
		} finally {
			setConnectingId(null);
		}
	}, [
		workspaceId,
		createConnector,
		refetchAllConnectors,
		setIsOpen,
		setIndexingConfig,
		setIndexingConnector,
		setIndexingConnectorConfig,
		setConnectingId,
	]);

	const handleConnectNonOAuth = useCallback(
		(connectorType: string) => {
			if (!workspaceId) return;
			trackConnectorSetupStarted(Number(workspaceId), connectorType, "non_oauth_click");
			setConnectingConnectorType(connectorType);
		},
		[workspaceId, setConnectingConnectorType]
	);

	const handleSubmitConnectForm = useCallback(
		async (
			formData: {
				name: string;
				connector_type: string;
				config: Record<string, unknown>;
				is_indexable: boolean;
				last_indexed_at: null;
				periodic_indexing_enabled: boolean;
				indexing_frequency_minutes: number | null;
				next_scheduled_at: null;
				startDate?: Date;
				endDate?: Date;
				periodicEnabled?: boolean;
				frequencyMinutes?: string;
			},
			onIndexingStart?: (connectorId: number) => void
		) => {
			if (!workspaceId || !connectingConnectorType) return;

			if (isCreatingConnectorRef.current) return;
			isCreatingConnectorRef.current = true;
			setIsCreatingConnector(true);

			try {
				const { startDate, endDate, periodicEnabled, frequencyMinutes, ...connectorData } =
					formData;

				const newConnector = await createConnector({
					data: {
						...connectorData,
						connector_type: connectorData.connector_type as EnumConnectorName,
						is_active: true,
						next_scheduled_at: connectorData.next_scheduled_at as string | null,
						enable_vision_llm: false,
					},
					queryParams: { workspace_id: workspaceId },
				});

				const result = (await refetchAllConnectors()) as { data?: SearchSourceConnector[] | null };
				if (result.data) {
					const connector = result.data.find(
						(c: SearchSourceConnector) => c.id === newConnector.id
					);
					if (connector) {
						const connectorValidation = searchSourceConnector.safeParse(connector);
						if (connectorValidation.success) {
							const currentConnectorType = connectingConnectorType;

							trackConnectorConnected(Number(workspaceId), currentConnectorType, connector.id);

							const connectorInfo = OTHER_CONNECTORS.find(
								(c) => c.connectorType === currentConnectorType
							);
							const connectorTitle = connectorInfo?.title || connector.name;

							const config = validateIndexingConfigState({
								connectorType: currentConnectorType as EnumConnectorName,
								connectorId: connector.id,
								connectorTitle,
							});

							setConnectingConnectorType(null);

							setIndexingConfig(config);
							setIndexingConnector(connector);
							setIndexingConnectorConfig(connector.config || {});

							if (formData.startDate !== undefined) setStartDate(formData.startDate);
							if (formData.endDate !== undefined) setEndDate(formData.endDate);
							if (formData.periodicEnabled !== undefined)
								setPeriodicEnabled(formData.periodicEnabled);
							if (formData.frequencyMinutes !== undefined)
								setFrequencyMinutes(formData.frequencyMinutes);

							if (connector.is_indexable) {
								const startDateForIndexing = formData.startDate;
								const endDateForIndexing = formData.endDate;
								const periodicEnabledForIndexing = formData.periodicEnabled || false;
								const frequencyMinutesForIndexing = formData.frequencyMinutes || "1440";

								if (periodicEnabledForIndexing) {
									const frequency = parseInt(frequencyMinutesForIndexing, 10);
									await updateConnector({
										id: connector.id,
										data: {
											periodic_indexing_enabled: true,
											indexing_frequency_minutes: frequency,
										},
									});
								}

								if (onIndexingStart) onIndexingStart(connector.id);

								const startDateStr = startDateForIndexing
									? format(startDateForIndexing, "yyyy-MM-dd")
									: undefined;
								const endDateStr = endDateForIndexing
									? format(endDateForIndexing, "yyyy-MM-dd")
									: undefined;

								await indexConnector({
									connector_id: connector.id,
									queryParams: {
										workspace_id: workspaceId,
										start_date: startDateStr,
										end_date: endDateStr,
									},
								});

								const successMessage =
									currentConnectorType === "MCP_CONNECTOR"
										? `${connector.name} added successfully`
										: `${connectorTitle} connected and syncing started!`;
								toast.success(successMessage);

								setIsOpen(false);

								setIndexingConfig(null);
								setIndexingConnector(null);
								setIndexingConnectorConfig(null);

								queryClient.invalidateQueries({
									queryKey: cacheKeys.logs.summary(Number(workspaceId)),
								});

								await refetchAllConnectors();
							} else {
								if (currentConnectorType === "CIRCLEBACK_CONNECTOR") {
									setConnectingConnectorType(null);
									setIndexingConfig(null);
									setIndexingConnector(null);
									setIndexingConnectorConfig(null);

									setEditingConnector(connector);
									setConnectorName(connector.name);
									setConnectorConfig(connector.config || {});
									setPeriodicEnabled(false);
									setFrequencyMinutes("1440");
									setEnableVisionLlm(connector.enable_vision_llm ?? false);
									setStartDate(undefined);
									setEndDate(undefined);
									setIsSaving(false);

									toast.success(`${connectorTitle} connected successfully!`, {
										description: "Configure the webhook URL in your Circleback settings.",
									});

									await refetchAllConnectors();
								} else {
									const successMessage =
										currentConnectorType === "MCP_CONNECTOR"
											? `${connector.name} added successfully`
											: `${connectorTitle} connected successfully!`;
									toast.success(successMessage);

									await refetchAllConnectors();

									setIsOpen(false);

									setIndexingConfig(null);
									setIndexingConnector(null);
									setIndexingConnectorConfig(null);
								}
							}
						}
					}
				}
			} catch (error) {
				console.error("Error creating connector:", error);
				trackConnectorSetupFailure(
					Number(workspaceId),
					connectingConnectorType ?? formData.connector_type,
					error instanceof Error ? error.message : "connector_create_failed",
					"non_oauth_form"
				);
				toast.error(error instanceof Error ? error.message : "Failed to create connector");
			} finally {
				isCreatingConnectorRef.current = false;
				setIsCreatingConnector(false);
			}
		},
		[
			workspaceId,
			connectingConnectorType,
			createConnector,
			refetchAllConnectors,
			updateConnector,
			indexConnector,
			setIsOpen,
			setIndexingConfig,
			setIndexingConnector,
			setIndexingConnectorConfig,
			setStartDate,
			setEndDate,
			setPeriodicEnabled,
			setFrequencyMinutes,
			setEnableVisionLlm,
			setEditingConnector,
			setConnectorName,
			setConnectorConfig,
			setConnectingConnectorType,
			setIsCreatingConnector,
			isCreatingConnectorRef,
			setIsSaving,
		]
	);

	const handleBackFromConnect = useCallback(() => {
		if (connectCameFromMCPList) {
			setViewingMCPList(true);
			setConnectCameFromMCPList(false);
		}
		setConnectingConnectorType(null);
	}, [
		connectCameFromMCPList,
		setViewingMCPList,
		setConnectCameFromMCPList,
		setConnectingConnectorType,
	]);

	return {
		handleCreateYouTubeCrawler,
		handleCreateWebcrawler,
		handleConnectNonOAuth,
		handleSubmitConnectForm,
		handleBackFromConnect,
		handleBackFromYouTube,
	};
}

export type ConnectorCreation = ReturnType<typeof useConnectorCreation>;

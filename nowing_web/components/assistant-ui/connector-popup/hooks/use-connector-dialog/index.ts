"use client";

import { useCallback, useEffect } from "react";
import { toast } from "sonner";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { searchSourceConnector } from "@/contracts/types/connector.types";
import { parseOAuthCallbackResult } from "@/contracts/types/oauth.types";
import { trackConnectorConnected, trackConnectorSetupFailure } from "@/lib/posthog/events";
import {
	AUTO_INDEX_CONNECTOR_TYPES,
	COMPOSIO_CONNECTORS,
	LIVE_CONNECTOR_TYPES,
	OAUTH_CONNECTORS,
} from "../../constants/connector-constants";
import { validateIndexingConfigState } from "../../constants/connector-popup.schemas";
import { clearOAuthResultCookie, readOAuthResultCookie } from "./constants";
import { useConnectorBase } from "./use-connector-base";
import { useConnectorCreation } from "./use-connector-creation";
import { useConnectorEdit } from "./use-connector-edit";
import { useConnectorIndexing } from "./use-connector-indexing";
import { useConnectorOAuth } from "./use-connector-oauth";

export function useConnectorDialog() {
	const base = useConnectorBase();
	const indexing = useConnectorIndexing({ base });
	const edit = useConnectorEdit({ base });
	const creation = useConnectorCreation({ base, indexing, edit });
	const oauth = useConnectorOAuth(base.workspaceId, base.setConnectingId);

	// Consume OAuth result from cookie (set by /connectors/callback route handler)
	useEffect(() => {
		const raw = readOAuthResultCookie();
		if (!raw || !base.workspaceId) return;
		clearOAuthResultCookie();

		const result = parseOAuthCallbackResult(raw);
		if (!result) return;

		if (result.error) {
			const oauthConnector = result.connector
				? OAUTH_CONNECTORS.find((c) => c.id === result.connector) ||
					COMPOSIO_CONNECTORS.find((c) => c.id === result.connector)
				: null;
			const name = oauthConnector?.title || "connector";

			if (oauthConnector) {
				trackConnectorSetupFailure(
					Number(base.workspaceId),
					oauthConnector.connectorType,
					result.error,
					"oauth_callback"
				);
			}

			if (result.error === "duplicate_account") {
				toast.error(`This ${name} account is already connected`, {
					description: "Please use a different account or manage the existing connection.",
				});
			} else {
				toast.error(`Failed to connect ${name}`, {
					description: result.error.replace(/_/g, " "),
				});
			}

			base.setIsOpen(true);
			return;
		}

		if (result.success === "true") {
			const earlyConnector = result.connector
				? OAUTH_CONNECTORS.find((c) => c.id === result.connector) ||
					COMPOSIO_CONNECTORS.find((c) => c.id === result.connector)
				: null;

			if (earlyConnector && AUTO_INDEX_CONNECTOR_TYPES.has(earlyConnector.connectorType)) {
				base.setIsOpen(false);
			}

			base.refetchAllConnectors().then(async (fetchResult) => {
				const data = (fetchResult as { data?: SearchSourceConnector[] | null }).data;
				if (!data) {
					toast.dismiss("auto-index");
					return;
				}

				let newConnector:
					| import("@/contracts/types/connector.types").SearchSourceConnector
					| undefined;
				let oauthConnector:
					| (typeof OAUTH_CONNECTORS)[number]
					| (typeof COMPOSIO_CONNECTORS)[number]
					| undefined;

				if (result.connectorId) {
					const connectorId = parseInt(result.connectorId, 10);
					newConnector = data.find((c: SearchSourceConnector) => c.id === connectorId);
					if (newConnector) {
						const connectorType = newConnector.connector_type;
						oauthConnector =
							OAUTH_CONNECTORS.find((c) => c.connectorType === connectorType) ||
							COMPOSIO_CONNECTORS.find((c) => c.connectorType === connectorType);
					}
				}

				if (!newConnector && result.connector) {
					oauthConnector =
						OAUTH_CONNECTORS.find((c) => c.id === result.connector) ||
						COMPOSIO_CONNECTORS.find((c) => c.id === result.connector);
					if (oauthConnector) {
						const oauthType = oauthConnector.connectorType;
						newConnector = data.find((c: SearchSourceConnector) => c.connector_type === oauthType);
					}
				}

				if (newConnector && oauthConnector) {
					const connectorValidation = searchSourceConnector.safeParse(newConnector);
					if (connectorValidation.success) {
						trackConnectorConnected(
							Number(base.workspaceId),
							oauthConnector.connectorType,
							newConnector.id
						);

						const isLiveConnector = LIVE_CONNECTOR_TYPES.has(oauthConnector.connectorType);

						if (isLiveConnector) {
							toast.dismiss("auto-index");
							toast.success(`${oauthConnector.title} connected successfully!`);
							await base.refetchAllConnectors();
						} else if (
							newConnector.is_indexable &&
							AUTO_INDEX_CONNECTOR_TYPES.has(oauthConnector.connectorType)
						) {
							await indexing.handleAutoIndex(
								newConnector,
								oauthConnector.title,
								oauthConnector.connectorType
							);
						} else if (!newConnector.is_indexable) {
							toast.dismiss("auto-index");
							toast.success(`${oauthConnector.title} connected successfully!`);
							await base.refetchAllConnectors();
						} else {
							toast.dismiss("auto-index");
							const config = validateIndexingConfigState({
								connectorType: oauthConnector.connectorType,
								connectorId: newConnector.id,
								connectorTitle: oauthConnector.title,
							});
							indexing.setIndexingConfig(config);
							indexing.setIndexingConnector(newConnector);
							indexing.setIndexingConnectorConfig(newConnector.config);
							indexing.setIsFromOAuth(true);
							base.setIsOpen(true);
						}
					} else {
						console.warn("Invalid connector data after OAuth:", connectorValidation.error);
						toast.dismiss("auto-index");
						toast.error("Failed to validate connector data");
					}
				} else {
					toast.dismiss("auto-index");
				}
			});
		}
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [
		base.workspaceId,
		indexing.handleAutoIndex,
		base.refetchAllConnectors,
		base.setIsOpen,
		indexing.setIndexingConfig,
		indexing.setIndexingConnector,
		indexing.setIndexingConnectorConfig,
		indexing.setIsFromOAuth,
	]);

	// Consume an import request from the Documents sidebar "Import" menu.
	// mode "connect" -> always OAuth connect (add account). mode "auto" routes by
	// account count: none -> connect, one -> edit view, many -> accounts list.
	useEffect(() => {
		if (!base.importConnectorRequest || !base.workspaceId) return;

		const { connectorType, mode } = base.importConnectorRequest;
		base.setImportConnectorRequest(null);

		const connectorDef =
			OAUTH_CONNECTORS.find((c) => c.connectorType === connectorType) ||
			COMPOSIO_CONNECTORS.find((c) => c.connectorType === connectorType);

		const existing = (base.allConnectors || []).filter(
			(c: SearchSourceConnector) => c.connector_type === connectorType
		);

		if (mode === "connect" || existing.length === 0) {
			if (connectorDef) {
				oauth.handleConnectOAuth(connectorDef);
			}
			return;
		}

		base.setIsOpen(true);
		if (existing.length === 1) {
			edit.handleStartEdit(existing[0]);
		} else {
			base.handleViewAccountsList(connectorType, connectorDef?.title);
		}
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [
		base.importConnectorRequest,
		base.workspaceId,
		base.allConnectors,
		base.setImportConnectorRequest,
		oauth.handleConnectOAuth,
		edit.handleStartEdit,
		base.handleViewAccountsList,
		base.setIsOpen,
	]);

	const handleOpenChange = useCallback(
		(open: boolean) => {
			base.setIsOpen(open);

			if (!open) {
				base.setIsScrolled(false);
				base.setSearchQuery("");
				base.setIsYouTubeView(false);
				indexing.setIsFromOAuth(false);
				if (
					!indexing.isStartingIndexing &&
					!edit.isSaving &&
					!edit.isDisconnecting &&
					!base.isCreatingConnector
				) {
					indexing.setIndexingConfig(null);
					indexing.setIndexingConnector(null);
					indexing.setIndexingConnectorConfig(null);
					edit.setEditingConnector(null);
					edit.setConnectorName(null);
					edit.setConnectorConfig(null);
					base.setConnectingConnectorType(null);
					base.setViewingAccountsType(null);
					base.setViewingMCPList(false);
					base.setCameFromAccountsList(null);
					base.setCameFromMCPList(false);
					base.setConnectCameFromMCPList(false);
					indexing.setStartDate(undefined);
					indexing.setEndDate(undefined);
					indexing.setPeriodicEnabled(false);
					indexing.setFrequencyMinutes("1440");
					indexing.setEnableVisionLlm(false);
				}
			}
		},
		[
			base,
			indexing.isStartingIndexing,
			edit.isSaving,
			edit.isDisconnecting,
			base.isCreatingConnector,
			indexing.setIsFromOAuth,
			indexing.setIndexingConfig,
			indexing.setIndexingConnector,
			indexing.setIndexingConnectorConfig,
			edit.setEditingConnector,
			edit.setConnectorName,
			edit.setConnectorConfig,
			indexing.setEnableVisionLlm,
			indexing.setEndDate,
			indexing.setFrequencyMinutes,
			indexing.setPeriodicEnabled,
			indexing.setStartDate,
		]
	);

	const handleTabChange = useCallback(
		(value: string) => {
			base.setActiveTab(value);
		},
		[base.setActiveTab]
	);

	const handleScroll = useCallback(
		(e: React.UIEvent<HTMLDivElement>) => {
			base.setIsScrolled(e.currentTarget.scrollTop > 0);
		},
		[base.setIsScrolled]
	);

	return {
		isOpen: base.isOpen,
		activeTab: base.activeTab,
		connectingId: base.connectingId,
		isScrolled: base.isScrolled,
		searchQuery: base.searchQuery,
		indexingConfig: indexing.indexingConfig,
		indexingConnector: indexing.indexingConnector,
		indexingConnectorConfig: indexing.indexingConnectorConfig,
		editingConnector: edit.editingConnector,
		connectingConnectorType: base.connectingConnectorType,
		isCreatingConnector: base.isCreatingConnector,
		startDate: indexing.startDate,
		endDate: indexing.endDate,
		isStartingIndexing: indexing.isStartingIndexing,
		isSaving: edit.isSaving,
		isDisconnecting: edit.isDisconnecting,
		periodicEnabled: indexing.periodicEnabled,
		frequencyMinutes: indexing.frequencyMinutes,
		enableVisionLlm: indexing.enableVisionLlm,
		workspaceId: base.workspaceId,
		allConnectors: base.allConnectors,
		viewingAccountsType: base.viewingAccountsType,
		viewingMCPList: base.viewingMCPList,
		isYouTubeView: base.isYouTubeView,
		isFromOAuth: indexing.isFromOAuth,

		setSearchQuery: base.setSearchQuery,
		setStartDate: indexing.setStartDate,
		setEndDate: indexing.setEndDate,
		setPeriodicEnabled: indexing.setPeriodicEnabled,
		setFrequencyMinutes: indexing.setFrequencyMinutes,
		setEnableVisionLlm: indexing.setEnableVisionLlm,
		setConnectorName: edit.setConnectorName,

		handleOpenChange,
		handleTabChange,
		handleScroll,
		handleConnectOAuth: oauth.handleConnectOAuth,
		handleConnectNonOAuth: creation.handleConnectNonOAuth,
		handleCreateWebcrawler: creation.handleCreateWebcrawler,
		handleCreateYouTubeCrawler: creation.handleCreateYouTubeCrawler,
		handleSubmitConnectForm: creation.handleSubmitConnectForm,
		handleAutoIndex: indexing.handleAutoIndex,
		handleStartIndexing: indexing.handleStartIndexing,
		handleSkipIndexing: indexing.handleSkipIndexing,
		handleStartEdit: edit.handleStartEdit,
		handleSaveConnector: edit.handleSaveConnector,
		handleDisconnectConnector: edit.handleDisconnectConnector,
		handleBackFromEdit: edit.handleBackFromEdit,
		handleBackFromConnect: creation.handleBackFromConnect,
		handleBackFromYouTube: creation.handleBackFromYouTube,
		handleViewAccountsList: base.handleViewAccountsList,
		handleBackFromAccountsList: base.handleBackFromAccountsList,
		handleViewMCPList: base.handleViewMCPList,
		handleBackFromMCPList: base.handleBackFromMCPList,
		handleAddNewMCPFromList: base.handleAddNewMCPFromList,
		handleQuickIndexConnector: indexing.handleQuickIndexConnector,
		connectorConfig: edit.connectorConfig,
		setConnectorConfig: edit.setConnectorConfig,
		setIndexingConnectorConfig: indexing.setIndexingConnectorConfig,
	};
}

"use client";

import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import type { IndexingConfigState } from "../../constants/connector-popup.schemas";

export type { IndexingConfigState } from "../../constants/connector-popup.schemas";

export interface AccountsViewState {
	connectorType: string;
	connectorTitle: string;
}

export interface UseConnectorDialogBase {
	workspaceId: string | null | undefined;
	allConnectors: SearchSourceConnector[] | undefined;
	refetchAllConnectors: () => Promise<unknown>;

	isOpen: boolean;
	setIsOpen: (open: boolean) => void;
	activeTab: string;
	setActiveTab: (value: string) => void;
	connectingId: string | null;
	setConnectingId: (id: string | null) => void;
	isScrolled: boolean;
	setIsScrolled: (scrolled: boolean) => void;
	searchQuery: string;
	setSearchQuery: (query: string) => void;
	isYouTubeView: boolean;
	setIsYouTubeView: (value: boolean) => void;

	importConnectorRequest: {
		connectorType: string;
		mode: "connect" | "auto";
	} | null;
	setImportConnectorRequest: (
		value: {
			connectorType: string;
			mode: "connect" | "auto";
		} | null
	) => void;

	isFromOAuth: boolean;
	setIsFromOAuth: (value: boolean) => void;

	viewingAccountsType: AccountsViewState | null;
	setViewingAccountsType: (value: AccountsViewState | null) => void;
	viewingMCPList: boolean;
	setViewingMCPList: (value: boolean) => void;
	cameFromAccountsList: AccountsViewState | null;
	setCameFromAccountsList: (value: AccountsViewState | null) => void;
	cameFromMCPList: boolean;
	setCameFromMCPList: (value: boolean) => void;
	connectCameFromMCPList: boolean;
	setConnectCameFromMCPList: (value: boolean) => void;
	connectingConnectorType: string | null;
	setConnectingConnectorType: (value: string | null) => void;
	isCreatingConnector: boolean;
	setIsCreatingConnector: (value: boolean) => void;
	isCreatingConnectorRef: React.MutableRefObject<boolean>;

	handleViewAccountsList: (connectorType: string, connectorTitle?: string) => void;
	handleBackFromAccountsList: () => void;
	handleViewMCPList: () => void;
	handleBackFromMCPList: () => void;
	handleAddNewMCPFromList: () => void;
}

export interface UseConnectorDialogIndexing {
	indexingConfig: IndexingConfigState | null;
	setIndexingConfig: (value: IndexingConfigState | null) => void;
	indexingConnector: SearchSourceConnector | null;
	setIndexingConnector: (value: SearchSourceConnector | null) => void;
	indexingConnectorConfig: Record<string, unknown> | null;
	setIndexingConnectorConfig: (value: Record<string, unknown> | null) => void;
	startDate: Date | undefined;
	setStartDate: (value: Date | undefined) => void;
	endDate: Date | undefined;
	setEndDate: (value: Date | undefined) => void;
	isStartingIndexing: boolean;
	setIsStartingIndexing: (value: boolean) => void;
	periodicEnabled: boolean;
	setPeriodicEnabled: (value: boolean) => void;
	frequencyMinutes: string;
	setFrequencyMinutes: (value: string) => void;
	enableVisionLlm: boolean;
	setEnableVisionLlm: (value: boolean) => void;
	isFromOAuth: boolean;
	setIsFromOAuth: (value: boolean) => void;
}

export interface UseConnectorDialogEdit {
	editingConnector: SearchSourceConnector | null;
	setEditingConnector: (value: SearchSourceConnector | null) => void;
	isSaving: boolean;
	setIsSaving: (value: boolean) => void;
	isDisconnecting: boolean;
	setIsDisconnecting: (value: boolean) => void;
	connectorConfig: Record<string, unknown> | null;
	setConnectorConfig: (value: Record<string, unknown> | null) => void;
	connectorName: string | null;
	setConnectorName: (value: string | null) => void;
}

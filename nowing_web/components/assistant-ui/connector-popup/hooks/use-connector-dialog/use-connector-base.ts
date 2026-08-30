"use client";

import { useAtom, useAtomValue } from "jotai";
import { useCallback, useRef, useState } from "react";
import {
	connectorDialogOpenAtom,
	importConnectorRequestAtom,
} from "@/atoms/connector-dialog/connector-dialog.atoms";
import { connectorsAtom } from "@/atoms/connectors/connector-query.atoms";
import { activeWorkspaceIdAtom } from "@/atoms/workspaces/workspace-query.atoms";
import { COMPOSIO_CONNECTORS, OAUTH_CONNECTORS } from "../../constants/connector-constants";
import type { AccountsViewState, UseConnectorDialogBase } from "./types";

export function useConnectorBase(): UseConnectorDialogBase {
	const workspaceId = useAtomValue(activeWorkspaceIdAtom);
	const { data: allConnectors, refetch: refetchAllConnectors } = useAtomValue(connectorsAtom);

	const [isOpen, setIsOpen] = useAtom(connectorDialogOpenAtom);
	const [importConnectorRequest, setImportConnectorRequest] = useAtom(importConnectorRequestAtom);
	const [activeTab, setActiveTab] = useState("all");
	const [connectingId, setConnectingId] = useState<string | null>(null);
	const [isScrolled, setIsScrolled] = useState(false);
	const [searchQuery, setSearchQuery] = useState("");
	const [isYouTubeView, setIsYouTubeView] = useState(false);
	const [isFromOAuth, setIsFromOAuth] = useState(false);

	const [viewingAccountsType, setViewingAccountsType] = useState<AccountsViewState | null>(null);
	const [viewingMCPList, setViewingMCPList] = useState(false);
	const [cameFromAccountsList, setCameFromAccountsList] = useState<AccountsViewState | null>(null);
	const [cameFromMCPList, setCameFromMCPList] = useState(false);
	const [connectCameFromMCPList, setConnectCameFromMCPList] = useState(false);
	const [connectingConnectorType, setConnectingConnectorType] = useState<string | null>(null);
	const [isCreatingConnector, setIsCreatingConnector] = useState(false);
	const isCreatingConnectorRef = useRef(false);

	const handleViewAccountsList = useCallback(
		(connectorType: string, _connectorTitle?: string) => {
			if (!workspaceId) return;

			const oauthConnector =
				OAUTH_CONNECTORS.find((c) => c.connectorType === connectorType) ||
				COMPOSIO_CONNECTORS.find((c) => c.connectorType === connectorType);
			if (oauthConnector) {
				setViewingAccountsType({
					connectorType: oauthConnector.connectorType,
					connectorTitle: oauthConnector.title,
				});
			}
		},
		[workspaceId]
	);

	const handleBackFromAccountsList = useCallback(() => {
		setViewingAccountsType(null);
	}, []);

	const handleViewMCPList = useCallback(() => {
		if (!workspaceId) return;
		setViewingMCPList(true);
	}, [workspaceId]);

	const handleBackFromMCPList = useCallback(() => {
		setViewingMCPList(false);
	}, []);

	const handleAddNewMCPFromList = useCallback(() => {
		setConnectCameFromMCPList(true);
		setViewingMCPList(false);
		setConnectingConnectorType("MCP_CONNECTOR");
	}, []);

	return {
		workspaceId,
		allConnectors,
		refetchAllConnectors,

		isOpen,
		setIsOpen,
		activeTab,
		setActiveTab,
		connectingId,
		setConnectingId,
		isScrolled,
		setIsScrolled,
		searchQuery,
		setSearchQuery,
		isYouTubeView,
		setIsYouTubeView,

		importConnectorRequest,
		setImportConnectorRequest,

		isFromOAuth,
		setIsFromOAuth,

		viewingAccountsType,
		setViewingAccountsType,
		viewingMCPList,
		setViewingMCPList,
		cameFromAccountsList,
		setCameFromAccountsList,
		cameFromMCPList,
		setCameFromMCPList,
		connectCameFromMCPList,
		setConnectCameFromMCPList,
		connectingConnectorType,
		setConnectingConnectorType,
		isCreatingConnector,
		setIsCreatingConnector,
		isCreatingConnectorRef,

		handleViewAccountsList,
		handleBackFromAccountsList,
		handleViewMCPList,
		handleBackFromMCPList,
		handleAddNewMCPFromList,
	};
}

export type ConnectorBase = ReturnType<typeof useConnectorBase>;

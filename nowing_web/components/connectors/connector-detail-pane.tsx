"use client";

import { useAtomValue } from "jotai";
import { Loader2, TriangleAlert } from "lucide-react";
import { useMemo } from "react";
import { connectorsAtom } from "@/atoms/connectors/connector-query.atoms";
import { statusInboxItemsAtom } from "@/atoms/inbox/status-inbox.atom";
import { ConnectorConnectView } from "@/components/assistant-ui/connector-popup/connector-configs/views/connector-connect-view";
import { ConnectorEditView } from "@/components/assistant-ui/connector-popup/connector-configs/views/connector-edit-view";
import {
	COMPOSIO_CONNECTORS,
	LIVE_CONNECTOR_TYPES,
	OAUTH_CONNECTORS,
} from "@/components/assistant-ui/connector-popup/constants/connector-constants";
import { useConnectorDialog } from "@/components/assistant-ui/connector-popup/hooks/use-connector-dialog";
import { useIndexingConnectors } from "@/components/assistant-ui/connector-popup/hooks/use-indexing-connectors";
import { ConnectorAccountsListView } from "@/components/assistant-ui/connector-popup/views/connector-accounts-list-view";
import { YouTubeCrawlerView } from "@/components/assistant-ui/connector-popup/views/youtube-crawler-view";
import { Button } from "@/components/ui/button";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { isConnectorIndexingMetadata } from "@/contracts/types/inbox.types";
import { useConnectorsSync } from "@/hooks/use-connectors-sync";
import { getConnectorTypeDisplay } from "@/lib/connectors/utils";
import { cn } from "@/lib/utils";

interface ConnectorDetailPaneProps {
	connectorType: string;
	workspaceId: string;
	onBack: () => void;
}

export function ConnectorDetailPane({
	connectorType,
	workspaceId,
	onBack,
}: ConnectorDetailPaneProps) {
	// Reuse the full connector dialog hook — it handles all view routing
	// (connect/edit/accounts) and mutations. The dialog itself is hidden on
	// the connectors page (client-layout.tsx: `!isConnectorsPage`), so
	// `isOpen` being true has no visible effect.
	const hook = useConnectorDialog();

	const { data: queryConnectors } = useAtomValue(connectorsAtom);
	const { connectors: syncConnectors } = useConnectorsSync(workspaceId);
	const connectors = useMemo<SearchSourceConnector[]>(
		() =>
			syncConnectors.length > 0
				? syncConnectors
				: ((queryConnectors ?? []) as SearchSourceConnector[]),
		[syncConnectors, queryConnectors]
	);

	const statusInboxItems = useAtomValue(statusInboxItemsAtom);
	const { indexingConnectorIds } = useIndexingConnectors(connectors, statusInboxItems);

	const groupConnectors = useMemo(
		() => connectors.filter((c) => c.connector_type === connectorType),
		[connectors, connectorType]
	);

	const accountCount = groupConnectors.length;
	const title = getConnectorTypeDisplay(connectorType);
	const isFailed = useMemo(() => {
		const failed = new Set<number>();
		for (const item of statusInboxItems) {
			if (item.type !== "connector_indexing") continue;
			const metadata = isConnectorIndexingMetadata(item.metadata) ? item.metadata : null;
			if (!metadata) continue;
			if (metadata.status === "failed" || metadata.error_message) {
				failed.add(metadata.connector_id);
			}
		}
		return groupConnectors.some((c) => failed.has(c.id));
	}, [statusInboxItems, groupConnectors]);
	const isSyncing = groupConnectors.some((c) => indexingConnectorIds.has(c.id));

	// Derive the active view from hook state — same priority as connector-popup.tsx
	const renderView = () => {
		if (hook.isYouTubeView && hook.workspaceId) {
			return (
				<YouTubeCrawlerView workspaceId={hook.workspaceId} onBack={hook.handleBackFromYouTube} />
			);
		}

		if (hook.viewingAccountsType) {
			return (
				<ConnectorAccountsListView
					connectorType={hook.viewingAccountsType.connectorType}
					connectorTitle={hook.viewingAccountsType.connectorTitle}
					connectors={connectors.filter(
						(c) => c.connector_type === hook.viewingAccountsType?.connectorType
					)}
					indexingConnectorIds={indexingConnectorIds}
					onBack={hook.handleBackFromAccountsList}
					onManage={hook.handleStartEdit}
					onAddAccount={() => {
						const oauthConnector =
							OAUTH_CONNECTORS.find(
								(c) => c.connectorType === hook.viewingAccountsType?.connectorType
							) ||
							COMPOSIO_CONNECTORS.find(
								(c) => c.connectorType === hook.viewingAccountsType?.connectorType
							);
						if (oauthConnector) hook.handleConnectOAuth(oauthConnector);
					}}
				/>
			);
		}

		if (hook.connectingConnectorType) {
			return (
				<ConnectorConnectView
					connectorType={hook.connectingConnectorType}
					onSubmit={(formData: Parameters<typeof hook.handleSubmitConnectForm>[0]) =>
						hook.handleSubmitConnectForm(formData, () => {})
					}
					onBack={hook.handleBackFromConnect}
					isSubmitting={hook.isCreatingConnector}
				/>
			);
		}

		if (hook.editingConnector) {
			return (
				<ConnectorEditView
					connector={{
						...hook.editingConnector,
						config: hook.connectorConfig || hook.editingConnector.config,
						name: hook.editingConnector.name,
						last_indexed_at:
							connectors.find((c) => c.id === hook.editingConnector?.id)?.last_indexed_at ??
							hook.editingConnector.last_indexed_at,
					}}
					startDate={hook.startDate}
					endDate={hook.endDate}
					periodicEnabled={hook.periodicEnabled}
					frequencyMinutes={hook.frequencyMinutes}
					enableVisionLlm={hook.enableVisionLlm}
					isSaving={hook.isSaving}
					isDisconnecting={hook.isDisconnecting}
					isIndexing={indexingConnectorIds.has(hook.editingConnector.id)}
					workspaceId={hook.workspaceId?.toString()}
					onStartDateChange={hook.setStartDate}
					onEndDateChange={hook.setEndDate}
					onPeriodicEnabledChange={hook.setPeriodicEnabled}
					onFrequencyChange={hook.setFrequencyMinutes}
					onEnableVisionLlmChange={hook.setEnableVisionLlm}
					onSave={() => hook.handleSaveConnector(() => {})}
					onDisconnect={() => hook.handleDisconnectConnector(() => {})}
					onBack={hook.handleBackFromEdit}
				/>
			);
		}

		// Default: show connector header + connect CTA (0 accounts) or accounts summary
		return (
			<div className="mt-8 flex flex-col items-center gap-4">
				{accountCount === 0 ? (
					<>
						<p className="text-sm text-muted-foreground">
							{LIVE_CONNECTOR_TYPES.has(connectorType as never)
								? "This connector requires OAuth authentication."
								: "Configure this connector to start importing data."}
						</p>
						<Button
							onClick={() => {
								const def =
									OAUTH_CONNECTORS.find((c) => c.connectorType === connectorType) ||
									COMPOSIO_CONNECTORS.find((c) => c.connectorType === connectorType);
								if (def) {
									hook.handleConnectOAuth(def);
								} else {
									hook.handleConnectNonOAuth(connectorType);
								}
							}}
						>
							Connect {title}
						</Button>
					</>
				) : (
					<Button onClick={() => hook.handleViewAccountsList(connectorType, title)}>
						View {accountCount} {accountCount === 1 ? "account" : "accounts"}
					</Button>
				)}
			</div>
		);
	};

	return (
		<div className="flex h-full flex-col p-5">
			<Button
				variant="ghost"
				size="sm"
				className="mb-4 w-fit -ml-2 text-muted-foreground hover:text-foreground"
				onClick={onBack}
			>
				← Back to catalog
			</Button>

			<div className="flex items-start gap-4">
				<div
					className={cn(
						"flex h-14 w-14 items-center justify-center rounded-xl border shrink-0",
						"bg-slate-400/5 dark:bg-white/5 border-slate-400/5 dark:border-white/5"
					)}
				>
					{getConnectorIcon(connectorType, "size-7")}
				</div>
				<div className="flex-1 min-w-0">
					<div className="flex items-center gap-2">
						<h2 className="text-lg font-semibold leading-tight truncate">{title}</h2>
						{isSyncing && (
							<span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
								<Loader2 className="size-3 animate-spin" />
								Syncing
							</span>
						)}
						{isFailed && (
							<span className="inline-flex items-center gap-1 rounded-full bg-destructive/10 px-2 py-0.5 text-[10px] font-medium text-destructive">
								<TriangleAlert className="size-3" />
								Failed
							</span>
						)}
					</div>
					<p className="mt-1 text-sm text-muted-foreground">
						{accountCount > 0 ? (
							<span>
								{accountCount} {accountCount === 1 ? "account" : "accounts"} connected
							</span>
						) : (
							<span>Not connected</span>
						)}
					</p>
				</div>
			</div>

			<div className="mt-6 flex-1 overflow-y-auto">{renderView()}</div>
		</div>
	);
}

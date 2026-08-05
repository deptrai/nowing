"use client";

import { ChevronLeft, Loader2, TriangleAlert } from "lucide-react";
import { useMemo } from "react";
import { Button } from "@/components/ui/button";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import type { ImportConnectorRequest } from "@/atoms/connector-dialog/connector-dialog.atoms";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { getConnectorTypeDisplay } from "@/lib/connectors/utils";
import { cn } from "@/lib/utils";

interface ConnectorDetailPaneProps {
	request: ImportConnectorRequest;
	connectors: SearchSourceConnector[];
	indexingConnectorIds: Set<number>;
	failedConnectorIds: Set<number>;
	onBack: () => void;
}

export function ConnectorDetailPane({
	request,
	connectors,
	indexingConnectorIds,
	failedConnectorIds,
	onBack,
}: ConnectorDetailPaneProps) {
	const groupConnectors = useMemo(
		() => connectors.filter((c) => c.connector_type === request.connectorType),
		[connectors, request.connectorType]
	);

	const accountCount = groupConnectors.length;
	const title = getConnectorTypeDisplay(request.connectorType);
	const isFailed = groupConnectors.some((c) => failedConnectorIds.has(c.id));
	const isSyncing = !isFailed && groupConnectors.some((c) => indexingConnectorIds.has(c.id));

	return (
		<div className="flex h-full flex-col p-5">
			<Button
				variant="ghost"
				size="sm"
				className="mb-4 w-fit -ml-2 text-muted-foreground hover:text-foreground"
				onClick={onBack}
			>
				<ChevronLeft className="size-4 mr-1" />
				Back to catalog
			</Button>

			<div className="flex items-start gap-4">
				<div
					className={cn(
						"flex h-14 w-14 items-center justify-center rounded-xl border shrink-0",
						"bg-slate-400/5 dark:bg-white/5 border-slate-400/5 dark:border-white/5"
					)}
				>
					{getConnectorIcon(request.connectorType, "size-7")}
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

			<div className="mt-8 rounded-xl border border-dashed border-border bg-slate-400/5 dark:bg-white/5 p-6 text-center">
				<p className="text-sm font-medium text-muted-foreground">Manage view</p>
				<p className="text-xs text-muted-foreground/60 mt-1">
					Full connect / edit / accounts flow for {title} is coming in the next pass.
				</p>
			</div>
		</div>
	);
}

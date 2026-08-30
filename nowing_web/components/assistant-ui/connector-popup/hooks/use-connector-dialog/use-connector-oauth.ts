"use client";

import { useCallback } from "react";
import { toast } from "sonner";
import { OAUTH_RESULT_COOKIE, type parseOAuthCallbackResult } from "@/contracts/types/oauth.types";
import { authenticatedFetch } from "@/lib/auth-fetch";
import { buildBackendUrl } from "@/lib/env-config";
import { trackConnectorSetupFailure, trackConnectorSetupStarted } from "@/lib/posthog/events";
import { COMPOSIO_CONNECTORS, OAUTH_CONNECTORS } from "../../constants/connector-constants";
import { parseOAuthAuthResponse } from "../../constants/connector-popup.schemas";

export interface UseConnectorOAuthResult {
	handleConnectOAuth: (
		connector: (typeof OAUTH_CONNECTORS)[number] | (typeof COMPOSIO_CONNECTORS)[number]
	) => Promise<void>;
	processOAuthResult: (
		result: ReturnType<typeof parseOAuthCallbackResult>,
		workspaceId: string
	) => void;
}

export function useConnectorOAuth(
	workspaceId: string | null | undefined,
	setConnectingId: (id: string | null) => void
): UseConnectorOAuthResult {
	const handleConnectOAuth = useCallback(
		async (connector: (typeof OAUTH_CONNECTORS)[number] | (typeof COMPOSIO_CONNECTORS)[number]) => {
			if (!workspaceId || !connector.authEndpoint) return;

			setConnectingId(connector.id);

			trackConnectorSetupStarted(Number(workspaceId), connector.connectorType, "oauth_click");

			try {
				const url = buildBackendUrl(connector.authEndpoint, { space_id: workspaceId });
				const response = await authenticatedFetch(url, { method: "GET" });

				if (!response.ok) {
					throw new Error(`Failed to initiate ${connector.title} OAuth`);
				}

				const data = await response.json();
				const validatedData = parseOAuthAuthResponse(data);

				window.location.href = validatedData.auth_url;
			} catch (error) {
				console.error(`Error connecting to ${connector.title}:`, error);
				trackConnectorSetupFailure(
					Number(workspaceId),
					connector.connectorType,
					error instanceof Error ? error.message : "oauth_initiation_failed",
					"oauth_init"
				);
				if (error instanceof Error && error.message.includes("Invalid auth URL")) {
					toast.error(`Invalid response from ${connector.title} OAuth endpoint`);
				} else {
					toast.error(`Failed to connect to ${connector.title}`);
				}
				setConnectingId(null);
			}
		},
		[workspaceId, setConnectingId]
	);

	const processOAuthResult = useCallback(
		(result: ReturnType<typeof parseOAuthCallbackResult>, workspaceId: string) => {
			if (!result) return;

			if (result.error) {
				const oauthConnector = result.connector
					? OAUTH_CONNECTORS.find((c) => c.id === result.connector) ||
						COMPOSIO_CONNECTORS.find((c) => c.id === result.connector)
					: null;
				const name = oauthConnector?.title || "connector";

				if (oauthConnector) {
					trackConnectorSetupFailure(
						Number(workspaceId),
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
			}
		},
		[]
	);

	return { handleConnectOAuth, processOAuthResult };
}

export { OAUTH_RESULT_COOKIE };

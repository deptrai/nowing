"use client";

import { useTranslations } from "next-intl";
import { useCallback } from "react";
import { toast } from "sonner";
import { OAUTH_RESULT_COOKIE, type parseOAuthCallbackResult } from "@/contracts/types/oauth.types";
import { authenticatedFetch } from "@/lib/auth-fetch";
import { BACKEND_URL, buildBackendUrl } from "@/lib/env-config";
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
	const t = useTranslations();
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

				// Only follow redirects to our own backend origin (auth_url is issued by the backend)
				const authUrl = new URL(validatedData.auth_url, window.location.origin);
				const backendOrigin = BACKEND_URL ? new URL(BACKEND_URL).origin : window.location.origin;
				if (authUrl.origin !== backendOrigin && authUrl.origin !== window.location.origin) {
					throw new Error("Invalid auth URL origin");
				}
				// pi-lens-ignore: ast-grep:no-open-redirect -- origin allowlisted above (backend-issued auth_url only)
				window.location.href = authUrl.toString();
			} catch (error) {
				console.error("[oauth] connect failed:", connector.connectorType, error);
				trackConnectorSetupFailure(
					Number(workspaceId),
					connector.connectorType,
					error instanceof Error ? error.message : "oauth_initiation_failed",
					"oauth_init"
				);
				if (error instanceof Error && error.message.includes("Invalid auth URL")) {
					toast.error(t("toast.oauth_invalid_response", { connector: connector.title }));
				} else {
					toast.error(t("toast.connect_failed", { connector: connector.title }));
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

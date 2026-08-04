/* eslint-disable no-console */
import posthog from "posthog-js";
import {
	identifyUser,
	resetUser,
	trackConnectorEvent,
	trackWorkspaceCreated,
	trackWorkspaceInviteAccepted,
	trackWorkspaceInviteDeclined,
	trackWorkspaceUserAdded,
} from "./events";

interface Captured {
	event: string;
	properties?: Record<string, unknown>;
}

const captured: Captured[] = [];
const identified: { userId: string; properties?: Record<string, unknown> }[] = [];

posthog.capture = ((event: string, properties?: Record<string, unknown>) => {
	captured.push({ event, properties });
}) as typeof posthog.capture;
posthog.identify = ((userId: string, properties?: Record<string, unknown>) => {
	identified.push({ userId, properties });
}) as typeof posthog.identify;
posthog.reset = (() => {
	identified.length = 0;
}) as typeof posthog.reset;

function assertNoKey(obj: Record<string, unknown> | undefined, key: string, label: string) {
	if (obj && key in obj) {
		throw new Error(`${label} must not contain "${key}"`);
	}
}

function assertHasKey(obj: Record<string, unknown> | undefined, key: string, label: string) {
	if (!obj || !(key in obj)) {
		throw new Error(`${label} should contain "${key}"`);
	}
}

function main() {
	trackWorkspaceCreated(42);
	const workspaceCreated = captured.find((c) => c.event === "workspace_created");
	if (!workspaceCreated) throw new Error("workspace_created not captured");
	assertNoKey(workspaceCreated.properties, "name", "workspace_created");
	assertHasKey(workspaceCreated.properties, "workspace_id", "workspace_created");

	trackWorkspaceInviteAccepted(42, "editor");
	const accepted = captured.find((c) => c.event === "workspace_invite_accepted");
	if (!accepted) throw new Error("workspace_invite_accepted not captured");
	assertNoKey(accepted.properties, "workspace_name", "workspace_invite_accepted");
	assertHasKey(accepted.properties, "workspace_id", "workspace_invite_accepted");
	assertHasKey(accepted.properties, "role_name", "workspace_invite_accepted");

	trackWorkspaceUserAdded(42, "editor");
	const added = captured.find((c) => c.event === "workspace_user_added");
	if (!added) throw new Error("workspace_user_added not captured");
	assertNoKey(added.properties, "workspace_name", "workspace_user_added");

	trackWorkspaceInviteDeclined(42);
	const declined = captured.find((c) => c.event === "workspace_invite_declined");
	if (!declined) throw new Error("workspace_invite_declined not captured");
	assertNoKey(declined.properties, "workspace_name", "workspace_invite_declined");
	assertHasKey(declined.properties, "workspace_id", "workspace_invite_declined");

	trackConnectorEvent("setup_started", "linear", { workspaceId: 42, source: "test" });
	const connector = captured.find((c) => c.event === "connector_setup_started");
	if (!connector) throw new Error("connector_setup_started not captured");
	assertNoKey(connector.properties, "connector_title", "connector_setup_started");
	assertHasKey(connector.properties, "connector_type", "connector_setup_started");
	assertHasKey(connector.properties, "connector_group", "connector_setup_started");
	assertHasKey(connector.properties, "is_oauth", "connector_setup_started");

	identifyUser("user-123", {
		is_superuser: true,
		is_verified: true,
		is_internal_user: true,
	});
	const superuserIdentify = identified[0];
	if (!superuserIdentify) throw new Error("superuser identify not captured");
	if (superuserIdentify.userId !== "user-123") throw new Error("wrong user id");
	assertNoKey(superuserIdentify.properties, "email", "superuser identify");
	assertNoKey(superuserIdentify.properties, "name", "superuser identify");
	assertHasKey(superuserIdentify.properties, "is_internal_user", "superuser identify");

	identifyUser("user-456", {
		email: "user@nowing.net",
		name: "Regular User",
		is_superuser: false,
		is_verified: true,
	});
	const regularIdentify = identified[1];
	if (!regularIdentify) throw new Error("regular identify not captured");
	assertHasKey(regularIdentify.properties, "email", "regular identify");
	assertHasKey(regularIdentify.properties, "name", "regular identify");

	// safeCapture should swallow thrown errors from posthog.capture.
	posthog.capture = () => {
		throw new Error("capture exploded");
	};
	trackWorkspaceCreated(99); // should not throw

	resetUser();

	console.log("events.selfcheck passed");
}

main();

/**
 * Focused unit check for connector rail health states.
 *
 * Uses the same data shape as `connectorsAtom` and the health logic
 * extracted from `ConnectorRail` so the test stays dependency-light.
 * Run directly with `tsx`.
 */

import assert from "node:assert/strict";
import { getConnectorGroupHealth } from "@/components/connectors/connector-rail";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import {
	type ConnectorGroup,
	groupConnectorsByType,
} from "@/lib/connectors/group-connectors-by-type";

const baseConnector: Omit<SearchSourceConnector, "id" | "connector_type" | "name"> = {
	is_indexable: true,
	is_active: true,
	last_indexed_at: null,
	config: {},
	enable_vision_llm: false,
	periodic_indexing_enabled: false,
	indexing_frequency_minutes: null,
	next_scheduled_at: null,
	workspace_id: 1,
	user_id: "1",
	created_at: new Date().toISOString(),
};

const mockConnectors: SearchSourceConnector[] = [
	{ ...baseConnector, id: 1, connector_type: "GOOGLE_DRIVE_CONNECTOR", name: "Google Drive A" },
	{ ...baseConnector, id: 2, connector_type: "GOOGLE_DRIVE_CONNECTOR", name: "Google Drive B" },
	{ ...baseConnector, id: 3, connector_type: "GOOGLE_GMAIL_CONNECTOR", name: "Gmail" },
];

const groups: ConnectorGroup[] = groupConnectorsByType(mockConnectors);
const googleDrive = groups.find((g) => g.connectorType === "GOOGLE_DRIVE_CONNECTOR");
const gmail = groups.find((g) => g.connectorType === "GOOGLE_GMAIL_CONNECTOR");

assert.ok(googleDrive, "Google Drive group should exist");
assert.ok(gmail, "Gmail group should exist");

// No indexing or failures -> ok.
assert.equal(getConnectorGroupHealth(googleDrive, new Set(), new Set()), "ok");

// Any member failed -> the whole group is failed.
assert.equal(getConnectorGroupHealth(googleDrive, new Set(), new Set([2])), "failed");

// Any member indexing (and not failed) -> syncing.
assert.equal(getConnectorGroupHealth(gmail, new Set([3]), new Set()), "syncing");

// Failed takes precedence over indexing.
assert.equal(getConnectorGroupHealth(googleDrive, new Set([1]), new Set([2])), "failed");

console.log("connector-rail-health.test.ts: all assertions passed");

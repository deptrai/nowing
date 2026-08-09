import assert from "node:assert";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { groupConnectorsByType } from "./group-connectors-by-type";

function makeConnector(type: string, id: number): SearchSourceConnector {
	return {
		id,
		name: `${type} - account ${id}`,
		connector_type: type as SearchSourceConnector["connector_type"],
		is_indexable: true,
		is_active: true,
		last_indexed_at: null,
		config: {},
		enable_vision_llm: false,
		periodic_indexing_enabled: false,
		indexing_frequency_minutes: null,
		next_scheduled_at: null,
		workspace_id: 1,
		user_id: "u1",
		created_at: new Date().toISOString(),
	};
}

const notDeprecated = new Set<string>();

// Test 1: basic grouping
{
	const connectors = [
		makeConnector("SLACK_CONNECTOR", 1),
		makeConnector("SLACK_CONNECTOR", 2),
		makeConnector("NOTION_CONNECTOR", 3),
	];
	const groups = groupConnectorsByType(connectors, { deprecatedTypes: notDeprecated });
	assert.strictEqual(groups.length, 2);
	assert.strictEqual(groups[0].connectorType, "NOTION_CONNECTOR");
	assert.strictEqual(groups[0].connectors.length, 1);
	assert.strictEqual(groups[1].connectorType, "SLACK_CONNECTOR");
	assert.strictEqual(groups[1].connectors.length, 2);
}

// Test 2: empty input
{
	const groups = groupConnectorsByType([], { deprecatedTypes: notDeprecated });
	assert.deepStrictEqual(groups, []);
}

// Test 3: include display types
{
	const groups = groupConnectorsByType([makeConnector("NOTION_CONNECTOR", 1)], {
		displayTypes: ["SLACK_CONNECTOR", "NOTION_CONNECTOR"],
		deprecatedTypes: notDeprecated,
	});
	assert.strictEqual(groups.length, 2);
	const slack = groups.find((g) => g.connectorType === "SLACK_CONNECTOR");
	assert.ok(slack);
	assert.strictEqual(slack?.connectors.length, 0);
}

// Test 4: deprecated hidden unless connected
{
	const deprecated = new Set(["DISCORD_CONNECTOR"]);
	const groups = groupConnectorsByType([makeConnector("DISCORD_CONNECTOR", 1)], {
		displayTypes: ["DISCORD_CONNECTOR", "NOTION_CONNECTOR"],
		deprecatedTypes: deprecated,
	});
	assert.strictEqual(groups.length, 2); // Discord (connected) + Notion
	const discord = groups.find((g) => g.connectorType === "DISCORD_CONNECTOR");
	assert.ok(discord);

	const groupsNotConnected = groupConnectorsByType([], {
		displayTypes: ["DISCORD_CONNECTOR", "NOTION_CONNECTOR"],
		deprecatedTypes: deprecated,
	});
	assert.strictEqual(groupsNotConnected.length, 1); // Only Notion
	assert.strictEqual(groupsNotConnected[0].connectorType, "NOTION_CONNECTOR");
}

// Test 5: malformed rows with no connector_type are skipped
{
	const malformed = { ...makeConnector("SLACK_CONNECTOR", 1), connector_type: "" };
	const connectors = [malformed as SearchSourceConnector, makeConnector("NOTION_CONNECTOR", 2)];
	const groups = groupConnectorsByType(connectors, { deprecatedTypes: notDeprecated });
	assert.strictEqual(groups.length, 1);
	assert.strictEqual(groups[0].connectorType, "NOTION_CONNECTOR");
}

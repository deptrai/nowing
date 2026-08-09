import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { getConnectorTypeDisplay } from "./utils";

export interface ConnectorGroup {
	connectorType: string;
	title: string;
	connectors: SearchSourceConnector[];
}

export interface GroupConnectorsByTypeOptions {
	/** Connector type strings to show even if not currently connected (e.g. catalog definitions). */
	displayTypes?: string[];
	/** Deprecated types are hidden unless at least one connector is connected. */
	deprecatedTypes?: Set<string>;
}

/**
 * Groups a list of connected connectors by their `connector_type`.
 *
 * - Optionally includes additional `displayTypes` (for catalogs) with an empty
 *   connector list when none are connected.
 * - Deprecated connector types are hidden unless they have at least one
 *   connected account, keeping the catalog clean while still allowing existing
 *   accounts to be managed.
 * - Groups are sorted by display title.
 */
export function groupConnectorsByType(
	connectors: SearchSourceConnector[],
	options: GroupConnectorsByTypeOptions = {}
): ConnectorGroup[] {
	const groups = new Map<string, SearchSourceConnector[]>();

	for (const connector of connectors) {
		// Skip malformed connector rows that are missing a type, which would
		// otherwise create an "undefined" group and break downstream rendering.
		if (!connector.connector_type) continue;
		const list = groups.get(connector.connector_type);
		if (list) {
			list.push(connector);
		} else {
			groups.set(connector.connector_type, [connector]);
		}
	}

	if (options.displayTypes) {
		for (const type of options.displayTypes) {
			if (!groups.has(type)) {
				groups.set(type, []);
			}
		}
	}

	if (options.deprecatedTypes) {
		for (const [type, list] of groups) {
			if (options.deprecatedTypes.has(type) && list.length === 0) {
				groups.delete(type);
			}
		}
	}

	return Array.from(groups.entries())
		.map(([connectorType, connectors]) => ({
			connectorType,
			title: getConnectorTypeDisplay(connectorType),
			connectors,
		}))
		.sort((a, b) =>
			String(a.title || a.connectorType).localeCompare(String(b.title || b.connectorType))
		);
}

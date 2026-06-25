import type { ThreadMessageLike } from "@assistant-ui/react";
import type { SankeyLink, SankeyNode, SmartMoneyFlowData } from "./streaming-state";
import type { MessageRecord } from "./thread-persistence";

/**
 * Convert backend message to assistant-ui ThreadMessageLike format.
 * Migrates legacy `thinking-steps` parts to `data-thinking-steps` (assistant-ui data parts).
 */
export function convertToThreadMessage(msg: MessageRecord): ThreadMessageLike {
	let content: ThreadMessageLike["content"];

	if (typeof msg.content === "string") {
		content = [{ type: "text", text: msg.content }];
	} else if (Array.isArray(msg.content)) {
		const convertedContent = msg.content
			.filter((part: unknown) => {
				if (typeof part !== "object" || part === null || !("type" in part)) return true;
				const partType = (part as { type: string }).type;
				return (
					partType !== "mentioned-documents" &&
					partType !== "attachments" &&
					partType !== "data-citation-map" &&
					partType !== "data-smart-money-flow"
				);
			})
			.map((part: unknown) => {
				if (
					typeof part === "object" &&
					part !== null &&
					"type" in part &&
					(part as { type: string }).type === "thinking-steps"
				) {
					return {
						type: "data-thinking-steps",
						data: { steps: (part as { steps: unknown[] }).steps ?? [] },
					};
				}
				return part;
			});
		content =
			convertedContent.length > 0
				? (convertedContent as ThreadMessageLike["content"])
				: [{ type: "text", text: "" }];
	} else {
		content = [{ type: "text", text: String(msg.content) }];
	}

	// Extract citation_map from content parts (persisted as data-citation-map part)
	// so CryptoCitationProvider has it after page reload
	let citationMap: Record<string, unknown> | undefined;
	let agentResults: Array<{ agentId: string; resultText: string; truncated: boolean }> | undefined;
	let smartMoneyFlow: SmartMoneyFlowData | undefined;
	if (Array.isArray(msg.content)) {
		for (const part of msg.content) {
			if (
				typeof part === "object" &&
				part !== null &&
				"type" in part &&
				(part as { type: string }).type === "data-citation-map"
			) {
				const mapPart = part as { type: string; data?: { citation_map?: Record<string, unknown> } };
				if (mapPart.data?.citation_map) {
					citationMap = mapPart.data.citation_map;
				}
			}
			if (
				typeof part === "object" &&
				part !== null &&
				"type" in part &&
				(part as { type: string }).type === "data-agent-results"
			) {
				const arPart = part as {
					type: string;
					data?: { results?: Array<{ agentId: string; resultText: string; truncated: boolean }> };
				};
				if (arPart.data?.results) {
					agentResults = arPart.data.results;
				}
			}
			if (
				typeof part === "object" &&
				part !== null &&
				"type" in part &&
				(part as { type: string }).type === "data-smart-money-flow"
			) {
				const smfPart = part as {
					type: string;
					data?: {
						nodes?: unknown;
						links?: unknown;
						net_flow_amount?: unknown;
						currency?: unknown;
						source_domain?: unknown;
						cohort_summary?: unknown;
					};
				};
				if (Array.isArray(smfPart.data?.nodes)) {
					smartMoneyFlow = {
						nodes: smfPart.data.nodes as SankeyNode[],
						links: Array.isArray(smfPart.data.links) ? (smfPart.data.links as SankeyLink[]) : [],
						net_flow_amount: Number(smfPart.data.net_flow_amount ?? 0) || 0,
						currency: typeof smfPart.data.currency === "string" ? smfPart.data.currency : "USD",
						source_domain:
							typeof smfPart.data.source_domain === "string"
								? smfPart.data.source_domain
								: undefined,
						cohort_summary:
							smfPart.data.cohort_summary &&
							typeof smfPart.data.cohort_summary === "object" &&
							!Array.isArray(smfPart.data.cohort_summary)
								? (smfPart.data.cohort_summary as SmartMoneyFlowData["cohort_summary"])
								: undefined,
					};
				}
			}
		}
	}

	const metadata =
		msg.author_id || citationMap || agentResults || smartMoneyFlow
			? {
					custom: {
						...(msg.author_id
							? {
									author: {
										displayName: msg.author_display_name ?? null,
										avatarUrl: msg.author_avatar_url ?? null,
									},
								}
							: {}),
						...(citationMap ? { citation_map: citationMap } : {}),
						...(agentResults ? { agent_results: agentResults } : {}),
						...(smartMoneyFlow ? { smart_money_flow: smartMoneyFlow } : {}),
					},
				}
			: undefined;

	return {
		id: `msg-${msg.id}`,
		role: msg.role,
		content,
		createdAt: new Date(msg.created_at),
		metadata,
	};
}

import type { InboxItem } from "@/contracts/types/inbox.types";

export interface InboxNotificationGroup {
	alert_rule_id: string;
	rule_name: string;
	match_count: number;
	items: InboxItem[];
	latest_created_at: string;
	unread: boolean;
}

/**
 * Group ``alert_run_complete`` inbox items by ``alert_rule_id``.
 *
 * Returns groups ordered by the most recent item in each rule, newest first.
 * Non-alert items are returned unchanged so the caller can interleave them
 * or render them separately.
 */
export function groupInboxNotifications(items: InboxItem[]): {
	groups: InboxNotificationGroup[];
	others: InboxItem[];
} {
	const groups = new Map<string, InboxNotificationGroup>();
	const others: InboxItem[] = [];

	for (const item of items) {
		if (item.type !== "alert_run_complete") {
			others.push(item);
			continue;
		}

		const meta = item.metadata as Record<string, unknown>;
		const ruleId = typeof meta?.alert_rule_id === "string" ? meta.alert_rule_id : null;
		if (!ruleId) {
			others.push(item);
			continue;
		}

		const ruleName = typeof meta?.rule_name === "string" ? meta.rule_name : "Saved search";
		const rawCount = meta?.new_items_count;
		let count = 0;
		if (typeof rawCount === "number") {
			count = rawCount;
		} else if (typeof rawCount === "string") {
			const parsed = parseInt(rawCount, 10);
			count = Number.isNaN(parsed) ? 0 : parsed;
		}

		const existing = groups.get(ruleId);
		if (existing) {
			existing.match_count += count;
			existing.items.push(item);
			if (item.created_at > existing.latest_created_at) {
				existing.latest_created_at = item.created_at;
			}
			if (!item.read) {
				existing.unread = true;
			}
		} else {
			groups.set(ruleId, {
				alert_rule_id: ruleId,
				rule_name: ruleName,
				match_count: count,
				items: [item],
				latest_created_at: item.created_at,
				unread: !item.read,
			});
		}
	}

	const sortedGroups = Array.from(groups.values()).sort(
		(a, b) => new Date(b.latest_created_at).getTime() - new Date(a.latest_created_at).getTime()
	);

	return { groups: sortedGroups, others };
}

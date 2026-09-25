import type { Context } from "@/types/zero";

type SpaceScopedQuery = {
	where: (...args: unknown[]) => SpaceScopedQuery;
};

export function canReadSpace(ctx: Context, workspaceId: number): boolean {
	return !!ctx?.allowedSpaceIds?.includes(workspaceId);
}

export function denySpace<T extends SpaceScopedQuery>(query: T): T {
	return query.where(({ or }: { or: (...args: unknown[]) => unknown }) => or()) as T;
}

export function constrainToAllowedSpaces<T extends SpaceScopedQuery>(query: T, ctx: Context): T {
	const allowedSpaceIds = ctx?.allowedSpaceIds ?? [];
	if (allowedSpaceIds.length === 0) {
		return denySpace(query);
	}
	// Use a single IN clause instead of chaining or(cmp(workspaceId, id), ...).
	// An OR of N comparisons nests N-deep; for users who belong to many
	// workspaces (or a broad allowedSpaceIds list) that exceeds SQLite's
	// 1000-node expression depth limit and the query returns an empty replica.
	// `where(col, "IN", ids)` emits one flat expression regardless of N.
	return query.where("workspaceId", "IN", allowedSpaceIds) as T;
}

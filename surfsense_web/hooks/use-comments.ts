import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { chatCommentsApiService } from "@/lib/apis/chat-comments-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";

interface UseCommentsOptions {
	messageId: number;
	enabled?: boolean;
}

// ---------------------------------------------------------------------------
// Module-level coordination: when a batch request is in-flight, individual
// useComments queryFns piggy-back on it instead of making their own requests.
// ---------------------------------------------------------------------------
let _batchInflight: Promise<void> | null = null;
let _batchTargetIds = new Set<number>();

export function useComments({ messageId, enabled = true }: UseCommentsOptions) {
	const queryClient = useQueryClient();

	return useQuery({
		queryKey: cacheKeys.comments.byMessage(messageId),
		queryFn: async () => {
			// Yield one macro-task so the batch prefetch useEffect (which sets
			// _batchInflight) has a chance to fire before we decide to fetch.
			await new Promise<void>((r) => setTimeout(r, 0));

			if (_batchInflight && _batchTargetIds.has(messageId)) {
				await _batchInflight;
				const cached = queryClient.getQueryData(cacheKeys.comments.byMessage(messageId));
				if (cached) return cached;
			}

			return chatCommentsApiService.getComments({ message_id: messageId });
		},
		enabled: enabled && !!messageId,
		staleTime: 30_000,
	});
}

/**
 * Batch-fetch comments for all given message IDs in a single request, then
 * seed the per-message React Query cache so individual useComments hooks
 * resolve from cache instead of firing their own requests.
 */
export function useBatchCommentsPreload(messageIds: number[]) {
	const queryClient = useQueryClient();
	const prevKeyRef = useRef<string>("");

	useEffect(() => {
		if (!messageIds.length) return;

		const key = messageIds
			.slice()
			.sort((a, b) => a - b)
			.join(",");
		if (key === prevKeyRef.current) return;
		prevKeyRef.current = key;

		_batchTargetIds = new Set(messageIds);
		let cancelled = false;

		const promise = chatCommentsApiService
			.getBatchComments({ message_ids: messageIds })
			.then((data) => {
				if (cancelled) return;
				for (const [msgIdStr, commentList] of Object.entries(data.comments_by_message)) {
					queryClient.setQueryData(cacheKeys.comments.byMessage(Number(msgIdStr)), commentList);
				}
			})
			.catch(() => {
				// Batch failed; individual queryFns will fall through to their own fetch
			})
			.finally(() => {
				if (_batchInflight === promise) {
					_batchInflight = null;
					_batchTargetIds = new Set();
				}
			});

		_batchInflight = promise;

		return () => {
			cancelled = true;
			if (_batchInflight === promise) {
				_batchInflight = null;
				_batchTargetIds = new Set();
			}
		};
	}, [messageIds, queryClient]);
}

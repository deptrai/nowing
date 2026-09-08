"use client";

import {
	type MemoryBrowserCreatorListResponse,
	type MemoryBrowserDetailResponse,
	type MemoryBrowserListResponse,
	type MemoryBrowserQuery,
	type MemoryBrowserTimelineResponse,
	type MemoryRelationListResponse,
	type MemoryReviewQueueRead,
	type MemoryVersionListResponse,
	memoryBrowserCreatorListResponseSchema,
	memoryBrowserDetailResponseSchema,
	memoryBrowserListResponseSchema,
	memoryBrowserTimelineResponseSchema,
	memoryRelationListResponseSchema,
	memoryReviewQueueReadSchema,
	memoryVersionListResponseSchema,
} from "@/contracts/types/memory-browser.types";
import { baseApiService } from "./base-api.service";

class MemoryBrowserApiService {
	/**
	 * List memories for a workspace with filters and pagination.
	 */
	listMemories = async (
		workspaceId: number,
		query: MemoryBrowserQuery = {}
	): Promise<MemoryBrowserListResponse> => {
		const params = new URLSearchParams();
		if (query.page) params.set("page", String(query.page));
		if (query.page_size) params.set("page_size", String(query.page_size));
		if (query.source_types) params.set("source_types", query.source_types);
		if (query.confidence_min !== undefined)
			params.set("confidence_min", String(query.confidence_min));
		if (query.confidence_max !== undefined)
			params.set("confidence_max", String(query.confidence_max));
		if (query.created_after) params.set("created_after", query.created_after);
		if (query.created_before) params.set("created_before", query.created_before);
		if (query.created_by) params.set("created_by", query.created_by);
		if (query.keyword) params.set("keyword", query.keyword);
		if (query.sort) params.set("sort", query.sort);
		if (query.sort_dir) params.set("sort_dir", query.sort_dir);

		const url = `/api/v1/workspaces/${workspaceId}/memory-browser${params.toString() ? `?${params.toString()}` : ""}`;
		return baseApiService.get(url, memoryBrowserListResponseSchema);
	};

	/**
	 * Get memory detail for the browser detail panel.
	 */
	getMemoryDetail = async (
		workspaceId: number,
		memoryId: number
	): Promise<MemoryBrowserDetailResponse> => {
		const url = `/api/v1/workspaces/${workspaceId}/memory-browser/${memoryId}`;
		return baseApiService.get(url, memoryBrowserDetailResponseSchema);
	};

	/**
	 * Get distinct memory creators for the creator filter dropdown (AC-2.4).
	 */
	listCreators = async (workspaceId: number): Promise<MemoryBrowserCreatorListResponse> => {
		const url = `/api/v1/workspaces/${workspaceId}/memory-browser/creators`;
		return baseApiService.get(url, memoryBrowserCreatorListResponseSchema);
	};

	/**
	 * Get research timeline: memories grouped by research thread (AC-4).
	 */
	getTimeline = async (workspaceId: number): Promise<MemoryBrowserTimelineResponse> => {
		const url = `/api/v1/workspaces/${workspaceId}/memory-browser/timeline`;
		return baseApiService.get(url, memoryBrowserTimelineResponseSchema);
	};

	/**
	 * Get version history for a memory (AC-3.3).
	 */
	getMemoryVersions = async (
		workspaceId: number,
		memoryId: number
	): Promise<MemoryVersionListResponse> => {
		const url = `/api/v1/workspaces/${workspaceId}/memory-browser/${memoryId}/versions`;
		return baseApiService.get(url, memoryVersionListResponseSchema);
	};

	/**
	 * Get related memories for a given memory (AC-3.5).
	 */
	getMemoryRelations = async (
		workspaceId: number,
		memoryId: number
	): Promise<MemoryRelationListResponse> => {
		const url = `/api/v1/workspaces/${workspaceId}/memory-browser/${memoryId}/relations`;
		return baseApiService.get(url, memoryRelationListResponseSchema);
	};

	/**
	 * Flag a memory for review by owners/editors.
	 */
	flagForReview = async (
		workspaceId: number,
		memoryId: number,
		flagReason: string
	): Promise<MemoryReviewQueueRead> => {
		const url = `/api/v1/workspaces/${workspaceId}/memory-browser/${memoryId}/review-flag`;
		return baseApiService.post(url, memoryReviewQueueReadSchema, {
			body: { flag_reason: flagReason },
		});
	};
}

export const memoryBrowserApiService = new MemoryBrowserApiService();

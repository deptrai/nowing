"use client";

import { z } from "zod";
import {
  memoryBrowserListResponseSchema,
  memoryBrowserDetailResponseSchema,
  memoryReviewQueueReadSchema,
  type MemoryBrowserQuery,
  type MemoryBrowserListResponse,
  type MemoryBrowserDetailResponse,
  type MemoryReviewQueueRead,
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
    if (query.confidence_min !== undefined) params.set("confidence_min", String(query.confidence_min));
    if (query.confidence_max !== undefined) params.set("confidence_max", String(query.confidence_max));
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
   * Flag a memory for review by owners/editors.
   */
  flagForReview = async (
    workspaceId: number,
    memoryId: number,
    flagReason: string
  ): Promise<MemoryReviewQueueRead> => {
    const url = `/api/v1/workspaces/${workspaceId}/memory-browser/${memoryId}/flag`;
    return baseApiService.post(url, memoryReviewQueueReadSchema, {
      body: { flag_reason: flagReason },
    });
  };
}

export const memoryBrowserApiService = new MemoryBrowserApiService();

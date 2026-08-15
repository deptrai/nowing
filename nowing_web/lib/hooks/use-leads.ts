"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import type { Lead, ListLeadsParams } from "@/contracts/types/leads.types";
import { leadsApiService } from "@/lib/apis/leads-api.service";

export interface UseLeadsReturn {
	leads: Lead[];
	total: number;
	loading: boolean;
	error: string | null;
	refetch: () => Promise<void>;
	updateStatus: (leadId: string, newStatus: string) => Promise<boolean>;
}

export function useLeads(
	workspaceId: number | string,
	params: ListLeadsParams = {}
): UseLeadsReturn {
	const [leads, setLeads] = useState<Lead[]>([]);
	const [total, setTotal] = useState<number>(0);
	const [loading, setLoading] = useState<boolean>(true);
	const [error, setError] = useState<string | null>(null);

	const { client_id, source, intent, min_score, status, search, sort, limit, offset } = params;

	const fetchLeads = useCallback(async () => {
		if (!workspaceId) return;
		setLoading(true);
		setError(null);
		try {
			const res = await leadsApiService.listLeads(workspaceId, {
				client_id,
				source,
				intent,
				min_score,
				status,
				search,
				sort,
				limit,
				offset,
			});
			setLeads(res.items);
			setTotal(res.total);
		} catch (err) {
			console.error("Error fetching leads:", err);
			setError("Không thể tải danh sách leads. Vui lòng thử lại.");
		} finally {
			setLoading(false);
		}
	}, [workspaceId, client_id, source, intent, min_score, status, search, sort, limit, offset]);

	useEffect(() => {
		fetchLeads();
	}, [fetchLeads]);

	// Optimistic Status Update (Zero-Cache pattern)
	const updateStatus = useCallback(
		async (leadId: string, newStatus: string): Promise<boolean> => {
			const previousLeads = [...leads];

			// 1. Apply optimistic update immediately
			setLeads((prev) =>
				prev.map((item) =>
					item.id === leadId
						? { ...item, status: newStatus, updated_at: new Date().toISOString() }
						: item
				)
			);

			try {
				// 2. Dispatch network update
				await leadsApiService.updateLeadStatus(workspaceId, leadId, newStatus);
				toast.success(`Đã cập nhật trạng thái sang "${newStatus}"`, { duration: 1500 });
				return true;
			} catch (err) {
				console.error("Failed to update status, rolling back:", err);
				// 3. Rollback on failure
				setLeads(previousLeads);
				toast.error("Cập nhật trạng thái thất bại. Đã khôi phục dữ liệu.");
				return false;
			}
		},
		[workspaceId, leads]
	);

	return {
		leads,
		total,
		loading,
		error,
		refetch: fetchLeads,
		updateStatus,
	};
}

"use client";

import { useCallback, useEffect, useState } from "react";
import type {
	WorkspaceTable,
	WorkspaceTableCreate,
	WorkspaceTableUpdate,
} from "@/contracts/types/workspace-table.types";
import { workspaceTablesApiService } from "@/lib/apis/workspace-tables-api.service";

export interface UseWorkspaceTablesResult {
	tables: WorkspaceTable[];
	loading: boolean;
	error: string | null;
	refetch: () => Promise<void>;
	createTable: (payload: WorkspaceTableCreate) => Promise<WorkspaceTable | null>;
	updateTable: (tableId: string, payload: WorkspaceTableUpdate) => Promise<WorkspaceTable | null>;
	deleteTable: (tableId: string) => Promise<boolean>;
}

export function useWorkspaceTables(workspaceId: number | string): UseWorkspaceTablesResult {
	const [tables, setTables] = useState<WorkspaceTable[]>([]);
	const [loading, setLoading] = useState<boolean>(true);
	const [error, setError] = useState<string | null>(null);

	const fetchTables = useCallback(async () => {
		if (!workspaceId) return;
		try {
			setLoading(true);
			setError(null);
			const data = await workspaceTablesApiService.listTables(workspaceId);
			setTables(data);
		} catch (err: unknown) {
			const msg = err instanceof Error ? err.message : "Không thể tải danh sách bảng";
			setError(msg);
		} finally {
			setLoading(false);
		}
	}, [workspaceId]);

	useEffect(() => {
		fetchTables();
	}, [fetchTables]);

	const createTable = useCallback(
		async (payload: WorkspaceTableCreate): Promise<WorkspaceTable | null> => {
			try {
				const created = await workspaceTablesApiService.createTable(workspaceId, payload);
				setTables((prev) => [...prev, created]);
				return created;
			} catch (err: unknown) {
				const msg = err instanceof Error ? err.message : "Tạo bảng thất bại";
				setError(msg);
				return null;
			}
		},
		[workspaceId]
	);

	const updateTable = useCallback(
		async (tableId: string, payload: WorkspaceTableUpdate): Promise<WorkspaceTable | null> => {
			try {
				const updated = await workspaceTablesApiService.updateTable(workspaceId, tableId, payload);
				setTables((prev) => prev.map((t) => (t.id === tableId ? updated : t)));
				return updated;
			} catch (err: unknown) {
				const msg = err instanceof Error ? err.message : "Cập nhật bảng thất bại";
				setError(msg);
				return null;
			}
		},
		[workspaceId]
	);

	const deleteTable = useCallback(
		async (tableId: string): Promise<boolean> => {
			try {
				await workspaceTablesApiService.deleteTable(workspaceId, tableId);
				setTables((prev) => prev.filter((t) => t.id !== tableId));
				return true;
			} catch (err: unknown) {
				const msg = err instanceof Error ? err.message : "Xóa bảng thất bại";
				setError(msg);
				return false;
			}
		},
		[workspaceId]
	);

	return {
		tables,
		loading,
		error,
		refetch: fetchTables,
		createTable,
		updateTable,
		deleteTable,
	};
}

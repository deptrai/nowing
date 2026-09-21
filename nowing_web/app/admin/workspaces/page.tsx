"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { adminUsersApiService } from "@/lib/apis/admin-users-api.service";

interface WorkspaceItem {
	id: number;
	name: string;
	description: string | null;
	vertical: string | null;
	created_at: string | null;
	user_id: string | null;
	citations_enabled: boolean;
	api_access_enabled: boolean;
	qna_custom_instructions: string | null;
	member_count: number;
	is_owner: boolean;
}

export default function AdminWorkspacesPage() {
	const t = useTranslations("admin");
	const [workspaces, setWorkspaces] = useState<WorkspaceItem[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [search, setSearch] = useState("");

	const loadWorkspaces = useCallback(async () => {
		try {
			setLoading(true);
			const data = await adminUsersApiService.listWorkspaces();
			setWorkspaces(data);
		} catch (e) {
			setError(e instanceof Error ? e.message : t("workspaces_load_failed"));
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		void loadWorkspaces();
	}, [loadWorkspaces]);

	const filtered = workspaces.filter((w) => w.name.toLowerCase().includes(search.toLowerCase()));

	return (
		<div className="p-8">
			<h1 className="text-2xl font-bold mb-4">{t("workspaces_title")}</h1>
			<div className="flex gap-4 mb-4 flex-wrap items-end">
				<div className="p-4 border rounded">
					<div className="text-sm text-gray-500">{t("workspaces_total")}</div>
					<div className="text-xl font-semibold">{workspaces.length}</div>
				</div>
				<div className="flex-1 min-w-[200px]">
					<label htmlFor="workspace-search" className="block text-sm text-gray-500 mb-1">
						{t("workspaces_search_label")}
					</label>
					<input
						id="workspace-search"
						type="text"
						value={search}
						onChange={(e) => setSearch(e.target.value)}
						placeholder={t("workspaces_search_placeholder")}
						className="w-full border rounded px-3 py-2 text-sm"
					/>
				</div>
			</div>
			<div className="border rounded p-4 overflow-auto max-h-[600px]">
				{loading && <div className="text-sm text-gray-500">{t("workspaces_loading")}</div>}
				{error && <div className="text-sm text-red-600">{error}</div>}
				<table className="w-full text-sm">
					<thead>
						<tr>
							<th className="text-left border-b p-2">{t("workspaces_col_name")}</th>
							<th className="text-left border-b p-2">{t("workspaces_col_vertical")}</th>
							<th className="text-left border-b p-2">{t("workspaces_col_members")}</th>
							<th className="text-left border-b p-2">{t("workspaces_col_api_access")}</th>
						</tr>
					</thead>
					<tbody>
						{filtered.map((ws) => (
							<tr key={ws.id}>
								<td className="p-2 border-b">{ws.name}</td>
								<td className="p-2 border-b">{ws.vertical ?? "—"}</td>
								<td className="p-2 border-b">{ws.member_count}</td>
								<td className="p-2 border-b">
									{ws.api_access_enabled ? t("workspaces_yes") : t("workspaces_no")}
								</td>
							</tr>
						))}
					</tbody>
				</table>
			</div>
		</div>
	);
}

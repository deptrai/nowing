"use client";

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
			setError(e instanceof Error ? e.message : "Failed to load workspaces");
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
			<h1 className="text-2xl font-bold mb-4">Admin Hub: Workspaces</h1>
			<div className="flex gap-4 mb-4 flex-wrap items-end">
				<div className="p-4 border rounded">
					<div className="text-sm text-gray-500">Total workspaces</div>
					<div className="text-xl font-semibold">{workspaces.length}</div>
				</div>
				<div className="flex-1 min-w-[200px]">
					<label htmlFor="workspace-search" className="block text-sm text-gray-500 mb-1">
						Search by name
					</label>
					<input
						id="workspace-search"
						type="text"
						value={search}
						onChange={(e) => setSearch(e.target.value)}
						placeholder="workspace name"
						className="w-full border rounded px-3 py-2 text-sm"
					/>
				</div>
			</div>
			<div className="border rounded p-4 overflow-auto max-h-[600px]">
				{loading && <div className="text-sm text-gray-500">Loading workspaces...</div>}
				{error && <div className="text-sm text-red-600">{error}</div>}
				<table className="w-full text-sm">
					<thead>
						<tr>
							<th className="text-left border-b p-2">Name</th>
							<th className="text-left border-b p-2">Vertical</th>
							<th className="text-left border-b p-2">Members</th>
							<th className="text-left border-b p-2">API access</th>
						</tr>
					</thead>
					<tbody>
						{filtered.map((ws) => (
							<tr key={ws.id}>
								<td className="p-2 border-b">{ws.name}</td>
								<td className="p-2 border-b">{ws.vertical ?? "—"}</td>
								<td className="p-2 border-b">{ws.member_count}</td>
								<td className="p-2 border-b">{ws.api_access_enabled ? "Yes" : "No"}</td>
							</tr>
						))}
					</tbody>
				</table>
			</div>
		</div>
	);
}

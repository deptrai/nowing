"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { useSession } from "@/hooks/use-session";
import { adminUsersApiService } from "@/lib/apis/admin-users-api.service";

interface UserItem {
	id: string;
	email: string;
	is_active: boolean;
	is_superuser: boolean;
	is_verified: boolean;
}

export default function AdminUsersPage() {
	const t = useTranslations("admin");
	const session = useSession();
	const [users, setUsers] = useState<UserItem[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [search, setSearch] = useState("");
	const [ticketRef, setTicketRef] = useState("");

	const loadUsers = useCallback(async () => {
		try {
			setLoading(true);
			const data = await adminUsersApiService.listUsers();
			setUsers(data);
		} catch (e) {
			setError(e instanceof Error ? e.message : t("failed_load_users"));
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		void loadUsers();
	}, [loadUsers]);

	const filtered = users.filter((u) => u.email.toLowerCase().includes(search.toLowerCase()));

	const handleImpersonate = async (userId: string) => {
		if (!ticketRef.trim()) {
			alert(t("enter_ticket_ref_alert"));
			return;
		}
		try {
			await adminUsersApiService.impersonate(userId, ticketRef.trim());
			await session.refresh();
			window.location.href = "/admin/users";
		} catch (e) {
			alert(e instanceof Error ? e.message : t("impersonation_failed"));
		}
	};

	return (
		<div className="p-8">
			<h1 className="text-2xl font-bold mb-4">{t("users_title")}</h1>
			<div className="flex gap-4 mb-4 flex-wrap items-end">
				<div className="p-4 border rounded">
					<div className="text-sm text-gray-500">{t("total_users")}</div>
					<div className="text-xl font-semibold">{users.length}</div>
				</div>
				<div className="flex-1 min-w-[200px]">
					<label htmlFor="user-search" className="block text-sm text-gray-500 mb-1">
						{t("search_by_email")}
					</label>
					<input
						id="user-search"
						type="text"
						value={search}
						onChange={(e) => setSearch(e.target.value)}
						placeholder="user@example.com"
						className="w-full border rounded px-3 py-2 text-sm"
					/>
				</div>
				<div className="flex-1 min-w-[200px]">
					<label htmlFor="ticket-ref" className="block text-sm text-gray-500 mb-1">
						{t("ticket_ref")}
					</label>
					<input
						id="ticket-ref"
						type="text"
						value={ticketRef}
						onChange={(e) => setTicketRef(e.target.value)}
						placeholder="https://jira.nowing.net/browse/SUPPORT-1234"
						className="w-full border rounded px-3 py-2 text-sm"
					/>
				</div>
			</div>
			<div className="border rounded p-4 overflow-auto max-h-[600px]">
				{loading && <div className="text-sm text-gray-500">{t("loading_users")}</div>}
				{error && <div className="text-sm text-red-600">{error}</div>}
				<table className="w-full text-sm">
					<thead>
						<tr>
							<th className="text-left border-b p-2">{t("col_email")}</th>
							<th className="text-left border-b p-2">{t("col_active")}</th>
							<th className="text-left border-b p-2">{t("col_superuser")}</th>
							<th className="text-left border-b p-2">{t("col_verified")}</th>
							<th className="text-left border-b p-2">{t("col_actions")}</th>
						</tr>
					</thead>
					<tbody>
						{filtered.map((user) => (
							<tr key={user.id}>
								<td className="p-2 border-b">{user.email}</td>
								<td className="p-2 border-b">{user.is_active ? t("yes") : t("no")}</td>
								<td className="p-2 border-b">{user.is_superuser ? t("yes") : t("no")}</td>
								<td className="p-2 border-b">{user.is_verified ? t("yes") : t("no")}</td>
								<td className="p-2 border-b">
									<button
										type="button"
										onClick={() => handleImpersonate(user.id)}
										className="text-blue-600 hover:underline mr-2"
									>
										{t("impersonate_btn")}
									</button>
								</td>
							</tr>
						))}
					</tbody>
				</table>
			</div>
		</div>
	);
}

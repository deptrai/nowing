"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { authenticatedFetch, isAuthenticated, redirectToLogin } from "@/lib/auth-utils";
import { BACKEND_URL } from "@/lib/env-config";

interface GiftRequestItem {
	id: string;
	user_id: string;
	user_email: string;
	plan_id: string;
	duration_months: number;
	status: string;
	gift_code_id: string | null;
	gift_code: string | null;
	created_at: string;
	updated_at: string | null;
}

interface GiftRequestApproveResponse {
	request_id: string;
	gift_code_id: string;
	gift_code: string;
	plan_id: string;
	duration_months: number;
}

const STATUS_TABS = ["pending", "approved", "rejected", "all"] as const;
type StatusTab = (typeof STATUS_TABS)[number];

export default function AdminGiftRequestsPage() {
	const [requests, setRequests] = useState<GiftRequestItem[]>([]);
	const [loading, setLoading] = useState(true);
	const [actionInProgress, setActionInProgress] = useState<string | null>(null);
	const [accessDenied, setAccessDenied] = useState(false);
	const [activeStatus, setActiveStatus] = useState<StatusTab>("pending");

	const fetchRequests = useCallback(
		async (signal?: AbortSignal) => {
			if (!isAuthenticated()) {
				redirectToLogin();
				return;
			}
			setLoading(true);
			setRequests([]);
			try {
				const response = await authenticatedFetch(
					`${BACKEND_URL}/api/v1/admin/gift-requests?status=${activeStatus}`,
					{ signal }
				);
				if (signal?.aborted) return;
				if (response.status === 401) {
					redirectToLogin();
					return;
				}
				if (response.status === 403) {
					setAccessDenied(true);
					return;
				}
				if (!response.ok) {
					const err = await response.json().catch(() => ({}));
					toast.error(err.detail ?? "Failed to load gift requests.");
					return;
				}
				const data: { items: GiftRequestItem[]; count: number } = await response.json();
				if (signal?.aborted) return;
				setRequests(data.items);
			} catch (err) {
				if ((err as { name?: string })?.name === "AbortError") return;
				toast.error("Failed to load gift requests.");
			} finally {
				if (!signal?.aborted) setLoading(false);
			}
		},
		[activeStatus]
	);

	useEffect(() => {
		const ctrl = new AbortController();
		fetchRequests(ctrl.signal);
		return () => ctrl.abort();
	}, [fetchRequests]);

	const handleApprove = async (requestId: string, email: string) => {
		if (!window.confirm(`Approve gift request for ${email}? A gift code will be minted.`)) {
			return;
		}
		setActionInProgress(requestId);
		try {
			const response = await authenticatedFetch(
				`${BACKEND_URL}/api/v1/admin/gift-requests/${requestId}/approve`,
				{ method: "POST" }
			);
			if (!response.ok) {
				const err = await response.json().catch(() => ({}));
				toast.error(err.detail ?? "Failed to approve request.");
				return;
			}
			const data: GiftRequestApproveResponse = await response.json();
			const code = data.gift_code;
			try {
				await navigator.clipboard.writeText(code);
				toast.success(`✅ Approved. Code: ${code} (copied to clipboard)`);
			} catch {
				toast.success(`✅ Approved. Code: ${code} — clipboard unavailable, copy manually`, {
					duration: Infinity,
				});
			}
			fetchRequests();
		} catch {
			toast.error("Failed to approve request.");
		} finally {
			setActionInProgress(null);
		}
	};

	const handleReject = async (requestId: string, email: string) => {
		const reason = window.prompt(`Reject gift request for ${email}? Reason (optional):`);
		if (reason === null) return;
		setActionInProgress(requestId);
		try {
			const response = await authenticatedFetch(
				`${BACKEND_URL}/api/v1/admin/gift-requests/${requestId}/reject`,
				{
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({ reason: reason || null }),
				}
			);
			if (!response.ok) {
				const err = await response.json().catch(() => ({}));
				toast.error(err.detail ?? "Failed to reject request.");
				return;
			}
			toast.info("Request rejected.");
			fetchRequests();
		} catch {
			toast.error("Failed to reject request.");
		} finally {
			setActionInProgress(null);
		}
	};

	const copyCode = async (code: string) => {
		try {
			await navigator.clipboard.writeText(code);
			toast.success(`Copied: ${code}`);
		} catch {
			toast.error("Clipboard unavailable.");
		}
	};

	if (accessDenied) {
		return (
			<div className="flex h-screen items-center justify-center">
				<p className="text-lg font-medium text-destructive">
					Access denied. Superuser privileges required.
				</p>
			</div>
		);
	}

	return (
		<div className="container mx-auto max-w-5xl py-10">
			<h1 className="mb-6 text-2xl font-bold">Gift Requests</h1>

			<div className="mb-4 flex gap-2">
				{STATUS_TABS.map((s) => (
					<button
						key={s}
						type="button"
						onClick={() => setActiveStatus(s)}
						className={`rounded px-3 py-1 text-sm font-medium capitalize transition-colors ${
							activeStatus === s ? "bg-indigo-600 text-white" : "bg-muted hover:bg-muted/80"
						}`}
					>
						{s}
					</button>
				))}
			</div>

			{loading ? (
				<p className="text-muted-foreground">Loading…</p>
			) : requests.length === 0 ? (
				<p className="text-muted-foreground">No {activeStatus} gift requests.</p>
			) : (
				<div className="overflow-x-auto rounded-lg border">
					<table className="w-full text-sm">
						<thead className="bg-muted/50">
							<tr>
								<th className="px-4 py-3 text-left font-medium">User</th>
								<th className="px-4 py-3 text-left font-medium">Plan</th>
								<th className="px-4 py-3 text-left font-medium">Duration</th>
								<th className="px-4 py-3 text-left font-medium">Status</th>
								<th className="px-4 py-3 text-left font-medium">Gift Code</th>
								<th className="px-4 py-3 text-left font-medium">Created</th>
								<th className="px-4 py-3 text-left font-medium">Actions</th>
							</tr>
						</thead>
						<tbody className="divide-y">
							{requests.map((req) => (
								<tr key={req.id} className="hover:bg-muted/30">
									<td className="px-4 py-3">{req.user_email}</td>
									<td className="px-4 py-3 capitalize">{req.plan_id.replace(/_/g, " ")}</td>
									<td className="px-4 py-3">
										{req.duration_months} {req.duration_months === 1 ? "month" : "months"}
									</td>
									<td className="px-4 py-3 capitalize">{req.status.toLowerCase()}</td>
									<td className="px-4 py-3 font-mono text-xs">
										{req.gift_code ? (
											<button
												type="button"
												onClick={() => copyCode(req.gift_code!)}
												className="rounded bg-muted px-2 py-1 hover:bg-muted/80"
												title="Copy"
											>
												{req.gift_code}
											</button>
										) : (
											<span className="text-muted-foreground">—</span>
										)}
									</td>
									<td className="px-4 py-3 text-xs text-muted-foreground">
										{new Date(req.created_at).toLocaleString()}
									</td>
									<td className="px-4 py-3">
										{req.status.toLowerCase() === "pending" ? (
											<div className="flex gap-2">
												<button
													type="button"
													className="rounded bg-green-600 px-3 py-1 text-xs font-medium text-white hover:bg-green-700 disabled:opacity-50"
													disabled={actionInProgress !== null}
													onClick={() => handleApprove(req.id, req.user_email)}
												>
													Approve
												</button>
												<button
													type="button"
													className="rounded bg-destructive px-3 py-1 text-xs font-medium text-white hover:opacity-90 disabled:opacity-50"
													disabled={actionInProgress !== null}
													onClick={() => handleReject(req.id, req.user_email)}
												>
													Reject
												</button>
											</div>
										) : (
											<span className="text-xs text-muted-foreground">—</span>
										)}
									</td>
								</tr>
							))}
						</tbody>
					</table>
				</div>
			)}
		</div>
	);
}

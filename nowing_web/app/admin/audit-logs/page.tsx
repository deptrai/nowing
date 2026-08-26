"use client";

import { Download, Eye, RefreshCw, Search, ShieldAlert } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import type {
	AuditEventRead,
	AuditLogFilterParams,
} from "@/contracts/types/admin-audit-logs.types";
import { adminAuditLogsApiService } from "@/lib/apis/admin-audit-logs-api.service";

function csvField(value: unknown): string {
	const s = value === null || value === undefined ? "" : String(value);
	if (s.includes(",") || s.includes('"') || s.includes("\n")) {
		return `"${s.replace(/"/g, '""')}"`;
	}
	return s;
}

function exportCsv(items: AuditEventRead[]) {
	const headers = [
		"id",
		"timestamp",
		"action",
		"actor_email",
		"subject_email",
		"ip_address",
		"user_agent",
		"ticket_ref",
		"endpoint",
		"diff_payload",
	];
	const rows = items.map((i) =>
		[
			i.id,
			i.created_at,
			i.action,
			i.actor_email || i.actor_id || "",
			i.subject_email || i.subject_id || "",
			i.ip_address || "",
			i.user_agent || "",
			i.ticket_ref || "",
			i.endpoint || "",
			i.diff_payload ? JSON.stringify(i.diff_payload) : "",
		]
			.map(csvField)
			.join(",")
	);
	const csvContent = [headers.map(csvField).join(","), ...rows].join("\n");
	const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
	const url = URL.createObjectURL(blob);
	const a = document.createElement("a");
	a.href = url;
	a.download = `audit-logs-${new Date().toISOString().slice(0, 10)}.csv`;
	a.click();
	URL.revokeObjectURL(url);
}

function getActionBadgeStyle(action: string) {
	if (action.startsWith("user.impersonate")) {
		return "bg-blue-500/10 text-blue-500 border-blue-500/20";
	}
	if (action.includes("delete") || action.includes("remove")) {
		return "bg-rose-500/10 text-rose-500 border-rose-500/20";
	}
	if (action.includes("create") || action.includes("add")) {
		return "bg-emerald-500/10 text-emerald-500 border-emerald-500/20";
	}
	if (action.includes("update") || action.includes("activate")) {
		return "bg-amber-500/10 text-amber-500 border-amber-500/20";
	}
	return "bg-zinc-500/10 text-zinc-400 border-zinc-500/20";
}

export default function AdminAuditLogsPage() {
	const [items, setItems] = useState<AuditEventRead[]>([]);
	const [total, setTotal] = useState(0);
	const [isLoading, setIsLoading] = useState(false);
	const [offset, setOffset] = useState(0);
	const [limit] = useState(50);

	const [actionFilter, setActionFilter] = useState("");
	const [searchActor, setSearchActor] = useState("");
	const [searchSubject, setSearchSubject] = useState("");
	const [ticketRefFilter, setTicketRefFilter] = useState("");
	const [startDate, setStartDate] = useState("");
	const [endDate, setEndDate] = useState("");

	const [selectedPayload, setSelectedPayload] = useState<Record<string, unknown> | null>(null);

	const loadAuditLogs = useCallback(async () => {
		setIsLoading(true);
		try {
			const filters: AuditLogFilterParams = {
				limit,
				offset,
				action: actionFilter || undefined,
				actor_email: searchActor || undefined,
				subject_email: searchSubject || undefined,
				ticket_ref: ticketRefFilter || undefined,
				start_date: startDate ? new Date(startDate).toISOString() : undefined,
				end_date: endDate ? new Date(endDate).toISOString() : undefined,
			};
			const res = await adminAuditLogsApiService.list(filters);
			setItems(res.items);
			setTotal(res.total);
		} catch (err) {
			console.error("Failed to load audit logs:", err);
		} finally {
			setIsLoading(false);
		}
	}, [
		limit,
		offset,
		actionFilter,
		searchActor,
		searchSubject,
		ticketRefFilter,
		startDate,
		endDate,
	]);

	useEffect(() => {
		loadAuditLogs();
	}, [loadAuditLogs]);

	return (
		<div className="space-y-6 p-6">
			{/* Header */}
			<div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
				<div>
					<div className="flex items-center gap-2">
						<ShieldAlert className="h-6 w-6 text-primary" />
						<h1 className="text-2xl font-bold tracking-tight">Security Audit Trail Logs</h1>
					</div>
					<p className="text-sm text-muted-foreground">
						Immutable dual-principal audit trail for administrative actions, impersonation, rules,
						and configuration changes.
					</p>
				</div>
				<div className="flex items-center gap-2">
					<button
						type="button"
						onClick={loadAuditLogs}
						disabled={isLoading}
						className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-3 py-2 text-sm font-medium text-foreground hover:bg-muted disabled:opacity-50"
					>
						<RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
						Refresh
					</button>
					<button
						type="button"
						onClick={() => exportCsv(items)}
						disabled={items.length === 0}
						className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
					>
						<Download className="h-4 w-4" />
						Export CSV
					</button>
				</div>
			</div>

			{/* Filters Bar */}
			<div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-6">
				<div>
					<label htmlFor="action-filter" className="text-xs font-medium text-muted-foreground">
						Action Type
					</label>
					<select
						id="action-filter"
						value={actionFilter}
						onChange={(e) => {
							setActionFilter(e.target.value);
							setOffset(0);
						}}
						className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
					>
						<option value="">All Actions</option>
						<option value="user.impersonate_start">user.impersonate_start</option>
						<option value="user.impersonate_exit">user.impersonate_exit</option>
						<option value="global_dnc.add">global_dnc.add</option>
						<option value="global_dnc.remove">global_dnc.remove</option>
						<option value="broadcast.create">broadcast.create</option>
						<option value="broadcast.update">broadcast.update</option>
						<option value="broadcast.delete">broadcast.delete</option>
						<option value="scraper_rule.create">scraper_rule.create</option>
						<option value="scraper_rule.update">scraper_rule.update</option>
						<option value="scraper_rule.activate">scraper_rule.activate</option>
						<option value="scraper_rule.delete">scraper_rule.delete</option>
					</select>
				</div>

				<div>
					<label htmlFor="search-actor" className="text-xs font-medium text-muted-foreground">
						Actor Email
					</label>
					<div className="relative mt-1">
						<Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
						<input
							id="search-actor"
							type="text"
							placeholder="Search actor..."
							value={searchActor}
							onChange={(e) => {
								setSearchActor(e.target.value);
								setOffset(0);
							}}
							className="w-full rounded-lg border border-border bg-background pl-8 pr-3 py-2 text-sm"
						/>
					</div>
				</div>

				<div>
					<label htmlFor="search-subject" className="text-xs font-medium text-muted-foreground">
						Subject Email / ID
					</label>
					<div className="relative mt-1">
						<Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
						<input
							id="search-subject"
							type="text"
							placeholder="Search subject..."
							value={searchSubject}
							onChange={(e) => {
								setSearchSubject(e.target.value);
								setOffset(0);
							}}
							className="w-full rounded-lg border border-border bg-background pl-8 pr-3 py-2 text-sm"
						/>
					</div>
				</div>

				<div>
					<label htmlFor="ticket-ref-filter" className="text-xs font-medium text-muted-foreground">
						Ticket Reference
					</label>
					<input
						id="ticket-ref-filter"
						type="text"
						placeholder="e.g. SEC-1234"
						value={ticketRefFilter}
						onChange={(e) => {
							setTicketRefFilter(e.target.value);
							setOffset(0);
						}}
						className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
					/>
				</div>

				<div>
					<label htmlFor="start-date-filter" className="text-xs font-medium text-muted-foreground">
						Start Date
					</label>
					<input
						id="start-date-filter"
						type="date"
						value={startDate}
						onChange={(e) => {
							setStartDate(e.target.value);
							setOffset(0);
						}}
						className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
					/>
				</div>

				<div>
					<label htmlFor="end-date-filter" className="text-xs font-medium text-muted-foreground">
						End Date
					</label>
					<input
						id="end-date-filter"
						type="date"
						value={endDate}
						onChange={(e) => {
							setEndDate(e.target.value);
							setOffset(0);
						}}
						className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
					/>
				</div>
			</div>

			{/* Table */}
			<div className="rounded-xl border border-border bg-card overflow-hidden">
				<div className="overflow-x-auto">
					<table className="w-full text-left text-sm">
						<thead className="border-b border-border bg-muted/40 text-xs font-medium text-muted-foreground uppercase">
							<tr>
								<th className="px-4 py-3">Timestamp</th>
								<th className="px-4 py-3">Action</th>
								<th className="px-4 py-3">Actor (Admin)</th>
								<th className="px-4 py-3">Subject (Target)</th>
								<th className="px-4 py-3">IP & Client</th>
								<th className="px-4 py-3">Ticket</th>
								<th className="px-4 py-3 text-right">Details</th>
							</tr>
						</thead>
						<tbody className="divide-y divide-border">
							{isLoading ? (
								<tr>
									<td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
										Loading audit events...
									</td>
								</tr>
							) : items.length === 0 ? (
								<tr>
									<td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
										No audit records match the current filters.
									</td>
								</tr>
							) : (
								items.map((event) => (
									<tr key={event.id} className="hover:bg-muted/30 transition">
										<td className="px-4 py-3 whitespace-nowrap text-xs text-muted-foreground font-mono">
											{new Date(event.created_at).toLocaleString()}
										</td>
										<td className="px-4 py-3">
											<span
												className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold ${getActionBadgeStyle(
													event.action
												)}`}
											>
												{event.action}
											</span>
										</td>
										<td className="px-4 py-3">
											<div className="font-medium text-foreground">
												{event.actor_email || "System"}
											</div>
											{event.actor_id && (
												<div className="text-[10px] text-muted-foreground font-mono truncate max-w-[140px]">
													{event.actor_id}
												</div>
											)}
										</td>
										<td className="px-4 py-3">
											{event.subject_email ? (
												<div className="font-medium text-foreground">{event.subject_email}</div>
											) : event.subject_id ? (
												<div className="text-xs font-mono text-muted-foreground truncate max-w-[140px]">
													{event.subject_id}
												</div>
											) : (
												<span className="text-xs text-muted-foreground">—</span>
											)}
										</td>
										<td className="px-4 py-3">
											<div className="text-xs font-mono text-foreground">
												{event.ip_address || "—"}
											</div>
											<div
												className="text-[10px] text-muted-foreground truncate max-w-[180px]"
												title={event.user_agent || ""}
											>
												{event.user_agent || ""}
											</div>
										</td>
										<td className="px-4 py-3 text-xs font-mono">
											{event.ticket_ref ? (
												<span className="rounded bg-muted px-1.5 py-0.5 text-foreground">
													{event.ticket_ref}
												</span>
											) : (
												<span className="text-muted-foreground">—</span>
											)}
										</td>
										<td className="px-4 py-3 text-right">
											{event.diff_payload ? (
												<button
													type="button"
													onClick={() => setSelectedPayload(event.diff_payload || null)}
													className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs hover:bg-muted"
												>
													<Eye className="h-3 w-3" />
													View
												</button>
											) : (
												<span className="text-xs text-muted-foreground">—</span>
											)}
										</td>
									</tr>
								))
							)}
						</tbody>
					</table>
				</div>

				{/* Pagination Bar */}
				<div className="flex items-center justify-between border-t border-border px-4 py-3 text-sm">
					<div className="text-xs text-muted-foreground">
						Showing {items.length} of {total} events
					</div>
					<div className="flex gap-2">
						<button
							type="button"
							onClick={() => setOffset((prev) => Math.max(0, prev - limit))}
							disabled={offset === 0 || isLoading}
							className="rounded-md border border-border px-3 py-1 text-xs font-medium hover:bg-muted disabled:opacity-40"
						>
							Previous
						</button>
						<button
							type="button"
							onClick={() => setOffset((prev) => prev + limit)}
							disabled={offset + limit >= total || isLoading}
							className="rounded-md border border-border px-3 py-1 text-xs font-medium hover:bg-muted disabled:opacity-40"
						>
							Next
						</button>
					</div>
				</div>
			</div>

			{/* JSON Viewer Modal */}
			{selectedPayload && (
				<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
					<div className="w-full max-w-2xl rounded-xl border border-border bg-card p-6 shadow-2xl space-y-4">
						<div className="flex items-center justify-between">
							<h3 className="text-lg font-bold">Audit Event Diff Payload</h3>
							<button
								type="button"
								onClick={() => setSelectedPayload(null)}
								className="rounded-lg p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
							>
								✕
							</button>
						</div>
						<pre className="max-h-[400px] overflow-auto rounded-lg bg-muted p-4 text-xs font-mono text-foreground whitespace-pre-wrap">
							{JSON.stringify(selectedPayload, null, 2)}
						</pre>
						<div className="flex justify-end">
							<button
								type="button"
								onClick={() => setSelectedPayload(null)}
								className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
							>
								Close
							</button>
						</div>
					</div>
				</div>
			)}
		</div>
	);
}

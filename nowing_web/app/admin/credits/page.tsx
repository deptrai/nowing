"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import ManualCreditModal from "@/components/admin/ManualCreditModal";
import {
	adminCreditsApiService,
	type ManualCreditLedgerEntry,
} from "@/lib/apis/admin-credits-api.service";

interface Filters {
	workspace_id: string;
	admin_id: string;
	date_from: string;
	date_to: string;
	reason: string;
}

function csvField(value: string | number): string {
	const s = String(value);
	if (s.includes(",") || s.includes('"') || s.includes("\n")) {
		return `"${s.replace(/"/g, '""')}"`;
	}
	return s;
}

function toCSV(rows: ManualCreditLedgerEntry[]): string {
	const headers = [
		"transaction_id",
		"workspace_id",
		"actor_admin_id",
		"direction",
		"amount_credits",
		"amount_micros",
		"reason",
		"ticket_ref",
		"created_at",
	];
	const lines = rows.map((r) =>
		[
			r.transaction_id,
			r.workspace_id,
			r.actor_admin_id,
			r.direction,
			r.amount_credits,
			r.amount_micros,
			r.reason,
			r.ticket_ref,
			r.created_at,
		]
			.map(csvField)
			.join(",")
	);
	return [headers.map(csvField).join(","), ...lines].join("\n");
}

export default function AdminCreditsPage() {
	const [ledger, setLedger] = useState<ManualCreditLedgerEntry[]>([]);
	const [isLoading, setIsLoading] = useState(false);
	const [isModalOpen, setIsModalOpen] = useState(false);
	const [filters, setFilters] = useState<Filters>({
		workspace_id: "",
		admin_id: "",
		date_from: "",
		date_to: "",
		reason: "",
	});

	const loadLedger = useCallback(async () => {
		setIsLoading(true);
		try {
			const data = await adminCreditsApiService.ledger({
				workspace_id: filters.workspace_id ? parseInt(filters.workspace_id, 10) : undefined,
				admin_id: filters.admin_id || undefined,
				date_from: filters.date_from || undefined,
				date_to: filters.date_to || undefined,
				reason: filters.reason || undefined,
			});
			setLedger(data);
		} finally {
			setIsLoading(false);
		}
	}, [filters]);

	useEffect(() => {
		loadLedger();
	}, [loadLedger]);

	const stats = useMemo(() => {
		const today = new Date().toISOString().slice(0, 10);
		const creditsMinted = ledger
			.filter((r) => r.direction === "CREDIT")
			.reduce((sum, r) => sum + r.amount_credits, 0);
		const debits = ledger
			.filter((r) => r.direction === "DEBIT")
			.reduce((sum, r) => sum + r.amount_credits, 0);
		const highValueCount = ledger.filter(
			(r) => r.direction === "CREDIT" && r.amount_credits >= 1000
		).length;
		const todayCount = ledger.filter((r) =>
			(r.created_at || "").slice(0, 10).startsWith(today)
		).length;
		return {
			creditsMinted,
			debits,
			totalCount: ledger.length,
			highValueCount,
			todayCount,
		};
	}, [ledger]);

	const handleExportCSV = () => {
		const blob = new Blob([toCSV(ledger)], {
			type: "text/csv;charset=utf-8;",
		});
		const url = URL.createObjectURL(blob);
		const a = document.createElement("a");
		a.href = url;
		a.download = `manual-credit-ledger-${new Date().toISOString().slice(0, 10)}.csv`;
		a.click();
		URL.revokeObjectURL(url);
	};

	return (
		<div className="p-6">
			<div className="mb-6 flex items-center justify-between">
				<h1 className="text-2xl font-bold">Admin: Manual Credits</h1>
				<button
					type="button"
					onClick={() => setIsModalOpen(true)}
					className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700"
				>
					+ New Adjustment
				</button>
			</div>

			<div className="mb-6 grid grid-cols-4 gap-4">
				<div className="rounded border p-3">
					<div className="text-xs text-slate-500">Total Credits Minted</div>
					<div className="font-mono text-lg font-semibold">
						{stats.creditsMinted.toLocaleString()}
					</div>
				</div>
				<div className="rounded border p-3">
					<div className="text-xs text-slate-500">Total Manual Debits</div>
					<div className="font-mono text-lg font-semibold">{stats.debits.toLocaleString()}</div>
				</div>
				<div className="rounded border p-3">
					<div className="text-xs text-slate-500">Today&apos;s Adjustments Count</div>
					<div className="font-mono text-lg font-semibold">{stats.todayCount.toLocaleString()}</div>
				</div>
				<div className="rounded border p-3">
					<div className="text-xs text-slate-500">High-Value Flags</div>
					<div className="font-mono text-lg font-semibold text-amber-600">
						{stats.highValueCount.toLocaleString()}
					</div>
				</div>
			</div>

			<div className="mb-4 flex flex-wrap items-end gap-3">
				<input
					type="number"
					placeholder="Workspace ID"
					className="h-9 rounded border px-2 text-sm"
					value={filters.workspace_id}
					onChange={(e) => setFilters((prev) => ({ ...prev, workspace_id: e.target.value }))}
				/>
				<input
					type="text"
					placeholder="Admin UUID"
					className="h-9 rounded border px-2 text-sm font-mono"
					value={filters.admin_id}
					onChange={(e) => setFilters((prev) => ({ ...prev, admin_id: e.target.value }))}
				/>
				<input
					type="date"
					className="h-9 rounded border px-2 text-sm"
					value={filters.date_from}
					onChange={(e) => setFilters((prev) => ({ ...prev, date_from: e.target.value }))}
				/>
				<input
					type="date"
					className="h-9 rounded border px-2 text-sm"
					value={filters.date_to}
					onChange={(e) => setFilters((prev) => ({ ...prev, date_to: e.target.value }))}
				/>
				<input
					type="text"
					placeholder="Reason contains"
					className="h-9 rounded border px-2 text-sm"
					value={filters.reason}
					onChange={(e) => setFilters((prev) => ({ ...prev, reason: e.target.value }))}
				/>
				<button
					type="button"
					onClick={loadLedger}
					className="h-9 rounded border bg-slate-100 px-3 text-sm hover:bg-slate-200"
				>
					Filter
				</button>
				<button
					type="button"
					onClick={handleExportCSV}
					className="h-9 rounded border px-3 text-sm hover:bg-slate-50"
				>
					Export CSV
				</button>
			</div>

			<div className="overflow-auto rounded border">
				<table className="w-full text-sm">
					<thead>
						<tr className="border-b bg-slate-50 text-left dark:bg-slate-800">
							<th className="h-9 px-2 font-medium">ID</th>
							<th className="h-9 px-2 font-medium">Workspace</th>
							<th className="h-9 px-2 font-medium">Admin</th>
							<th className="h-9 px-2 font-medium">Direction</th>
							<th className="h-9 px-2 font-medium text-right">Credits</th>
							<th className="h-9 px-2 font-medium">Reason</th>
							<th className="h-9 px-2 font-medium">Ticket Ref</th>
							<th className="h-9 px-2 font-medium">Created At</th>
						</tr>
					</thead>
					<tbody>
						{isLoading ? (
							<tr>
								<td colSpan={8} className="h-9 px-2 text-center text-slate-500">
									Loading...
								</td>
							</tr>
						) : ledger.length === 0 ? (
							<tr>
								<td colSpan={8} className="h-9 px-2 text-center text-slate-500">
									No adjustments found.
								</td>
							</tr>
						) : (
							ledger.map((row) => (
								<tr
									key={row.transaction_id}
									className="h-9 border-b hover:bg-slate-50 dark:hover:bg-slate-800"
								>
									<td className="px-2 font-mono">{row.transaction_id}</td>
									<td className="px-2 font-mono">{row.workspace_id}</td>
									<td className="px-2 font-mono text-xs">{row.actor_admin_id}</td>
									<td className="px-2">
										<span
											className={`rounded px-1.5 py-0.5 text-xs font-medium ${
												row.direction === "CREDIT"
													? "bg-green-100 text-green-700"
													: "bg-red-100 text-red-700"
											}`}
										>
											{row.direction}
										</span>
									</td>
									<td
										className={`px-2 text-right font-mono ${
											row.direction === "CREDIT" ? "text-green-600" : "text-red-600"
										}`}
									>
										{row.direction === "CREDIT" ? "+" : "-"}
										{row.amount_credits.toLocaleString()}
									</td>
									<td className="px-2 max-w-xs truncate" title={row.reason}>
										{row.reason}
									</td>
									<td className="px-2 font-mono text-xs">{row.ticket_ref}</td>
									<td className="px-2 font-mono text-xs">{row.created_at}</td>
								</tr>
							))
						)}
					</tbody>
				</table>
			</div>

			<ManualCreditModal
				isOpen={isModalOpen}
				onClose={() => setIsModalOpen(false)}
				onSuccess={loadLedger}
			/>
		</div>
	);
}

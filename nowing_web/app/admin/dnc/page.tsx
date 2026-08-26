"use client";

import { Ban, FileSpreadsheet, Plus, RefreshCw, Search, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import type {
	DncRecordType,
	GlobalDncCsvImportResponse,
	GlobalDncRecordRead,
} from "@/contracts/types/admin-dnc.types";
import { adminDncApiService } from "@/lib/apis/admin-dnc-api.service";

export default function AdminDncPage() {
	const [items, setItems] = useState<GlobalDncRecordRead[]>([]);
	const [total, setTotal] = useState(0);
	const [isLoading, setIsLoading] = useState(false);
	const [recordTypeFilter, setRecordTypeFilter] = useState<string>("");
	const [searchQuery, setSearchQuery] = useState("");
	const [offset, setOffset] = useState(0);
	const [limit] = useState(50);

	// Add single modal
	const [isAddModalOpen, setIsAddModalOpen] = useState(false);
	const [newType, setNewType] = useState<DncRecordType>("phone");
	const [newValue, setNewValue] = useState("");
	const [newReason, setNewReason] = useState("Opt-out requested");
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [addError, setAddError] = useState("");

	// CSV Import modal
	const [isCsvModalOpen, setIsCsvModalOpen] = useState(false);
	const [csvFile, setCsvFile] = useState<File | null>(null);
	const [isImporting, setIsImporting] = useState(false);
	const [importSummary, setImportSummary] = useState<GlobalDncCsvImportResponse | null>(null);

	const loadDncRecords = useCallback(async () => {
		setIsLoading(true);
		try {
			const res = await adminDncApiService.list({
				record_type: recordTypeFilter || undefined,
				search: searchQuery || undefined,
				limit,
				offset,
			});
			setItems(res.items);
			setTotal(res.total);
		} catch (err) {
			console.error("Failed to load global DNC entries:", err);
		} finally {
			setIsLoading(false);
		}
	}, [recordTypeFilter, searchQuery, limit, offset]);

	useEffect(() => {
		loadDncRecords();
	}, [loadDncRecords]);

	const handleAddSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		setAddError("");
		setIsSubmitting(true);
		try {
			await adminDncApiService.create({
				record_type: newType,
				value: newValue,
				reason: newReason,
				source: "admin_manual",
			});
			setIsAddModalOpen(false);
			setNewValue("");
			setNewReason("Opt-out requested");
			await loadDncRecords();
		} catch (err: unknown) {
			const msg = err instanceof Error ? err.message : "Failed to add DNC entry. Check format.";
			setAddError(msg);
		} finally {
			setIsSubmitting(false);
		}
	};

	const handleCsvImport = async (e: React.FormEvent) => {
		e.preventDefault();
		if (!csvFile) return;
		setIsImporting(true);
		try {
			const summary = await adminDncApiService.importCsv(csvFile);
			setImportSummary(summary);
			setCsvFile(null);
			await loadDncRecords();
		} catch (err: unknown) {
			const msg = err instanceof Error ? err.message : "Unknown error";
			alert(`CSV import failed: ${msg}`);
		} finally {
			setIsImporting(false);
		}
	};

	const handleDelete = async (id: string) => {
		if (!confirm("Are you sure you want to remove this entry from the global blacklist?")) {
			return;
		}
		try {
			await adminDncApiService.delete(id);
			await loadDncRecords();
		} catch (err: unknown) {
			const msg = err instanceof Error ? err.message : "Unknown error";
			alert(`Failed to delete entry: ${msg}`);
		}
	};

	return (
		<div className="space-y-6 p-6">
			{/* Header */}
			<div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
				<div>
					<div className="flex items-center gap-2">
						<Ban className="h-6 w-6 text-rose-500" />
						<h1 className="text-2xl font-bold tracking-tight">Global DNC Blacklist Registry</h1>
					</div>
					<p className="text-sm text-muted-foreground">
						Platform-wide exclusion registry (Decree 91 & Decree 13 PDPD). Contacts matching these
						entries are blocked fail-closed across all workspaces.
					</p>
				</div>
				<div className="flex items-center gap-2">
					<button
						type="button"
						onClick={loadDncRecords}
						disabled={isLoading}
						className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-3 py-2 text-sm font-medium text-foreground hover:bg-muted"
					>
						<RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
						Refresh
					</button>
					<button
						type="button"
						onClick={() => {
							setImportSummary(null);
							setIsCsvModalOpen(true);
						}}
						className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-3 py-2 text-sm font-medium text-foreground hover:bg-muted"
					>
						<FileSpreadsheet className="h-4 w-4 text-emerald-500" />
						Import CSV
					</button>
					<button
						type="button"
						onClick={() => {
							setAddError("");
							setIsAddModalOpen(true);
						}}
						className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
					>
						<Plus className="h-4 w-4" />
						Add Entry
					</button>
				</div>
			</div>

			{/* Filters Bar */}
			<div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
				<div>
					<label htmlFor="dnc-type-filter" className="text-xs font-medium text-muted-foreground">
						Filter by Type
					</label>
					<select
						id="dnc-type-filter"
						value={recordTypeFilter}
						onChange={(e) => {
							setRecordTypeFilter(e.target.value);
							setOffset(0);
						}}
						className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
					>
						<option value="">All Types (Phone, Domain, Email, Tax ID)</option>
						<option value="phone">Phone (+84...)</option>
						<option value="domain">Domain (e.g. spammer.com)</option>
						<option value="email">Email</option>
						<option value="tax_id">Tax ID (Mã số thuế)</option>
					</select>
				</div>

				<div>
					<label htmlFor="dnc-search" className="text-xs font-medium text-muted-foreground">
						Search Masked / Reason
					</label>
					<div className="relative mt-1">
						<Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
						<input
							id="dnc-search"
							type="text"
							placeholder="Search value or reason..."
							value={searchQuery}
							onChange={(e) => {
								setSearchQuery(e.target.value);
								setOffset(0);
							}}
							className="w-full rounded-lg border border-border bg-background pl-8 pr-3 py-2 text-sm"
						/>
					</div>
				</div>
			</div>

			{/* Table */}
			<div className="rounded-xl border border-border bg-card overflow-hidden">
				<div className="overflow-x-auto">
					<table className="w-full text-left text-sm">
						<thead className="border-b border-border bg-muted/40 text-xs font-medium text-muted-foreground uppercase">
							<tr>
								<th className="px-4 py-3">Type</th>
								<th className="px-4 py-3">Masked Value</th>
								<th className="px-4 py-3">HMAC-SHA256 Blind Hash</th>
								<th className="px-4 py-3">Reason</th>
								<th className="px-4 py-3">Source</th>
								<th className="px-4 py-3">Added</th>
								<th className="px-4 py-3 text-right">Action</th>
							</tr>
						</thead>
						<tbody className="divide-y divide-border">
							{isLoading ? (
								<tr>
									<td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
										Loading DNC records...
									</td>
								</tr>
							) : items.length === 0 ? (
								<tr>
									<td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
										No global DNC entries registered.
									</td>
								</tr>
							) : (
								items.map((r) => (
									<tr key={r.id} className="hover:bg-muted/30 transition">
										<td className="px-4 py-3">
											<span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs font-semibold uppercase">
												{r.record_type}
											</span>
										</td>
										<td className="px-4 py-3 font-medium text-foreground">{r.value || "—"}</td>
										<td className="px-4 py-3">
											<span
												className="text-xs font-mono text-muted-foreground truncate block max-w-[200px]"
												title={r.value_hmac}
											>
												{r.value_hmac}
											</span>
										</td>
										<td className="px-4 py-3 text-xs text-muted-foreground">
											{r.reason || "Opt-out requested"}
										</td>
										<td className="px-4 py-3">
											<span className="inline-flex rounded bg-muted/60 px-1.5 py-0.5 text-[11px] font-mono text-muted-foreground">
												{r.source}
											</span>
										</td>
										<td className="px-4 py-3 text-xs text-muted-foreground whitespace-nowrap">
											{new Date(r.created_at).toLocaleDateString()}
										</td>
										<td className="px-4 py-3 text-right">
											<button
												type="button"
												onClick={() => handleDelete(r.id)}
												className="inline-flex items-center gap-1 rounded-md p-1.5 text-xs text-rose-500 hover:bg-rose-500/10"
												title="Delete from global blacklist"
											>
												<Trash2 className="h-4 w-4" />
											</button>
										</td>
									</tr>
								))
							)}
						</tbody>
					</table>
				</div>

				{/* Pagination */}
				<div className="flex items-center justify-between border-t border-border px-4 py-3 text-sm">
					<div className="text-xs text-muted-foreground">
						Showing {items.length} of {total} entries
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

			{/* Add Entry Modal */}
			{isAddModalOpen && (
				<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
					<div className="w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-2xl space-y-4">
						<div className="flex items-center justify-between">
							<h3 className="text-lg font-bold">Add to Global DNC Blacklist</h3>
							<button
								type="button"
								onClick={() => setIsAddModalOpen(false)}
								className="rounded-lg p-1 text-muted-foreground hover:bg-muted"
							>
								✕
							</button>
						</div>
						{addError && (
							<div className="rounded-lg bg-rose-500/10 p-3 text-xs text-rose-500">{addError}</div>
						)}
						<form onSubmit={handleAddSubmit} className="space-y-4">
							<div>
								<label htmlFor="new-dnc-type" className="text-xs font-medium text-muted-foreground">
									Record Type
								</label>
								<select
									id="new-dnc-type"
									value={newType}
									onChange={(e) => setNewType(e.target.value as DncRecordType)}
									className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
								>
									<option value="phone">Phone Number (+84...)</option>
									<option value="domain">Domain / Host</option>
									<option value="email">Email Address</option>
									<option value="tax_id">Corporate Tax ID</option>
								</select>
							</div>

							<div>
								<label htmlFor="new-dnc-val" className="text-xs font-medium text-muted-foreground">
									Value
								</label>
								<input
									id="new-dnc-val"
									type="text"
									required
									placeholder={
										newType === "phone"
											? "e.g. 0901234567"
											: newType === "domain"
												? "e.g. spam-broker.com"
												: newType === "email"
													? "e.g. optout@company.com"
													: "e.g. 0314567890"
									}
									value={newValue}
									onChange={(e) => setNewValue(e.target.value)}
									className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
								/>
							</div>

							<div>
								<label
									htmlFor="new-dnc-reason"
									className="text-xs font-medium text-muted-foreground"
								>
									Reason / Reference
								</label>
								<input
									id="new-dnc-reason"
									type="text"
									value={newReason}
									onChange={(e) => setNewReason(e.target.value)}
									className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
								/>
							</div>

							<div className="flex justify-end gap-2 pt-2">
								<button
									type="button"
									onClick={() => setIsAddModalOpen(false)}
									className="rounded-lg border border-border px-4 py-2 text-sm font-medium hover:bg-muted"
								>
									Cancel
								</button>
								<button
									type="submit"
									disabled={isSubmitting || !newValue.trim()}
									className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
								>
									{isSubmitting ? "Adding..." : "Add to Blacklist"}
								</button>
							</div>
						</form>
					</div>
				</div>
			)}

			{/* CSV Import Modal */}
			{isCsvModalOpen && (
				<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
					<div className="w-full max-w-lg rounded-xl border border-border bg-card p-6 shadow-2xl space-y-4">
						<div className="flex items-center justify-between">
							<h3 className="text-lg font-bold">Bulk CSV Blacklist Import</h3>
							<button
								type="button"
								onClick={() => setIsCsvModalOpen(false)}
								className="rounded-lg p-1 text-muted-foreground hover:bg-muted"
							>
								✕
							</button>
						</div>

						<p className="text-xs text-muted-foreground">
							Upload a CSV file containing columns:{" "}
							<code className="rounded bg-muted px-1">record_type,value,reason</code>. Valid record
							types: <code className="rounded bg-muted px-1">phone</code>,{" "}
							<code className="rounded bg-muted px-1">domain</code>,{" "}
							<code className="rounded bg-muted px-1">email</code>,{" "}
							<code className="rounded bg-muted px-1">tax_id</code>.
						</p>

						{importSummary ? (
							<div className="space-y-3 rounded-lg bg-muted/50 p-4 text-xs">
								<div className="font-semibold text-sm">Import Results:</div>
								<div className="grid grid-cols-3 gap-2 text-center">
									<div className="rounded bg-emerald-500/10 p-2 text-emerald-500 font-bold">
										{importSummary.imported_count} Imported
									</div>
									<div className="rounded bg-amber-500/10 p-2 text-amber-500 font-bold">
										{importSummary.skipped_count} Skipped
									</div>
									<div className="rounded bg-rose-500/10 p-2 text-rose-500 font-bold">
										{importSummary.failed_count} Failed
									</div>
								</div>
								{importSummary.errors.length > 0 && (
									<div className="max-h-32 overflow-auto rounded bg-rose-500/10 p-2 text-rose-500 font-mono text-[11px]">
										{importSummary.errors.map((err) => (
											<div key={err}>{err}</div>
										))}
									</div>
								)}
								<div className="flex justify-end pt-2">
									<button
										type="button"
										onClick={() => setIsCsvModalOpen(false)}
										className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
									>
										Done
									</button>
								</div>
							</div>
						) : (
							<form onSubmit={handleCsvImport} className="space-y-4">
								<div className="rounded-lg border-2 border-dashed border-border p-6 text-center">
									<input
										type="file"
										accept=".csv"
										required
										onChange={(e) => setCsvFile(e.target.files?.[0] || null)}
										className="w-full text-sm"
									/>
								</div>

								<div className="flex justify-end gap-2 pt-2">
									<button
										type="button"
										onClick={() => setIsCsvModalOpen(false)}
										className="rounded-lg border border-border px-4 py-2 text-sm font-medium hover:bg-muted"
									>
										Cancel
									</button>
									<button
										type="submit"
										disabled={isImporting || !csvFile}
										className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
									>
										{isImporting ? "Importing..." : "Process Import"}
									</button>
								</div>
							</form>
						)}
					</div>
				</div>
			)}
		</div>
	);
}

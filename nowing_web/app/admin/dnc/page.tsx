"use client";

import { Ban, FileSpreadsheet, Plus, RefreshCw, Search, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import type {
	DncRecordType,
	GlobalDncCsvImportResponse,
	GlobalDncRecordRead,
} from "@/contracts/types/admin-dnc.types";
import { adminDncApiService } from "@/lib/apis/admin-dnc-api.service";

export default function AdminDncPage() {
	const t = useTranslations("admin");
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
			console.error(t("dnc_load_failed"), err);
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
			const msg = err instanceof Error ? err.message : t("dnc_add_failed");
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
			const msg = err instanceof Error ? err.message : t("dnc_unknown_error");
			alert(t("dnc_import_failed", { msg }));
		} finally {
			setIsImporting(false);
		}
	};

	const handleDelete = async (id: string) => {
		if (!confirm(t("dnc_confirm_delete"))) {
			return;
		}
		try {
			await adminDncApiService.delete(id);
			await loadDncRecords();
		} catch (err: unknown) {
			const msg = err instanceof Error ? err.message : t("dnc_unknown_error");
			alert(t("dnc_delete_failed", { msg }));
		}
	};

	return (
		<div className="space-y-6 p-6">
			{/* Header */}
			<div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
				<div>
					<div className="flex items-center gap-2">
						<Ban className="h-6 w-6 text-rose-500" />
						<h1 className="text-2xl font-bold tracking-tight">{t("dnc_title")}</h1>
					</div>
					<p className="text-sm text-muted-foreground">{t("dnc_subtitle")}</p>
				</div>
				<div className="flex items-center gap-2">
					<button
						type="button"
						onClick={loadDncRecords}
						disabled={isLoading}
						className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-3 py-2 text-sm font-medium text-foreground hover:bg-muted"
					>
						<RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
						{t("dnc_refresh")}
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
						{t("dnc_import_csv")}
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
						{t("dnc_add_entry")}
					</button>
				</div>
			</div>

			{/* Filters Bar */}
			<div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
				<div>
					<label htmlFor="dnc-type-filter" className="text-xs font-medium text-muted-foreground">
						{t("dnc_filter_type")}
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
						<option value="">{t("dnc_all_types")}</option>
						<option value="phone">{t("dnc_type_phone")}</option>
						<option value="domain">{t("dnc_type_domain")}</option>
						<option value="email">{t("dnc_type_email")}</option>
						<option value="tax_id">{t("dnc_type_tax_id")}</option>
					</select>
				</div>

				<div>
					<label htmlFor="dnc-search" className="text-xs font-medium text-muted-foreground">
						{t("dnc_search_label")}
					</label>
					<div className="relative mt-1">
						<Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
						<input
							id="dnc-search"
							type="text"
							placeholder={t("dnc_search_placeholder")}
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
								<th className="px-4 py-3">{t("dnc_col_type")}</th>
								<th className="px-4 py-3">{t("dnc_col_masked_value")}</th>
								<th className="px-4 py-3">{t("dnc_col_hmac")}</th>
								<th className="px-4 py-3">{t("dnc_col_reason")}</th>
								<th className="px-4 py-3">{t("dnc_col_source")}</th>
								<th className="px-4 py-3">{t("dnc_col_added")}</th>
								<th className="px-4 py-3 text-right">{t("dnc_col_action")}</th>
							</tr>
						</thead>
						<tbody className="divide-y divide-border">
							{isLoading ? (
								<tr>
									<td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
										{t("dnc_loading")}
									</td>
								</tr>
							) : items.length === 0 ? (
								<tr>
									<td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
										{t("dnc_empty")}
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
											{r.reason || t("dnc_optout_requested")}
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
												title={t("dnc_delete_title")}
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
						{t("dnc_showing", { count: items.length, total })}
					</div>
					<div className="flex gap-2">
						<button
							type="button"
							onClick={() => setOffset((prev) => Math.max(0, prev - limit))}
							disabled={offset === 0 || isLoading}
							className="rounded-md border border-border px-3 py-1 text-xs font-medium hover:bg-muted disabled:opacity-40"
						>
							{t("dnc_previous")}
						</button>
						<button
							type="button"
							onClick={() => setOffset((prev) => prev + limit)}
							disabled={offset + limit >= total || isLoading}
							className="rounded-md border border-border px-3 py-1 text-xs font-medium hover:bg-muted disabled:opacity-40"
						>
							{t("dnc_next")}
						</button>
					</div>
				</div>
			</div>

			{/* Add Entry Modal */}
			{isAddModalOpen && (
				<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
					<div className="w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-2xl space-y-4">
						<div className="flex items-center justify-between">
							<h3 className="text-lg font-bold">{t("dnc_modal_add_title")}</h3>
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
									{t("dnc_record_type")}
								</label>
								<select
									id="new-dnc-type"
									value={newType}
									onChange={(e) => setNewType(e.target.value as DncRecordType)}
									className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
								>
									<option value="phone">{t("dnc_type_phone_num")}</option>
									<option value="domain">{t("dnc_type_domain_host")}</option>
									<option value="email">{t("dnc_type_email_addr")}</option>
									<option value="tax_id">{t("dnc_type_tax_corp")}</option>
								</select>
							</div>

							<div>
								<label htmlFor="new-dnc-val" className="text-xs font-medium text-muted-foreground">
									{t("dnc_value")}
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
									{t("dnc_reason_ref")}
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
									{t("dnc_cancel")}
								</button>
								<button
									type="submit"
									disabled={isSubmitting || !newValue.trim()}
									className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
								>
									{isSubmitting ? t("dnc_adding") : t("dnc_add_to_blacklist")}
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
							<h3 className="text-lg font-bold">{t("dnc_csv_title")}</h3>
							<button
								type="button"
								onClick={() => setIsCsvModalOpen(false)}
								className="rounded-lg p-1 text-muted-foreground hover:bg-muted"
							>
								✕
							</button>
						</div>

						<p className="text-xs text-muted-foreground">
							{t("dnc_csv_desc")}{" "}
							<code className="rounded bg-muted px-1">record_type,value,reason</code>.{" "}
							{t("dnc_csv_valid_types")} <code className="rounded bg-muted px-1">phone</code>,{" "}
							<code className="rounded bg-muted px-1">domain</code>,{" "}
							<code className="rounded bg-muted px-1">email</code>,{" "}
							<code className="rounded bg-muted px-1">tax_id</code>.
						</p>

						{importSummary ? (
							<div className="space-y-3 rounded-lg bg-muted/50 p-4 text-xs">
								<div className="font-semibold text-sm">{t("dnc_import_results")}</div>
								<div className="grid grid-cols-3 gap-2 text-center">
									<div className="rounded bg-emerald-500/10 p-2 text-emerald-500 font-bold">
										{importSummary.imported_count} {t("dnc_imported")}
									</div>
									<div className="rounded bg-amber-500/10 p-2 text-amber-500 font-bold">
										{importSummary.skipped_count} {t("dnc_skipped")}
									</div>
									<div className="rounded bg-rose-500/10 p-2 text-rose-500 font-bold">
										{importSummary.failed_count} {t("dnc_failed")}
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
										{t("dnc_done")}
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
										{isImporting ? t("dnc_importing") : t("dnc_process_import")}
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

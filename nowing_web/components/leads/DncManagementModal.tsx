"use client";

import {
	AlertCircle,
	CheckCircle2,
	FileSpreadsheet,
	Filter,
	Loader2,
	Plus,
	RefreshCw,
	Search,
	ShieldAlert,
	Trash2,
	UploadCloud,
	X,
} from "lucide-react";
import type React from "react";
import { useCallback, useEffect, useState } from "react";
import type { DncCsvImportResponse, DncRecord, DncRecordType } from "@/contracts/types/dnc.types";
import { dncApiService } from "@/lib/apis/dnc-api.service";

interface DncManagementModalProps {
	isOpen: boolean;
	onClose: () => void;
	workspaceId: string | number;
}

export const DncManagementModal: React.FC<DncManagementModalProps> = ({
	isOpen,
	onClose,
	workspaceId,
}) => {
	const [activeTab, setActiveTab] = useState<"list" | "add" | "import">("list");
	const [records, setRecords] = useState<DncRecord[]>([]);
	const [totalCount, setTotalCount] = useState<number>(0);
	const [page, setPage] = useState<number>(1);
	const [selectedType, setSelectedType] = useState<string>("all");
	const [searchQuery, setSearchQuery] = useState<string>("");
	const [debouncedQuery, setDebouncedQuery] = useState<string>("");
	const [loading, setLoading] = useState<boolean>(false);
	const [actionLoading, setActionLoading] = useState<boolean>(false);
	const [error, setError] = useState<string | null>(null);
	const [successMsg, setSuccessMsg] = useState<string | null>(null);

	// Debounce search query input (300ms)
	useEffect(() => {
		const timer = setTimeout(() => {
			setDebouncedQuery(searchQuery);
		}, 300);
		return () => clearTimeout(timer);
	}, [searchQuery]);

	// New Entry Form State
	const [newType, setNewType] = useState<DncRecordType>("phone");
	const [newValue, setNewValue] = useState<string>("");
	const [newReason, setNewReason] = useState<string>("Opt-out requested");

	// CSV Upload State
	const [selectedFile, setSelectedFile] = useState<File | null>(null);
	const [importResult, setImportResult] = useState<DncCsvImportResponse | null>(null);

	const fetchRecords = useCallback(async () => {
		if (!isOpen) return;
		setLoading(true);
		setError(null);
		try {
			const res = await dncApiService.listDncRecords(workspaceId, {
				record_type: selectedType === "all" ? undefined : selectedType,
				search: debouncedQuery ? debouncedQuery.trim() : undefined,
				page,
				page_size: 20,
			});
			setRecords(res.records);
			setTotalCount(res.total_count);
		} catch (err: unknown) {
			setError(err instanceof Error ? err.message : "An error occurred");
		} finally {
			setLoading(false);
		}
	}, [isOpen, page, selectedType, debouncedQuery, workspaceId]);

	useEffect(() => {
		if (isOpen) {
			fetchRecords();
		}
	}, [isOpen, fetchRecords]);

	const handleAddSingle = async (e: React.FormEvent) => {
		e.preventDefault();
		if (!newValue.trim()) return;

		setActionLoading(true);
		setError(null);
		setSuccessMsg(null);
		try {
			await dncApiService.createDncRecord(workspaceId, {
				record_type: newType,
				value: newValue.trim(),
				reason: newReason.trim(),
			});
			setSuccessMsg(`Added ${newType} '${newValue}' to DNC blacklist`);
			setNewValue("");
			setActiveTab("list");
			await fetchRecords();
		} catch (err: unknown) {
			setError(err instanceof Error ? err.message : "Failed to add DNC entry");
		} finally {
			setActionLoading(false);
		}
	};

	const handleDelete = async (recordId: string) => {
		if (!confirm("Are you sure you want to remove this record from the DNC blacklist?")) {
			return;
		}
		setActionLoading(true);
		setError(null);
		try {
			await dncApiService.deleteDncRecord(workspaceId, recordId);
			setRecords((prev) => prev.filter((r) => r.id !== recordId));
			setTotalCount((prev) => Math.max(0, prev - 1));
			setSuccessMsg("Removed record from DNC blacklist");
		} catch (err: unknown) {
			setError(err instanceof Error ? err.message : "Failed to delete record");
		} finally {
			setActionLoading(false);
		}
	};

	const handleFileUpload = async (e: React.FormEvent) => {
		e.preventDefault();
		if (!selectedFile) return;

		setActionLoading(true);
		setError(null);
		setImportResult(null);
		try {
			const res = await dncApiService.importDncCsv(workspaceId, selectedFile);
			setImportResult(res);
			setSuccessMsg(`Successfully imported ${res.imported_count} DNC records`);
			setSelectedFile(null);
			await fetchRecords();
		} catch (err: unknown) {
			setError(err instanceof Error ? err.message : "CSV import failed");
		} finally {
			setActionLoading(false);
		}
	};

	if (!isOpen) return null;

	return (
		<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 overflow-y-auto">
			<div className="relative w-full max-w-3xl rounded-2xl bg-zinc-900 border border-zinc-800 shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
				{/* Header */}
				<div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800 bg-zinc-900/80 sticky top-0 z-10">
					<div className="flex items-center gap-3">
						<div className="p-2 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400">
							<ShieldAlert className="w-5 h-5" />
						</div>
						<div>
							<h2 className="text-lg font-semibold text-zinc-100 flex items-center gap-2">
								Do-Not-Call (DNC) & Compliance Registry
								<span className="text-xs font-normal px-2 py-0.5 rounded-full bg-red-950/80 text-red-300 border border-red-800/40">
									NĐ 91/2020 & NĐ 13/2023
								</span>
							</h2>
							<p className="text-xs text-zinc-400">
								Contacts in this registry are strictly excluded from automated outreach and phone
								resolution.
							</p>
						</div>
					</div>
					<button
						type="button"
						onClick={onClose}
						className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 transition-colors"
					>
						<X className="w-5 h-5" />
					</button>
				</div>

				{/* Tabs Navigation */}
				<div className="flex items-center gap-2 px-6 pt-3 border-b border-zinc-800 bg-zinc-950/40">
					<button
						type="button"
						onClick={() => {
							setActiveTab("list");
							setError(null);
							setSuccessMsg(null);
						}}
						className={`px-4 py-2 text-sm font-medium border-b-2 transition-all flex items-center gap-2 ${
							activeTab === "list"
								? "border-emerald-500 text-emerald-400"
								: "border-transparent text-zinc-400 hover:text-zinc-200"
						}`}
					>
						<Filter className="w-4 h-4" />
						Blacklist Registry ({totalCount})
					</button>
					<button
						type="button"
						onClick={() => {
							setActiveTab("add");
							setError(null);
							setSuccessMsg(null);
						}}
						className={`px-4 py-2 text-sm font-medium border-b-2 transition-all flex items-center gap-2 ${
							activeTab === "add"
								? "border-emerald-500 text-emerald-400"
								: "border-transparent text-zinc-400 hover:text-zinc-200"
						}`}
					>
						<Plus className="w-4 h-4" />
						Add Single Record
					</button>
					<button
						type="button"
						onClick={() => {
							setActiveTab("import");
							setError(null);
							setSuccessMsg(null);
						}}
						className={`px-4 py-2 text-sm font-medium border-b-2 transition-all flex items-center gap-2 ${
							activeTab === "import"
								? "border-emerald-500 text-emerald-400"
								: "border-transparent text-zinc-400 hover:text-zinc-200"
						}`}
					>
						<UploadCloud className="w-4 h-4" />
						Bulk CSV Import
					</button>
				</div>

				{/* Body Content */}
				<div className="p-6 overflow-y-auto flex-1 space-y-4">
					{error && (
						<div className="flex items-center gap-3 p-3 rounded-lg bg-red-950/50 border border-red-800 text-red-300 text-sm">
							<AlertCircle className="w-4 h-4 shrink-0" />
							<span>{error}</span>
						</div>
					)}
					{successMsg && (
						<div className="flex items-center gap-3 p-3 rounded-lg bg-emerald-950/50 border border-emerald-800 text-emerald-300 text-sm">
							<CheckCircle2 className="w-4 h-4 shrink-0" />
							<span>{successMsg}</span>
						</div>
					)}

					{/* TAB 1: LIST */}
					{activeTab === "list" && (
						<div className="space-y-4">
							{/* Filters Bar */}
							<div className="flex flex-col sm:flex-row gap-3 items-center justify-between">
								<div className="relative w-full sm:w-72">
									<Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
									<input
										type="text"
										value={searchQuery}
										onChange={(e) => {
											setSearchQuery(e.target.value);
											setPage(1);
										}}
										placeholder="Search number, domain, reason..."
										className="w-full pl-9 pr-3 py-1.5 bg-zinc-800/80 border border-zinc-700 rounded-lg text-sm text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-emerald-500"
									/>
								</div>

								<div className="flex items-center gap-2 w-full sm:w-auto">
									<select
										value={selectedType}
										onChange={(e) => {
											setSelectedType(e.target.value);
											setPage(1);
										}}
										className="px-3 py-1.5 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-200 focus:outline-none focus:border-emerald-500"
									>
										<option value="all">All Types</option>
										<option value="phone">Phone (+84)</option>
										<option value="domain">Domain / Subdomain</option>
										<option value="email">Email</option>
										<option value="tax_id">Tax ID (MST)</option>
									</select>
									<button
										type="button"
										onClick={fetchRecords}
										disabled={loading}
										className="p-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors"
										title="Refresh"
									>
										<RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
									</button>
								</div>
							</div>

							{/* Table */}
							<div className="border border-zinc-800 rounded-xl overflow-hidden bg-zinc-950/50">
								<table className="w-full text-left text-sm text-zinc-300">
									<thead className="bg-zinc-900/60 text-xs font-semibold text-zinc-400 uppercase tracking-wider border-b border-zinc-800">
										<tr>
											<th className="px-4 py-3">Type</th>
											<th className="px-4 py-3">Value / Match</th>
											<th className="px-4 py-3">Reason</th>
											<th className="px-4 py-3">Source</th>
											<th className="px-4 py-3 text-right">Action</th>
										</tr>
									</thead>
									<tbody className="divide-y divide-zinc-800/60">
										{loading ? (
											<tr>
												<td colSpan={5} className="px-4 py-8 text-center text-zinc-400">
													<Loader2 className="w-6 h-6 animate-spin mx-auto text-emerald-400 mb-2" />
													Loading compliance records...
												</td>
											</tr>
										) : records.length === 0 ? (
											<tr>
												<td colSpan={5} className="px-4 py-8 text-center text-zinc-500">
													No DNC records found matching your filters.
												</td>
											</tr>
										) : (
											records.map((r) => (
												<tr key={r.id} className="hover:bg-zinc-800/30 transition-colors">
													<td className="px-4 py-3">
														<span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-medium bg-zinc-800 border border-zinc-700 text-zinc-300 uppercase">
															{r.record_type}
														</span>
													</td>
													<td className="px-4 py-3 font-mono text-zinc-200">
														{r.value || `[HMAC: ${r.value_hmac.slice(0, 10)}...]`}
													</td>
													<td className="px-4 py-3 text-zinc-400 text-xs">
														{r.reason || "Opt-out"}
													</td>
													<td className="px-4 py-3 text-xs text-zinc-500">
														{r.source === "right_to_be_forgotten" ? (
															<span className="text-amber-400/90 font-medium">
																Right-to-be-Forgotten
															</span>
														) : (
															r.source
														)}
													</td>
													<td className="px-4 py-3 text-right">
														<button
															type="button"
															onClick={() => handleDelete(r.id)}
															disabled={actionLoading}
															className="p-1.5 rounded-md text-zinc-500 hover:text-red-400 hover:bg-red-950/40 transition-colors"
															title="Remove from DNC"
														>
															<Trash2 className="w-4 h-4" />
														</button>
													</td>
												</tr>
											))
										)}
									</tbody>
								</table>
							</div>

							{/* Pagination */}
							{totalCount > 20 && (
								<div className="flex items-center justify-between text-xs text-zinc-400 px-1">
									<span>
										Showing {records.length} of {totalCount} records
									</span>
									<div className="flex items-center gap-2">
										<button
											type="button"
											onClick={() => setPage((p) => Math.max(1, p - 1))}
											disabled={page <= 1 || loading}
											className="px-2.5 py-1 rounded bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50"
										>
											Prev
										</button>
										<span>Page {page}</span>
										<button
											type="button"
											onClick={() => setPage((p) => p + 1)}
											disabled={records.length < 20 || loading}
											className="px-2.5 py-1 rounded bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50"
										>
											Next
										</button>
									</div>
								</div>
							)}
						</div>
					)}

					{/* TAB 2: ADD SINGLE ENTRY */}
					{activeTab === "add" && (
						<form onSubmit={handleAddSingle} className="space-y-4 max-w-xl mx-auto py-4">
							<div className="space-y-1.5">
								<label
									htmlFor="dnc-record-type"
									className="text-xs font-semibold text-zinc-300 uppercase tracking-wider"
								>
									Record Identifier Type
								</label>
								<select
									id="dnc-record-type"
									value={newType}
									onChange={(e) => setNewType(e.target.value as DncRecordType)}
									className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-200 focus:outline-none focus:border-emerald-500"
								>
									<option value="phone">Phone Number (e.g. 0908123456 or +84908123456)</option>
									<option value="domain">Company Domain (e.g. vinhomes.vn or *.vinhomes.vn)</option>
									<option value="email">Email Address (e.g. contact@domain.com)</option>
									<option value="tax_id">Corporate Tax ID / MST (e.g. 0101234567)</option>
								</select>
							</div>

							<div className="space-y-1.5">
								<label
									htmlFor="dnc-target-val"
									className="text-xs font-semibold text-zinc-300 uppercase tracking-wider"
								>
									Target Value
								</label>
								<input
									id="dnc-target-val"
									type="text"
									value={newValue}
									onChange={(e) => setNewValue(e.target.value)}
									placeholder={
										newType === "phone"
											? "0908123456"
											: newType === "domain"
												? "*.vinhomes.vn"
												: newType === "email"
													? "ceo@company.com"
													: "0312345678"
									}
									required
									className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-200 focus:outline-none focus:border-emerald-500"
								/>
							</div>

							<div className="space-y-1.5">
								<label
									htmlFor="dnc-legal-context"
									className="text-xs font-semibold text-zinc-300 uppercase tracking-wider"
								>
									Reason / Legal Opt-Out Context
								</label>
								<input
									id="dnc-legal-context"
									type="text"
									value={newReason}
									onChange={(e) => setNewReason(e.target.value)}
									placeholder="e.g. Customer requested opt-out via phone call"
									className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-200 focus:outline-none focus:border-emerald-500"
								/>
							</div>

							<div className="pt-2">
								<button
									type="submit"
									disabled={actionLoading || !newValue.trim()}
									className="w-full py-2.5 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-sm flex items-center justify-center gap-2 transition-all disabled:opacity-50"
								>
									{actionLoading && <Loader2 className="w-4 h-4 animate-spin" />}
									Add to DNC Blacklist
								</button>
							</div>
						</form>
					)}

					{/* TAB 3: BULK CSV IMPORT */}
					{activeTab === "import" && (
						<form onSubmit={handleFileUpload} className="space-y-5 max-w-xl mx-auto py-4">
							<div className="p-4 rounded-xl bg-zinc-950/60 border border-zinc-800 text-xs text-zinc-400 space-y-2">
								<p className="font-semibold text-zinc-200 flex items-center gap-2">
									<FileSpreadsheet className="w-4 h-4 text-emerald-400" />
									CSV File Structure Guide
								</p>
								<p>
									CSV should contain columns: <code className="text-emerald-300">type</code>,{" "}
									<code className="text-emerald-300">value</code>, and optional{" "}
									<code className="text-emerald-300">reason</code>. Supports up to 5,000 records per
									upload.
								</p>
								<pre className="p-2 rounded bg-zinc-900 border border-zinc-800 font-mono text-[11px] text-zinc-300">
									type,value,reason{"\n"}
									phone,0908123456,Decree 91 Blacklist{"\n"}
									domain,*.competitor.com,Competitor Domain{"\n"}
									email,optout@agency.vn,Customer Opt-Out
								</pre>
							</div>

							<div className="border-2 border-dashed border-zinc-700 hover:border-emerald-500 rounded-2xl p-6 text-center transition-colors">
								<input
									type="file"
									accept=".csv"
									id="dnc-csv-input"
									onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
									className="hidden"
								/>
								<label
									htmlFor="dnc-csv-input"
									className="cursor-pointer flex flex-col items-center gap-2"
								>
									<UploadCloud className="w-10 h-10 text-zinc-400 hover:text-emerald-400 transition-colors" />
									<span className="text-sm font-medium text-zinc-200">
										{selectedFile ? selectedFile.name : "Click or drag CSV file here to upload"}
									</span>
									<span className="text-xs text-zinc-500">
										{selectedFile
											? `${(selectedFile.size / 1024).toFixed(1)} KB`
											: "UTF-8 encoded .csv up to 10MB"}
									</span>
								</label>
							</div>

							{importResult && (
								<div className="p-3 rounded-lg bg-zinc-900 border border-zinc-800 text-xs space-y-1 text-zinc-300">
									<p className="font-semibold text-emerald-400">
										Import Complete: {importResult.imported_count} records inserted
									</p>
									<p className="text-zinc-400">
										Skipped: {importResult.skipped_count} | Failed: {importResult.failed_count}
									</p>
									{importResult.errors.length > 0 && (
										<div className="mt-2 text-red-400 font-mono">
											{importResult.errors.slice(0, 5).map((e) => (
												<div key={e}>{e}</div>
											))}
										</div>
									)}
								</div>
							)}

							<button
								type="submit"
								disabled={actionLoading || !selectedFile}
								className="w-full py-2.5 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-sm flex items-center justify-center gap-2 transition-all disabled:opacity-50"
							>
								{actionLoading && <Loader2 className="w-4 h-4 animate-spin" />}
								Upload & Process DNC CSV
							</button>
						</form>
					)}
				</div>
			</div>
		</div>
	);
};

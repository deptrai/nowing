"use client";

import { CheckCircle2, Cloud, FileSpreadsheet, Shield, X } from "lucide-react";
import type React from "react";
import { useState } from "react";

interface FieldMappingModalProps {
	isOpen: boolean;
	onClose: () => void;
	exportType: "lark_base" | "google_sheets";
	totalLeadsCount: number;
	onConfirmSync: (config: Record<string, unknown>, maskPii: boolean) => Promise<void>;
}

export const FieldMappingModal: React.FC<FieldMappingModalProps> = ({
	isOpen,
	onClose,
	exportType,
	totalLeadsCount,
	onConfirmSync,
}) => {
	const [maskPii, setMaskPii] = useState<boolean>(true);
	const [loading, setLoading] = useState<boolean>(false);

	// Lark Base config
	const [appToken, setAppToken] = useState<string>("");
	const [tableId, setTableId] = useState<string>("");
	const [larkToken, setLarkToken] = useState<string>("");

	// Google Sheets config
	const [spreadsheetId, setSpreadsheetId] = useState<string>("");
	const [sheetRange, setSheetRange] = useState<string>("Sheet1!A1");
	const [googleToken, setGoogleToken] = useState<string>("");

	if (!isOpen) return null;

	const isLark = exportType === "lark_base";

	const handleSync = async () => {
		setLoading(true);
		try {
			const config: Record<string, unknown> = isLark
				? { app_token: appToken, table_id: tableId, access_token: larkToken }
				: {
						spreadsheet_id: spreadsheetId,
						sheet_range: sheetRange,
						access_token: googleToken,
					};
			await onConfirmSync(config, maskPii);
			onClose();
		} catch (err) {
			console.error(err);
		} finally {
			setLoading(false);
		}
	};

	return (
		<div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
			<div className="w-full max-w-lg rounded-2xl bg-zinc-900 border border-zinc-800 p-6 shadow-2xl space-y-5">
				{/* Modal Header */}
				<div className="flex items-center justify-between pb-3 border-b border-zinc-800">
					<div className="flex items-center gap-2.5">
						<div
							className={`p-2 rounded-xl border ${
								isLark
									? "bg-blue-500/10 border-blue-500/20 text-blue-400"
									: "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
							}`}
						>
							{isLark ? (
								<Cloud className="w-5 h-5" aria-hidden="true" />
							) : (
								<FileSpreadsheet className="w-5 h-5" aria-hidden="true" />
							)}
						</div>
						<div>
							<h2 className="text-base font-bold text-zinc-100">
								{isLark ? "Đồng bộ Lark Base (Bitable)" : "Đồng bộ Google Sheets"}
							</h2>
							<p className="text-xs text-zinc-400">
								Đẩy {totalLeadsCount} bản ghi đã lọc sang hệ thống lưu trữ ngoài
							</p>
						</div>
					</div>
					<button
						type="button"
						onClick={onClose}
						className="p-1 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
					>
						<X className="w-4 h-4" aria-hidden="true" />
					</button>
				</div>

				{/* Configuration Fields */}
				<div className="space-y-3.5 text-xs">
					{isLark ? (
						<>
							<div>
								<label htmlFor="lark-app-token" className="block text-zinc-300 font-medium mb-1">
									App Token (Bitable Base Token) *
								</label>
								<input
									id="lark-app-token"
									type="text"
									value={appToken}
									onChange={(e) => setAppToken(e.target.value)}
									placeholder="VD: bascnO123456789abcdef"
									className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-blue-500 font-mono text-xs"
								/>
							</div>

							<div>
								<label htmlFor="lark-table-id" className="block text-zinc-300 font-medium mb-1">
									Table ID (Bảng dữ liệu) *
								</label>
								<input
									id="lark-table-id"
									type="text"
									value={tableId}
									onChange={(e) => setTableId(e.target.value)}
									placeholder="VD: tblAbCdEf123456"
									className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-blue-500 font-mono text-xs"
								/>
							</div>

							<div>
								<label htmlFor="lark-tenant-token" className="block text-zinc-300 font-medium mb-1">
									Tenant Access Token (Tùy chọn nếu dùng OAuth workspace)
								</label>
								<input
									id="lark-tenant-token"
									type="password"
									value={larkToken}
									onChange={(e) => setLarkToken(e.target.value)}
									placeholder="t-g104..."
									className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-blue-500 font-mono text-xs"
								/>
							</div>
						</>
					) : (
						<>
							<div>
								<label htmlFor="gsheet-id" className="block text-zinc-300 font-medium mb-1">
									Spreadsheet ID *
								</label>
								<input
									id="gsheet-id"
									type="text"
									value={spreadsheetId}
									onChange={(e) => setSpreadsheetId(e.target.value)}
									placeholder="VD: 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
									className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500 font-mono text-xs"
								/>
							</div>

							<div>
								<label htmlFor="gsheet-range" className="block text-zinc-300 font-medium mb-1">
									Sheet Range
								</label>
								<input
									id="gsheet-range"
									type="text"
									value={sheetRange}
									onChange={(e) => setSheetRange(e.target.value)}
									placeholder="Sheet1!A1"
									className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500 font-mono text-xs"
								/>
							</div>

							<div>
								<label htmlFor="gsheet-token" className="block text-zinc-300 font-medium mb-1">
									Google OAuth Access Token (Tùy chọn)
								</label>
								<input
									id="gsheet-token"
									type="password"
									value={googleToken}
									onChange={(e) => setGoogleToken(e.target.value)}
									placeholder="ya29.a0..."
									className="w-full px-3 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500 font-mono text-xs"
								/>
							</div>
						</>
					)}

					{/* PII Masking toggle */}
					<div className="flex items-start gap-2.5 p-3 rounded-xl bg-zinc-950/80 border border-zinc-800">
						<input
							type="checkbox"
							id="pii-mask-toggle"
							checked={maskPii}
							onChange={(e) => setMaskPii(e.target.checked)}
							className="mt-0.5 rounded border-zinc-700 text-emerald-500 focus:ring-emerald-500"
						/>
						<label htmlFor="pii-mask-toggle" className="cursor-pointer">
							<div className="font-semibold text-zinc-200 flex items-center gap-1.5">
								<Shield className="w-3.5 h-3.5 text-emerald-400" aria-hidden="true" />
								<span>Che thông tin cá nhân (PII Masking)</span>
							</div>
							<p className="text-[11px] text-zinc-400 mt-0.5">
								Tự động che SĐT (0908***456) và Email theo quy chuẩn Nghị định 13/2023/NĐ-CP.
							</p>
						</label>
					</div>

					{/* Schema Mapping preview */}
					<div className="p-3 rounded-xl bg-zinc-950/40 border border-zinc-800/60 space-y-1.5">
						<div className="text-[11px] font-medium text-zinc-400 flex items-center gap-1">
							<CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" aria-hidden="true" />
							<span>Tự động ánh xạ 12 cột chuẩn:</span>
						</div>
						<p className="text-[10px] text-zinc-500 font-mono leading-relaxed">
							Company Name, Domain, Source, Industry, Location, Fit Score, Status, Contact Name,
							Title, Email, Phone, Created At
						</p>
					</div>
				</div>

				{/* Modal Footer */}
				<div className="flex items-center justify-end gap-2.5 pt-3 border-t border-zinc-800">
					<button
						type="button"
						onClick={onClose}
						className="px-3.5 py-2 text-xs font-medium rounded-lg bg-zinc-800 text-zinc-300 hover:bg-zinc-700 transition-colors"
					>
						Hủy bỏ
					</button>
					<button
						type="button"
						onClick={handleSync}
						disabled={loading || (isLark ? !appToken || !tableId : !spreadsheetId)}
						className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-medium rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-emerald-950"
					>
						{loading ? (
							<div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
						) : (
							<Cloud className="w-3.5 h-3.5" aria-hidden="true" />
						)}
						<span>Bắt đầu đồng bộ ({totalLeadsCount} leads)</span>
					</button>
				</div>
			</div>
		</div>
	);
};

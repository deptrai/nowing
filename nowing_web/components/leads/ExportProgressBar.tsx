"use client";

import { CheckCircle2, ExternalLink, Loader2, X, XCircle } from "lucide-react";
import type React from "react";
import type { ExportJobResponse } from "@/contracts/types/workspace-table.types";

interface ExportProgressBarProps {
	job: ExportJobResponse | null;
	onDismiss: () => void;
}

export const ExportProgressBar: React.FC<ExportProgressBarProps> = ({ job, onDismiss }) => {
	if (!job) return null;

	const percent =
		job.total_rows > 0 ? Math.min(100, Math.round((job.processed_rows / job.total_rows) * 100)) : 0;

	return (
		<div className="fixed bottom-6 right-6 z-50 w-80 rounded-2xl bg-zinc-900/95 border border-zinc-800 p-4 shadow-2xl backdrop-blur-md animate-in slide-in-from-bottom-5 duration-300">
			<div className="flex items-start justify-between gap-3">
				<div className="flex items-center gap-2.5">
					{job.status === "processing" ? (
						<Loader2 className="w-5 h-5 text-emerald-400 animate-spin" aria-hidden="true" />
					) : job.status === "completed" ? (
						<CheckCircle2 className="w-5 h-5 text-emerald-400" aria-hidden="true" />
					) : (
						<XCircle className="w-5 h-5 text-rose-400" aria-hidden="true" />
					)}

					<div>
						<h4 className="text-xs font-bold text-zinc-100">
							{job.export_type === "lark_base"
								? "Đồng bộ Lark Base"
								: job.export_type === "google_sheets"
									? "Đồng bộ Google Sheets"
									: "Xuất dữ liệu"}
						</h4>
						<p className="text-[11px] text-zinc-400">
							{job.status === "processing"
								? `Đang đẩy: ${job.processed_rows}/${job.total_rows} rows (${percent}%)`
								: job.status === "completed"
									? `Hoàn tất (${job.processed_rows} leads)`
									: "Đồng bộ thất bại"}
						</p>
					</div>
				</div>

				<button
					type="button"
					onClick={onDismiss}
					className="p-1 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
				>
					<X className="w-3.5 h-3.5" aria-hidden="true" />
				</button>
			</div>

			{/* Progress Bar */}
			{job.status === "processing" && (
				<div className="mt-3 w-full bg-zinc-950 rounded-full h-1.5 overflow-hidden border border-zinc-800">
					<div
						className="bg-emerald-500 h-full transition-all duration-300 rounded-full"
						style={{ width: `${percent}%` }}
					/>
				</div>
			)}

			{/* Target Link on completion */}
			{job.status === "completed" && job.target_url && (
				<div className="mt-2.5 pt-2 border-t border-zinc-800/80 flex items-center justify-between text-[11px]">
					<span className="text-zinc-400">Xem bảng dữ liệu:</span>
					<a
						href={job.target_url}
						target="_blank"
						rel="noreferrer"
						className="inline-flex items-center gap-1 font-medium text-emerald-400 hover:text-emerald-300 hover:underline"
					>
						<span>Mở liên kết</span>
						<ExternalLink className="w-3 h-3" aria-hidden="true" />
					</a>
				</div>
			)}
		</div>
	);
};

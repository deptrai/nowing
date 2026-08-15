"use client";

import { Check, ChevronDown, Cloud, Download, FileSpreadsheet, Share2 } from "lucide-react";
import type React from "react";
import { useEffect, useRef, useState } from "react";

interface SendExportDropdownProps {
	totalLeadsCount: number;
	onDownloadCsv: () => Promise<void>;
	onOpenLarkSync: () => void;
	onOpenGoogleSheetsSync: () => void;
	onShareLink: () => Promise<void>;
}

export const SendExportDropdown: React.FC<SendExportDropdownProps> = ({
	totalLeadsCount,
	onDownloadCsv,
	onOpenLarkSync,
	onOpenGoogleSheetsSync,
	onShareLink,
}) => {
	const [isOpen, setIsOpen] = useState<boolean>(false);
	const [copied, setCopied] = useState<boolean>(false);
	const dropdownRef = useRef<HTMLDivElement>(null);

	// Close on outside click
	useEffect(() => {
		const handleClickOutside = (event: MouseEvent) => {
			if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
				setIsOpen(false);
			}
		};
		document.addEventListener("mousedown", handleClickOutside);
		return () => document.removeEventListener("mousedown", handleClickOutside);
	}, []);

	const handleDownloadCsv = async () => {
		setIsOpen(false);
		await onDownloadCsv();
	};

	const handleShare = async () => {
		setIsOpen(false);
		await onShareLink();
		setCopied(true);
		setTimeout(() => setCopied(false), 2000);
	};

	return (
		<div className="relative" ref={dropdownRef}>
			<button
				type="button"
				onClick={() => setIsOpen(!isOpen)}
				className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white transition-colors shadow-sm shadow-emerald-950/50"
			>
				<Download className="w-3.5 h-3.5" />
				<span>Send & Export</span>
				<ChevronDown
					className={`w-3.5 h-3.5 transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`}
				/>
			</button>

			{isOpen && (
				<div className="absolute right-0 mt-2 w-64 rounded-xl bg-zinc-900 border border-zinc-800 p-1.5 shadow-2xl z-40 text-xs space-y-1 animate-in fade-in zoom-in-95 duration-150">
					<div className="px-2.5 py-1 text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">
						Xuất {totalLeadsCount} Leads đã lọc
					</div>

					{/* CSV Option */}
					<button
						type="button"
						onClick={handleDownloadCsv}
						className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-zinc-200 hover:bg-zinc-800 hover:text-white transition-colors text-left"
					>
						<Download className="w-4 h-4 text-emerald-400" />
						<div>
							<div className="font-medium">Tải file CSV</div>
							<div className="text-[10px] text-zinc-400">Xuất file Excel / CSV tải trực tiếp</div>
						</div>
					</button>

					{/* Lark Base Option */}
					<button
						type="button"
						onClick={() => {
							setIsOpen(false);
							onOpenLarkSync();
						}}
						className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-zinc-200 hover:bg-zinc-800 hover:text-white transition-colors text-left"
					>
						<Cloud className="w-4 h-4 text-blue-400" />
						<div>
							<div className="font-medium">Đẩy sang Lark Base</div>
							<div className="text-[10px] text-zinc-400">1-click push Bitable tự động map cột</div>
						</div>
					</button>

					{/* Google Sheets Option */}
					<button
						type="button"
						onClick={() => {
							setIsOpen(false);
							onOpenGoogleSheetsSync();
						}}
						className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-zinc-200 hover:bg-zinc-800 hover:text-white transition-colors text-left"
					>
						<FileSpreadsheet className="w-4 h-4 text-emerald-400" />
						<div>
							<div className="font-medium">Đẩy sang Google Sheets</div>
							<div className="text-[10px] text-zinc-400">Append dòng mới vào Google Sheet</div>
						</div>
					</button>

					{/* Share Link Option */}
					<div className="pt-1 border-t border-zinc-800/80">
						<button
							type="button"
							onClick={handleShare}
							className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-zinc-200 hover:bg-zinc-800 hover:text-white transition-colors text-left"
						>
							{copied ? (
								<Check className="w-4 h-4 text-emerald-400" />
							) : (
								<Share2 className="w-4 h-4 text-indigo-400" />
							)}
							<div>
								<div className="font-medium">
									{copied ? "Đã sao chép link!" : "Chia sẻ liên kết Read-only"}
								</div>
								<div className="text-[10px] text-zinc-400">Tạo link bảo mật chỉ xem</div>
							</div>
						</button>
					</div>
				</div>
			)}
		</div>
	);
};

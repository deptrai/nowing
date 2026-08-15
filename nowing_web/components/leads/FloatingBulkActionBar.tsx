"use client";

import { CheckSquare, Download, MessageSquare, PhoneCall, X } from "lucide-react";
import type React from "react";
import { cn } from "@/lib/utils";

export interface FloatingBulkActionBarProps {
	selectedCount: number;
	onUnlockPhones?: () => void;
	onExportLarkBase?: () => void;
	onBulkZalo?: () => void;
	onClearSelection: () => void;
	className?: string;
}

export const FloatingBulkActionBar: React.FC<FloatingBulkActionBarProps> = ({
	selectedCount,
	onUnlockPhones,
	onExportLarkBase,
	onBulkZalo,
	onClearSelection,
	className,
}) => {
	if (selectedCount < 2) {
		return null;
	}

	return (
		<aside
			aria-label="Thao tác hàng loạt"
			data-testid="floating-bulk-action-bar"
			className={cn(
				"fixed bottom-6 left-1/2 -translate-x-1/2 z-[60] flex items-center gap-3 px-4 py-2.5",
				"rounded-2xl border border-emerald-500/30 bg-zinc-900/95 text-zinc-100 shadow-2xl backdrop-blur-md",
				"animate-in fade-in slide-in-from-bottom-4 duration-200",
				className
			)}
		>
			<div className="flex items-center gap-2 pr-3 border-r border-zinc-700">
				<span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-400">
					<CheckSquare className="h-3.5 w-3.5" />
				</span>
				<span className="text-xs font-semibold text-zinc-200">
					Đã chọn <span className="font-mono text-emerald-400 font-bold">{selectedCount}</span>{" "}
					leads
				</span>
			</div>

			<div className="flex items-center gap-1.5">
				{onUnlockPhones && (
					<button
						type="button"
						onClick={onUnlockPhones}
						className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white transition-colors cursor-pointer shadow-sm shadow-emerald-950"
					>
						<PhoneCall className="w-3.5 h-3.5" />
						Mở khóa SĐT ({selectedCount})
					</button>
				)}

				{onExportLarkBase && (
					<button
						type="button"
						onClick={onExportLarkBase}
						className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700/60 transition-colors cursor-pointer"
					>
						<Download className="w-3.5 h-3.5 text-emerald-400" />
						Xuất Lark Base
					</button>
				)}

				{onBulkZalo && (
					<button
						type="button"
						onClick={onBulkZalo}
						className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-colors cursor-pointer"
					>
						<MessageSquare className="w-3.5 h-3.5" />
						Gửi Zalo hàng loạt
					</button>
				)}
			</div>

			<button
				type="button"
				onClick={onClearSelection}
				title="Bỏ chọn tất cả"
				className="p-1 rounded-lg hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer ml-1"
			>
				<X className="w-4 h-4" />
			</button>
		</aside>
	);
};

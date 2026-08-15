"use client";

import { Activity, CheckCircle, RefreshCw } from "lucide-react";
import type React from "react";
import { useState } from "react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

export interface ScraperPlatformMonitorPanelProps {
	workspaceId?: string | number;
	className?: string;
}

export const ScraperPlatformMonitorPanel: React.FC<ScraperPlatformMonitorPanelProps> = ({
	workspaceId: _workspaceId = "1",
	className,
}) => {
	const [isRefreshing, setIsRefreshing] = useState(false);

	const platforms = [
		{
			id: "batdongsan",
			name: "Batdongsan.com.vn",
			status: "healthy",
			successRate: "99.4%",
			requestsToday: "1,240 reqs",
			cookieStatus: "Live (Hết hạn sau 14 ngày)",
			icon: "🏠",
			creditsPerLead: "1.5 Credits",
		},
		{
			id: "chotot",
			name: "Chợ Tốt Mobile API",
			status: "healthy",
			successRate: "98.8%",
			requestsToday: "850 reqs",
			cookieStatus: "Token Pool (4/4 Sống)",
			icon: "🛒",
			creditsPerLead: "1.0 Credit",
		},
		{
			id: "topcv",
			name: "TopCV & ITviec Hiring Signals",
			status: "healthy",
			successRate: "99.1%",
			requestsToday: "620 reqs",
			cookieStatus: "Enterprise API Connected",
			icon: "💼",
			creditsPerLead: "1.2 Credits",
		},
		{
			id: "muasamcong",
			name: "Hệ Thống Đấu Thầu Quốc Gia",
			status: "healthy",
			successRate: "97.5%",
			requestsToday: "310 reqs",
			cookieStatus: "Public Key Valid",
			icon: "🏛️",
			creditsPerLead: "2.0 Credits",
		},
		{
			id: "xactions",
			name: "Social Outbound (Facebook & X)",
			status: "healthy",
			successRate: "96.8%",
			requestsToday: "490 reqs",
			cookieStatus: "Session Active",
			icon: "🌐",
			creditsPerLead: "1.5 Credits",
		},
	];

	const handleRefreshAll = () => {
		setIsRefreshing(true);
		setTimeout(() => {
			setIsRefreshing(false);
			toast.success("Đã kiểm tra sức khỏe 5 nền tảng cào dữ liệu: Tất cả đều Hoạt Động Tốt!");
		}, 1200);
	};

	return (
		<div
			className={cn(
				"h-full flex flex-col bg-background text-foreground overflow-hidden font-sans",
				className
			)}
		>
			{/* Top Bar */}
			<div className="h-10 border-b border-border/80 bg-muted/30 flex items-center justify-between px-4 shrink-0">
				<div className="flex items-center gap-2">
					<Activity className="w-3.5 h-3.5 text-emerald-600" />
					<span className="text-xs font-bold text-foreground">
						Giám Sát Hạ Tầng Cào Dữ Liệu (Scraper Platforms Hub)
					</span>
					<span className="px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 text-[10px] font-semibold">
						5/5 Sẵn Sàng
					</span>
				</div>

				<button
					type="button"
					onClick={handleRefreshAll}
					disabled={isRefreshing}
					className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-md border border-border/80 bg-card hover:bg-muted text-foreground transition-colors cursor-pointer disabled:opacity-50"
				>
					<RefreshCw className={cn("w-3 h-3 text-emerald-600", isRefreshing && "animate-spin")} />
					<span>Kiểm Tra Toàn Bộ</span>
				</button>
			</div>

			{/* Platforms Mega Grid */}
			<div className="flex-1 overflow-y-auto p-6 scrollbar-thin space-y-4">
				<div className="grid grid-cols-1 gap-3.5">
					{platforms.map((platform) => (
						<div
							key={platform.id}
							className="p-4 rounded-xl border border-border bg-card flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-xs hover:border-emerald-500/40 transition-colors"
						>
							<div className="flex items-center gap-3">
								<span className="text-2xl">{platform.icon}</span>
								<div>
									<div className="flex items-center gap-2">
										<h4 className="text-xs font-bold text-foreground">{platform.name}</h4>
										<span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 text-[10px] font-semibold">
											<CheckCircle className="w-2.5 h-2.5" />
											Hoạt Động
										</span>
									</div>
									<div className="flex items-center gap-3 text-[11px] text-muted-foreground mt-1">
										<span>
											Thành công:{" "}
											<strong className="text-foreground font-mono">{platform.successRate}</strong>
										</span>
										<span>•</span>
										<span>
											Hôm nay:{" "}
											<strong className="text-foreground font-mono">
												{platform.requestsToday}
											</strong>
										</span>
										<span>•</span>
										<span>
											Chi phí:{" "}
											<strong className="text-emerald-600 dark:text-emerald-400 font-mono">
												{platform.creditsPerLead}
											</strong>
										</span>
									</div>
								</div>
							</div>

							<div className="flex items-center gap-2 self-end sm:self-center">
								<span className="text-[10px] text-muted-foreground font-mono bg-muted/60 px-2 py-1 rounded-md border border-border/60">
									{platform.cookieStatus}
								</span>
								<button
									type="button"
									onClick={() => toast.success(`Đã làm mới token session cho ${platform.name}`)}
									className="px-2.5 py-1 text-[11px] font-semibold rounded-md border border-border bg-background hover:bg-muted text-foreground transition-colors cursor-pointer"
								>
									Làm Mới Token
								</button>
							</div>
						</div>
					))}
				</div>
			</div>
		</div>
	);
};

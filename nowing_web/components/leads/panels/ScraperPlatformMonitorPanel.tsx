"use client";

import { Activity, CheckCircle, ExternalLink, RefreshCw, ShieldCheck } from "lucide-react";
import type React from "react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import {
	type ScraperPlatformAccount,
	scraperPlatformAccountsApiService,
} from "@/lib/apis/scraper-platform-accounts-api.service";
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
	const [accounts, setAccounts] = useState<ScraperPlatformAccount[]>([]);
	const [_isLoading, setIsLoading] = useState(true);

	const fetchLiveAccounts = useCallback(async () => {
		try {
			setIsRefreshing(true);
			const data = await scraperPlatformAccountsApiService.list();
			setAccounts(data);
		} catch (_err) {
			// fallback gracefully
		} finally {
			setIsRefreshing(false);
			setIsLoading(false);
		}
	}, []);

	useEffect(() => {
		fetchLiveAccounts();
	}, [fetchLiveAccounts]);

	const handleRefreshAll = async () => {
		await fetchLiveAccounts();
		toast.success("Đã đồng bộ trạng thái sức khỏe các nền tảng cào dữ liệu!");
	};

	const handleCaptureSession = async (platform: string) => {
		try {
			toast.loading(`Đang khởi tạo phiên xác thực cho ${platform}...`, { id: "capture-session" });
			const res = await scraperPlatformAccountsApiService.capture(platform);
			toast.success(`Đã khởi tạo phiên xác thực (${res.capture_id}).`, { id: "capture-session" });
			fetchLiveAccounts();
		} catch (_err) {
			toast.error("Không thể kích hoạt phiên xác thực lúc này.", { id: "capture-session" });
		}
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

			<div className="flex-1 overflow-y-auto p-6 scrollbar-thin space-y-4">
				<div className="flex items-center justify-between">
					<p className="text-xs text-muted-foreground">
						Trạng thái kết nối và phiên làm việc (Session Pool) của các crawler chuyên sâu
					</p>
					<a
						href="/admin/scraper-accounts"
						className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600 dark:text-emerald-400 hover:underline"
					>
						<span>Quản lý Tài Khoản Scraper</span>
						<ExternalLink className="w-3 h-3" />
					</a>
				</div>

				<div className="grid grid-cols-1 gap-3.5">
					{[
						{
							id: "batdongsan",
							name: "Batdongsan.com.vn",
							icon: "🏠",
							credits: "1.5 Credits",
							account: accounts.find((a) => a.platform === "batdongsan"),
						},
						{
							id: "chotot_bds",
							name: "Chợ Tốt Nhà & BĐS",
							icon: "🛒",
							credits: "1.0 Credit",
							account: accounts.find((a) => a.platform === "chotot" || a.platform === "chotot_bds"),
						},
						{
							id: "muaban_bds",
							name: "Mua Bán BĐS Toàn Quốc",
							icon: "🏢",
							credits: "1.0 Credit",
							account: accounts.find((a) => a.platform === "muaban_bds"),
						},
						{
							id: "topcv",
							name: "TopCV & ITviec Hiring Signals",
							icon: "💼",
							credits: "1.2 Credits",
							account: accounts.find((a) => a.platform === "topcv"),
						},
						{
							id: "cafef",
							name: "CafeF Doanh Nghiệp & Tài Chính",
							icon: "📈",
							credits: "1.0 Credit",
							account: accounts.find((a) => a.platform === "cafef"),
						},
					].map((item) => {
						const _isConfigured = !!item.account;
						const isEnabled = item.account?.is_enabled ?? true;
						const hasCookies = !!item.account?.credentials?.cookies;

						return (
							<div
								key={item.id}
								className="p-4 rounded-xl border border-border bg-card flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-xs hover:border-emerald-500/40 transition-colors"
							>
								<div className="flex items-center gap-3">
									<span className="text-2xl">{item.icon}</span>
									<div>
										<div className="flex items-center gap-2">
											<h4 className="text-xs font-bold text-foreground">{item.name}</h4>
											<span
												className={cn(
													"inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold",
													isEnabled
														? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
														: "bg-amber-500/10 text-amber-700 dark:text-amber-400"
												)}
											>
												<CheckCircle className="w-2.5 h-2.5" />
												{isEnabled ? "Sẵn Sàng" : "Tạm Tắt"}
											</span>
											{item.account?.is_default && (
												<span className="px-1.5 py-0.2 rounded bg-blue-500/10 text-blue-600 text-[10px] font-bold">
													Default Pool
												</span>
											)}
										</div>
										<div className="flex items-center gap-3 text-[11px] text-muted-foreground mt-1">
											<span>
												Phiên Cookie:{" "}
												<strong className="text-foreground font-mono">
													{hasCookies ? "Đã cấu hình Session" : "Public FastCrawler"}
												</strong>
											</span>
											<span>•</span>
											<span>
												Định danh:{" "}
												<strong className="text-foreground font-mono">
													{item.account?.label || "Hệ thống Nowing"}
												</strong>
											</span>
											<span>•</span>
											<span>
												Chi phí:{" "}
												<strong className="text-emerald-600 dark:text-emerald-400 font-mono">
													{item.credits}
												</strong>
											</span>
										</div>
									</div>
								</div>

								<div className="flex items-center gap-2 self-end sm:self-center">
									<button
										type="button"
										onClick={() => handleCaptureSession(item.id)}
										className="px-2.5 py-1 text-[11px] font-semibold rounded-md border border-border bg-background hover:bg-muted text-foreground transition-colors cursor-pointer inline-flex items-center gap-1"
									>
										<ShieldCheck className="w-3 h-3 text-emerald-600" />
										<span>Nạp Cookie / Session</span>
									</button>
								</div>
							</div>
						);
					})}
				</div>
			</div>
		</div>
	);
};

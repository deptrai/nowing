"use client";

import { useQuery } from "@tanstack/react-query";
import {
	AlertTriangle,
	CheckCircle2,
	Coins,
	FileSpreadsheet,
	QrCode,
	RefreshCw,
	ShieldAlert,
	ShieldCheck,
	XCircle,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { AffiliatePayoutDetailModal } from "@/components/admin/AffiliatePayoutDetailModal";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import type { AdminPayoutItem } from "@/contracts/types/admin-affiliates.types";
import { adminAffiliatesApiService } from "@/lib/apis/admin-affiliates-api.service";

const LIMIT = 100;

export default function AffiliatePayoutsPage() {
	const [statusFilter, setStatusFilter] = useState<string>("all");
	const [selectedPayout, setSelectedPayout] = useState<AdminPayoutItem | null>(null);
	const [offset, setOffset] = useState<number>(0);
	const [allItems, setAllItems] = useState<AdminPayoutItem[]>([]);

	const { data, isLoading, error, refetch, isFetching } = useQuery({
		queryKey: ["admin", "affiliates", "payouts", statusFilter, offset],
		queryFn: () =>
			adminAffiliatesApiService.listPayouts({
				status: statusFilter === "all" ? undefined : statusFilter,
				limit: LIMIT,
				offset,
			}),
	});

	useEffect(() => {
		if (!data) return;
		setAllItems((prev) => (offset === 0 ? data.items : [...prev, ...data.items]));
	}, [data, offset]);

	const handleStatusFilter = (next: string) => {
		setStatusFilter(next);
		setOffset(0);
	};

	const handleLoadMore = () => {
		if (data && allItems.length < data.total) {
			setOffset((prev) => prev + LIMIT);
		}
	};

	const items = allItems;
	const hasMore = data ? allItems.length < data.total : false;

	// Calculate high-level summary metrics
	const metrics = useMemo(() => {
		let totalGross = 0;
		let totalNet = 0;
		let pendingCount = 0;
		let highRiskCount = 0;

		for (const p of items) {
			if (p.status === "pending") {
				pendingCount++;
				totalGross += p.gross_amount_vnd;
				totalNet += p.net_payout_amount_vnd;
				if (p.risk_level === "high" || p.risk_score >= 70) {
					highRiskCount++;
				}
			}
		}

		return { totalGross, totalNet, pendingCount, highRiskCount };
	}, [items]);

	return (
		<div className="space-y-6 p-6">
			{/* Header */}
			<div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
				<div>
					<div className="flex items-center gap-2">
						<h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
							Bàn Phê Duyệt Payout & Anti-Fraud Đối Tác
						</h1>
						<Badge
							variant="outline"
							className="border-primary/40 bg-primary/10 text-primary text-xs font-semibold"
						>
							Affiliate Desk
						</Badge>
					</div>
					<p className="mt-1 text-sm text-muted-foreground">
						Kiểm tra đối soát tên tài khoản ngân hàng, phát hiện gian lận self-referral ring và chi
						trả 1-click Napas 24/7 VietQR.
					</p>
				</div>

				<div className="flex items-center gap-2">
					<Button
						variant="outline"
						size="sm"
						onClick={() => refetch()}
						disabled={isFetching}
						className="gap-1.5 text-xs"
					>
						<RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`} />
						Làm mới
					</Button>
				</div>
			</div>

			{/* Stats Cards */}
			<div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
				<Card className="border-border/70 bg-card/60 backdrop-blur">
					<CardHeader className="flex flex-row items-center justify-between pb-2">
						<CardTitle className="text-xs font-medium text-muted-foreground uppercase">
							Chờ Phê Duyệt
						</CardTitle>
						<Coins className="h-4 w-4 text-primary" aria-hidden="true" />
					</CardHeader>
					<CardContent>
						<div className="text-2xl font-bold text-foreground">{metrics.pendingCount}</div>
						<p className="text-xs text-muted-foreground mt-1">Yêu cầu rút tiền chưa xử lý</p>
					</CardContent>
				</Card>

				<Card className="border-border/70 bg-card/60 backdrop-blur">
					<CardHeader className="flex flex-row items-center justify-between pb-2">
						<CardTitle className="text-xs font-medium text-muted-foreground uppercase">
							Tổng Tiền Chờ Chi (Gross)
						</CardTitle>
						<FileSpreadsheet className="h-4 w-4 text-blue-500" aria-hidden="true" />
					</CardHeader>
					<CardContent>
						<div className="text-2xl font-bold text-foreground">
							{metrics.totalGross.toLocaleString("vi-VN")} đ
						</div>
						<p className="text-xs text-muted-foreground mt-1">Trước khi khấu trừ 10% PIT</p>
					</CardContent>
				</Card>

				<Card className="border-border/70 bg-card/60 backdrop-blur">
					<CardHeader className="flex flex-row items-center justify-between pb-2">
						<CardTitle className="text-xs font-medium text-muted-foreground uppercase">
							Thực Chi Dự Kiến (Net)
						</CardTitle>
						<QrCode className="h-4 w-4 text-emerald-500" aria-hidden="true" />
					</CardHeader>
					<CardContent>
						<div className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">
							{metrics.totalNet.toLocaleString("vi-VN")} đ
						</div>
						<p className="text-xs text-muted-foreground mt-1">Chuyển qua VietQR Napas</p>
					</CardContent>
				</Card>

				<Card className="border-border/70 bg-card/60 backdrop-blur">
					<CardHeader className="flex flex-row items-center justify-between pb-2">
						<CardTitle className="text-xs font-medium text-muted-foreground uppercase">
							Cảnh Báo Gian Lận Cao
						</CardTitle>
						<ShieldAlert className="h-4 w-4 text-destructive" aria-hidden="true" />
					</CardHeader>
					<CardContent>
						<div className="text-2xl font-bold text-destructive">{metrics.highRiskCount}</div>
						<p className="text-xs text-muted-foreground mt-1">Yêu cầu bị khóa 1-click payout</p>
					</CardContent>
				</Card>
			</div>

			{/* Status Filter Tabs */}
			<div className="flex items-center gap-2 overflow-x-auto pb-1">
				{[
					{ id: "all", label: "Tất Cả Yêu Cầu" },
					{ id: "pending", label: "Chờ Phê Duyệt" },
					{ id: "processing", label: "Đang Chuyển Tiền" },
					{ id: "completed", label: "Đã Hoàn Tất" },
					{ id: "rejected", label: "Đã Từ Chối" },
				].map((tab) => (
					<Button
						key={tab.id}
						variant={statusFilter === tab.id ? "default" : "outline"}
						size="sm"
						onClick={() => handleStatusFilter(tab.id)}
						className="text-xs whitespace-nowrap"
					>
						{tab.label}
					</Button>
				))}
			</div>

			{/* Main Data Table */}
			<Card className="border-border/70 bg-card/60 backdrop-blur overflow-hidden">
				<CardHeader className="py-4 px-6 border-b border-border/40">
					<div className="flex items-center justify-between">
						<div>
							<CardTitle className="text-base font-bold">Danh Sách Yêu Cầu Rút Tiền</CardTitle>
							<CardDescription className="text-xs text-muted-foreground">
								Hiển thị {items.length} bản ghi
							</CardDescription>
						</div>
					</div>
				</CardHeader>

				<CardContent className="p-0">
					{isLoading ? (
						<div className="flex items-center justify-center py-20">
							<Spinner className="h-7 w-7 text-primary" />
						</div>
					) : error ? (
						<div className="p-8 text-center text-destructive text-sm">
							{(error as Error).message ?? "Không thể tải dữ liệu payout"}
						</div>
					) : items.length === 0 ? (
						<div className="p-12 text-center text-muted-foreground text-sm">
							Không có yêu cầu rút tiền nào trong trạng thái này.
						</div>
					) : (
						<Table>
							<TableHeader className="bg-muted/30">
								<TableRow className="text-xs">
									<TableHead>Đối Tác / Email</TableHead>
									<TableHead>Tài Khoản Thụ Hưởng</TableHead>
									<TableHead className="text-center">Đối Soát Tên</TableHead>
									<TableHead className="text-right">Tổng Tiền (Gross)</TableHead>
									<TableHead className="text-right">Thuế 10% (PIT)</TableHead>
									<TableHead className="text-right">Thực Nhận (Net)</TableHead>
									<TableHead className="text-center">Rủi Ro (Anti-Fraud)</TableHead>
									<TableHead className="text-center">Trạng Thái</TableHead>
									<TableHead className="text-right">Thao Tác</TableHead>
								</TableRow>
							</TableHeader>
							<TableBody>
								{items.map((item) => {
									const isHighRisk = item.risk_level === "high" || item.risk_score >= 70;
									const isMidRisk =
										item.risk_level === "mid" || (item.risk_score >= 30 && item.risk_score < 70);

									return (
										<TableRow
											key={item.id}
											className="cursor-pointer hover:bg-muted/20 text-xs"
											onClick={() => setSelectedPayout(item)}
										>
											{/* Partner Column */}
											<TableCell className="font-medium">
												<div className="flex flex-col">
													<span className="font-semibold text-foreground">
														{item.partner_email || item.partner_name}
													</span>
													<div className="flex items-center gap-1.5 mt-0.5">
														<span className="font-mono text-[11px] text-muted-foreground">
															{item.partner_code}
														</span>
														<Badge variant="secondary" className="text-[9px] uppercase px-1 py-0">
															{item.partner_tier}
														</Badge>
													</div>
												</div>
											</TableCell>

											{/* Bank Account Column */}
											<TableCell>
												<div className="flex flex-col">
													<span className="font-semibold text-foreground">
														{item.bank_short_name || item.bank_bin || "Napas 24/7"}
													</span>
													<span className="font-mono text-[11px] text-muted-foreground">
														{item.account_number} • {item.account_holder}
													</span>
												</div>
											</TableCell>

											{/* Name Match Badge */}
											<TableCell className="text-center">
												<Badge
													variant={
														item.name_match_status === "100% Match"
															? "default"
															: item.name_match_status === "Name Mismatch"
																? "destructive"
																: "secondary"
													}
													className="text-[10px] gap-1"
												>
													{item.name_match_status === "100% Match" ? (
														<CheckCircle2 className="h-3 w-3" aria-hidden="true" />
													) : item.name_match_status === "Name Mismatch" ? (
														<XCircle className="h-3 w-3" aria-hidden="true" />
													) : (
														<AlertTriangle className="h-3 w-3" aria-hidden="true" />
													)}
													{item.name_match_status}
												</Badge>
											</TableCell>

											{/* Gross Amount */}
											<TableCell className="text-right font-mono font-medium">
												{item.gross_amount_vnd.toLocaleString("vi-VN")} đ
											</TableCell>

											{/* PIT Tax */}
											<TableCell className="text-right font-mono text-destructive">
												{item.pit_tax_deduction_vnd > 0 ? (
													<span>- {item.pit_tax_deduction_vnd.toLocaleString("vi-VN")} đ</span>
												) : (
													<span className="text-muted-foreground">0 đ</span>
												)}
											</TableCell>

											{/* Net Amount */}
											<TableCell className="text-right font-mono font-bold text-primary">
												{item.net_payout_amount_vnd.toLocaleString("vi-VN")} đ
											</TableCell>

											{/* Fraud Risk Score */}
											<TableCell className="text-center">
												<Badge
													variant="outline"
													className={`text-[10px] gap-1 font-semibold ${
														isHighRisk
															? "border-destructive text-destructive bg-destructive/10"
															: isMidRisk
																? "border-amber-500 text-amber-500 bg-amber-500/10"
																: "border-emerald-500 text-emerald-600 bg-emerald-500/10"
													}`}
												>
													{isHighRisk ? (
														<ShieldAlert className="h-3 w-3" aria-hidden="true" />
													) : (
														<ShieldCheck className="h-3 w-3" aria-hidden="true" />
													)}
													{item.risk_score}/100 • {item.risk_level.toUpperCase()}
												</Badge>
											</TableCell>

											{/* Status */}
											<TableCell className="text-center">
												<Badge
													variant={
														item.status === "completed"
															? "default"
															: item.status === "processing"
																? "secondary"
																: item.status === "rejected"
																	? "destructive"
																	: "outline"
													}
													className="text-[10px] uppercase font-mono"
												>
													{item.status}
												</Badge>
											</TableCell>

											{/* Action */}
											<TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
												<Button
													size="sm"
													variant="outline"
													className="h-7 text-xs gap-1 font-medium"
													onClick={() => setSelectedPayout(item)}
												>
													<QrCode className="h-3 w-3" aria-hidden="true" />
													Xử Lý
												</Button>
											</TableCell>
										</TableRow>
									);
								})}
							</TableBody>
						</Table>
					)}

					{data && data.total > 0 && (
						<div className="px-6 py-3 border-t border-border/40 flex items-center justify-between">
							<span className="text-xs text-muted-foreground">
								Hiển thị {allItems.length} / {data.total} bản ghi
							</span>
							<Button
								size="sm"
								variant="outline"
								disabled={!hasMore || isFetching}
								onClick={handleLoadMore}
								className="text-xs"
							>
								{isFetching ? <Spinner className="h-3 w-3 mr-1" /> : null}
								Tải thêm
							</Button>
						</div>
					)}
				</CardContent>
			</Card>

			{/* Modal Detail & Actions */}
			<AffiliatePayoutDetailModal
				payout={selectedPayout}
				open={!!selectedPayout}
				onOpenChange={(open) => {
					if (!open) setSelectedPayout(null);
				}}
				onSuccess={() => {
					refetch();
				}}
			/>
		</div>
	);
}

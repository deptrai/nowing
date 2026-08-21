"use client";

import {
	AlertTriangle,
	ArrowRight,
	Building,
	CheckCircle2,
	Coins,
	FileText,
	Info,
	QrCode,
	ShieldAlert,
	ShieldCheck,
	User,
	XCircle,
} from "lucide-react";
import { useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import type {
	AdminPayoutItem,
	PayoutRejectionReason,
} from "@/contracts/types/admin-affiliates.types";
import { adminAffiliatesApiService } from "@/lib/apis/admin-affiliates-api.service";

interface AffiliatePayoutDetailModalProps {
	payout: AdminPayoutItem | null;
	open: boolean;
	onOpenChange: (open: boolean) => void;
	onSuccess: () => void;
}

export function AffiliatePayoutDetailModal({
	payout,
	open,
	onOpenChange,
	onSuccess,
}: AffiliatePayoutDetailModalProps) {
	const [isApproving, setIsApproving] = useState(false);
	const [isRejecting, setIsRejecting] = useState(false);
	const [isEvaluating, setIsEvaluating] = useState(false);
	const [showRejectForm, setShowRejectForm] = useState(false);
	const [rejectionReason, setRejectionReason] = useState<PayoutRejectionReason>("name_mismatch");
	const [rejectionNotes, setRejectionNotes] = useState("");
	const [error, setError] = useState<string | null>(null);

	if (!payout) return null;

	const isPending = payout.status === "pending";
	const isHighRisk = payout.risk_level === "high" || payout.risk_score >= 70;
	const canApprove =
		!isHighRisk && payout.name_match_status !== "Name Mismatch" && payout.gross_amount_vnd > 0;

	async function handleEvaluateRisk() {
		if (!payout) return;
		setIsEvaluating(true);
		setError(null);
		try {
			await adminAffiliatesApiService.evaluateRisk(payout.id);
			onSuccess();
		} catch (err) {
			setError((err as Error).message ?? "Không thể đánh giá rủi ro");
		} finally {
			setIsEvaluating(false);
		}
	}

	async function handleApprove() {
		if (!payout) return;
		setIsApproving(true);
		setError(null);
		try {
			await adminAffiliatesApiService.approvePayout(payout.id);
			onSuccess();
			onOpenChange(false);
		} catch (err) {
			setError((err as Error).message ?? "Không thể phê duyệt payout");
		} finally {
			setIsApproving(false);
		}
	}

	async function handleReject() {
		if (!payout) return;
		setIsRejecting(true);
		setError(null);
		try {
			await adminAffiliatesApiService.rejectPayout(payout.id, {
				rejection_reason: rejectionReason,
				notes: rejectionNotes || undefined,
			});
			onSuccess();
			onOpenChange(false);
		} catch (err) {
			setError((err as Error).message ?? "Không thể từ chối payout");
		} finally {
			setIsRejecting(false);
		}
	}

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="max-h-[92vh] max-w-2xl overflow-y-auto">
				<DialogHeader className="border-b border-border/40 pb-3">
					<div className="flex items-center justify-between">
						<div className="flex items-center gap-2">
							<QrCode className="h-5 w-5 text-primary" />
							<DialogTitle className="text-lg font-bold">
								Chi Tiết Yêu Cầu Rút Tiền Đối Tác (Payout Desk)
							</DialogTitle>
						</div>
						<Badge
							variant={
								payout.status === "completed"
									? "default"
									: payout.status === "processing"
										? "secondary"
										: payout.status === "rejected"
											? "destructive"
											: "outline"
							}
							className="font-mono uppercase text-xs"
						>
							{payout.status}
						</Badge>
					</div>
					<DialogDescription className="text-xs text-muted-foreground">
						Mã Payout: <span className="font-mono text-foreground">{payout.id}</span>
					</DialogDescription>
				</DialogHeader>

				{error && (
					<Alert variant="destructive" className="py-2.5 text-xs">
						<AlertTriangle className="h-4 w-4" />
						<AlertTitle className="text-xs font-semibold">Lỗi Xử Lý</AlertTitle>
						<AlertDescription>{error}</AlertDescription>
					</Alert>
				)}

				{/* High Risk Warning Alert */}
				{isHighRisk && isPending && (
					<Alert variant="destructive" className="bg-destructive/10 border-destructive/30 py-2.5">
						<ShieldAlert className="h-4 w-4 text-destructive" />
						<AlertTitle className="text-xs font-bold text-destructive">
							Cảnh Báo: Rủi Ro Gian Lận Mức Độ Cao (Điểm: {payout.risk_score}/100)
						</AlertTitle>
						<AlertDescription className="text-[11px] text-destructive/90">
							Hệ thống phát hiện dấu hiệu bất thường (Self-referral ring hoặc không khớp tên ngân
							hàng). Quy trình 1-click Napas bị tạm khóa cho đến khi có sự phê duyệt từ quản lý cấp
							cao.
						</AlertDescription>
					</Alert>
				)}

				<div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
					{/* Partner Info Box */}
					<div className="rounded-lg border border-border/70 bg-card p-3.5 space-y-2.5">
						<div className="flex items-center gap-1.5 font-semibold text-foreground border-b border-border/40 pb-1.5">
							<User className="h-4 w-4 text-primary" />
							<span>Thông Tin Đối Tác Affiliate</span>
						</div>
						<div className="space-y-1.5 text-muted-foreground">
							<div className="flex justify-between">
								<span>Tên / Email:</span>
								<span className="font-medium text-foreground">
									{payout.partner_email || payout.partner_name}
								</span>
							</div>
							<div className="flex justify-between">
								<span>Mã Giới Thiệu:</span>
								<Badge variant="outline" className="font-mono text-[10px]">
									{payout.partner_code}
								</Badge>
							</div>
							<div className="flex justify-between">
								<span>Hạng Đối Tác:</span>
								<span className="capitalize font-medium text-foreground">
									{payout.partner_tier}
								</span>
							</div>
							<div className="flex justify-between">
								<span>Thời Gian Tạo:</span>
								<span>{new Date(payout.created_at).toLocaleString("vi-VN")}</span>
							</div>
						</div>
					</div>

					{/* Bank & Beneficiary Box */}
					<div className="rounded-lg border border-border/70 bg-card p-3.5 space-y-2.5">
						<div className="flex items-center justify-between border-b border-border/40 pb-1.5">
							<div className="flex items-center gap-1.5 font-semibold text-foreground">
								<Building className="h-4 w-4 text-primary" />
								<span>Tài Khoản Nhận Tiền</span>
							</div>
							<Badge
								variant={
									payout.name_match_status === "100% Match"
										? "default"
										: payout.name_match_status === "Name Mismatch"
											? "destructive"
											: "secondary"
								}
								className="text-[10px] gap-1"
							>
								{payout.name_match_status === "100% Match" ? (
									<CheckCircle2 className="h-3 w-3" />
								) : payout.name_match_status === "Name Mismatch" ? (
									<XCircle className="h-3 w-3" />
								) : (
									<Info className="h-3 w-3" />
								)}
								{payout.name_match_status}
							</Badge>
						</div>
						<div className="space-y-1.5 text-muted-foreground">
							<div className="flex justify-between">
								<span>Ngân Hàng:</span>
								<span className="font-medium text-foreground">
									{payout.bank_short_name || payout.bank_bin || "Napas 24/7"}
								</span>
							</div>
							<div className="flex justify-between">
								<span>Số Tài Khoản:</span>
								<span className="font-mono font-bold text-foreground">{payout.account_number}</span>
							</div>
							<div className="flex justify-between">
								<span>Chủ Tài Khoản:</span>
								<span className="font-bold text-foreground uppercase">{payout.account_holder}</span>
							</div>
						</div>
					</div>
				</div>

				{/* Financial Breakdown (Gross, PIT Tax, Net) */}
				<div className="rounded-lg border border-primary/20 bg-primary/5 p-3.5 space-y-2 text-xs">
					<div className="flex items-center justify-between font-semibold text-primary border-b border-primary/20 pb-1.5">
						<div className="flex items-center gap-1.5">
							<Coins className="h-4 w-4" />
							<span>Bảng Kê Chi Trả & Khấu Trừ Thuế TNCN (TT 111/2013/TT-BTC)</span>
						</div>
					</div>
					<div className="grid grid-cols-3 gap-3 pt-1 text-center">
						<div className="p-2 rounded bg-background/80 border border-border/50">
							<div className="text-[10px] text-muted-foreground uppercase">
								Tổng Hoa Hồng (Gross)
							</div>
							<div className="text-sm font-bold text-foreground mt-0.5">
								{payout.gross_amount_vnd.toLocaleString("vi-VN")} đ
							</div>
						</div>
						<div className="p-2 rounded bg-background/80 border border-border/50">
							<div className="text-[10px] text-muted-foreground uppercase">Thuế TNCN 10% (PIT)</div>
							<div className="text-sm font-bold text-destructive mt-0.5">
								- {payout.pit_tax_deduction_vnd.toLocaleString("vi-VN")} đ
							</div>
						</div>
						<div className="p-2 rounded bg-background/80 border border-primary/30">
							<div className="text-[10px] text-primary uppercase font-semibold">
								Thực Nhận (Net Payout)
							</div>
							<div className="text-base font-extrabold text-primary mt-0.5">
								{payout.net_payout_amount_vnd.toLocaleString("vi-VN")} đ
							</div>
						</div>
					</div>
				</div>

				{/* Anti-Fraud Assessment Details */}
				<div className="rounded-lg border border-border/70 bg-card p-3.5 space-y-2 text-xs">
					<div className="flex items-center justify-between border-b border-border/40 pb-1.5">
						<div className="flex items-center gap-1.5 font-semibold text-foreground">
							<ShieldCheck className="h-4 w-4 text-primary" />
							<span>Kết Quả Đánh Giá Anti-Fraud Engine</span>
						</div>
						<Button
							variant="ghost"
							size="sm"
							className="h-6 text-[11px] px-2 text-primary"
							onClick={handleEvaluateRisk}
							disabled={isEvaluating}
						>
							{isEvaluating ? <Spinner className="h-3 w-3 mr-1" /> : null}
							Đánh giá lại
						</Button>
					</div>

					<div className="space-y-1 pt-1">
						{payout.risk_reasons && payout.risk_reasons.length > 0 ? (
							payout.risk_reasons.map((reason) => (
								<div key={reason} className="flex items-start gap-1.5 text-muted-foreground">
									<ArrowRight className="h-3.5 w-3.5 text-primary shrink-0 mt-0.5" />
									<span>{reason}</span>
								</div>
							))
						) : (
							<p className="text-muted-foreground italic">
								Không có cảnh báo rủi ro nào được ghi nhận.
							</p>
						)}
					</div>
				</div>

				{/* Rejection Form Drawer */}
				{showRejectForm && (
					<div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3.5 space-y-3 text-xs">
						<div className="flex items-center gap-1.5 font-semibold text-destructive">
							<FileText className="h-4 w-4" />
							<span>Lý Do Từ Chối Yêu Cầu Payout (Ledger Rollback)</span>
						</div>

						<div className="space-y-2">
							<div>
								<Label className="text-xs">Phân Loại Lý Do:</Label>
								<Select
									value={rejectionReason}
									onValueChange={(val) => setRejectionReason(val as PayoutRejectionReason)}
								>
									<SelectTrigger className="h-8 text-xs mt-1">
										<SelectValue />
									</SelectTrigger>
									<SelectContent>
										<SelectItem value="name_mismatch">
											Khác Tên Thụ Hưởng Ngân Hàng (Name Mismatch)
										</SelectItem>
										<SelectItem value="suspected_fraud_ring">
											Nghi Vấn Gian Lận / Self-Referral Ring
										</SelectItem>
										<SelectItem value="invalid_account">
											Tài Khoản Không Hợp Lệ Hoặc Đã Đóng
										</SelectItem>
									</SelectContent>
								</Select>
							</div>

							<div>
								<Label className="text-xs">Ghi Chú Chi Tiết (Tùy chọn):</Label>
								<Textarea
									placeholder="Nhập ghi chú cho đối tác và lưu vết Audit Event..."
									value={rejectionNotes}
									onChange={(e) => setRejectionNotes(e.target.value)}
									className="text-xs h-16 mt-1"
								/>
							</div>
						</div>
					</div>
				)}

				<DialogFooter className="pt-2 border-t border-border/40 gap-2 sm:gap-0">
					{isPending && (
						<div className="flex items-center justify-between w-full">
							<div>
								{!showRejectForm ? (
									<Button
										type="button"
										variant="outline"
										size="sm"
										className="text-destructive hover:bg-destructive/10"
										onClick={() => setShowRejectForm(true)}
									>
										Từ Chối Payout
									</Button>
								) : (
									<div className="flex items-center gap-1.5">
										<Button
											type="button"
											variant="destructive"
											size="sm"
											onClick={handleReject}
											disabled={isRejecting}
										>
											{isRejecting ? <Spinner className="h-3 w-3 mr-1" /> : null}
											Xác Nhận Từ Chối
										</Button>
										<Button
											type="button"
											variant="ghost"
											size="sm"
											onClick={() => setShowRejectForm(false)}
										>
											Hủy
										</Button>
									</div>
								)}
							</div>

							<div className="flex items-center gap-2">
								<Button
									type="button"
									variant="outline"
									size="sm"
									onClick={() => onOpenChange(false)}
								>
									Đóng
								</Button>
								<Button
									type="button"
									size="sm"
									className="gap-1.5 font-semibold bg-emerald-600 hover:bg-emerald-700 text-white"
									onClick={handleApprove}
									disabled={!canApprove || isApproving}
								>
									{isApproving ? (
										<Spinner className="h-3 w-3 mr-1" />
									) : (
										<QrCode className="h-3.5 w-3.5" />
									)}
									Phê Duyệt & Chuyển Tiền VietQR
								</Button>
							</div>
						</div>
					)}
					{!isPending && (
						<Button type="button" variant="outline" size="sm" onClick={() => onOpenChange(false)}>
							Đóng
						</Button>
					)}
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}

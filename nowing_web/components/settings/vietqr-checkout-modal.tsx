"use client";

import { useQuery } from "@tanstack/react-query";
import { Building2, Check, CheckCircle2, Copy, Timer, XCircle } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import type { TopupIntent } from "@/contracts/types/vietqr.types";
import { vietqrApiService } from "@/lib/apis/vietqr-api.service";

const formatVnd = (vnd: number) => `${vnd.toLocaleString("vi-VN")}đ`;

const formatCountdown = (ms: number) => {
	const total = Math.max(0, Math.floor(ms / 1000));
	const m = Math.floor(total / 60);
	const s = total % 60;
	return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
};

interface VietQRCheckoutModalProps {
	intent: TopupIntent | null;
	open: boolean;
	onOpenChange: (open: boolean) => void;
	onCompleted?: (intent: TopupIntent) => void;
}

/**
 * Dynamic VietQR transfer modal (Story 37.7 / AC-2).
 *
 * Shows the per-intent QR + transfer memo with a 10-minute countdown and
 * polls the intent status until the Napas webhook credits the wallet.
 */
export function VietQRCheckoutModal({
	intent,
	open,
	onOpenChange,
	onCompleted,
}: VietQRCheckoutModalProps) {
	const [copiedField, setCopiedField] = useState<string | null>(null);
	const [now, setNow] = useState(() => Date.now());

	// Defensive parse: a malformed expires_at reads as already-expired, never NaN.
	const expiresAtMs = useMemo(() => {
		const t = intent ? new Date(intent.expires_at).getTime() : Number.NaN;
		return Number.isFinite(t) ? t : 0;
	}, [intent]);
	const remainingMs = expiresAtMs - now;

	// Poll while the transfer window is open; refetchInterval keys off the
	// *current* (polled) status so a completed/expired/failed flip stops polling.
	const { data: polled } = useQuery({
		queryKey: ["vietqr-topup-intent", intent?.intent_id],
		queryFn: () => {
			if (!intent) throw new Error("missing intent");
			return vietqrApiService.getTopupIntent(intent.intent_id);
		},
		enabled: open && !!intent,
		refetchInterval: (query) => {
			const status = query.state.data?.status ?? intent?.status;
			return status === "pending" && remainingMs > 0 ? 3000 : false;
		},
	});

	const current = polled ?? intent;
	const isCompleted = current?.status === "completed";
	const isFailed = current?.status === "failed";
	// polled status can flip to "expired" server-side, so derive from `current`
	const isExpired = current?.status === "expired" || remainingMs <= 0;

	// 1s countdown tick
	useEffect(() => {
		if (!open || !intent) return;
		const tick = setInterval(() => setNow(Date.now()), 1000);
		return () => clearInterval(tick);
	}, [open, intent]);

	// Fire onCompleted exactly once per intent id — poll updates must not
	// re-trigger the parent's success toast/invalidation on every render.
	const completedIntentRef = useRef<string | null>(null);
	useEffect(() => {
		if (isCompleted && current && completedIntentRef.current !== current.intent_id) {
			completedIntentRef.current = current.intent_id;
			onCompleted?.(current);
		}
	}, [isCompleted, current, onCompleted]);

	const copyToClipboard = (text: string, field: string) => {
		navigator.clipboard
			.writeText(text)
			.then(() => {
				setCopiedField(field);
				toast.success(`Đã sao chép ${field}`);
				setTimeout(() => setCopiedField(null), 2000);
			})
			.catch(() => {
				toast.error("Không sao chép được — vui lòng copy thủ công.");
			});
	};

	if (!intent || !current) return null;

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="sm:max-w-md">
				<DialogHeader>
					<DialogTitle className="flex items-center gap-2">
						Thanh toán VietQR
						{!isCompleted && !isFailed && !isExpired && (
							<span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-xs font-semibold text-amber-600 dark:text-amber-400 tabular-nums">
								<Timer className="size-3" aria-hidden="true" />
								{formatCountdown(remainingMs)}
							</span>
						)}
					</DialogTitle>
					<DialogDescription>
						Quét mã bằng app ngân hàng — credits tự động cộng trong ~5 giây sau khi chuyển khoản
						thành công.
					</DialogDescription>
				</DialogHeader>

				{isCompleted ? (
					<div className="flex flex-col items-center gap-2 py-6 text-center">
						<CheckCircle2 className="size-10 text-emerald-500" aria-hidden="true" />
						<p className="font-semibold">Thanh toán thành công!</p>
						<p className="text-sm text-muted-foreground">
							{current.credits.toLocaleString("vi-VN")} credits đã được cộng vào ví của bạn.
						</p>
						<Button className="mt-2" onClick={() => onOpenChange(false)}>
							Đóng
						</Button>
					</div>
				) : isExpired || isFailed ? (
					<div className="flex flex-col items-center gap-2 py-6 text-center">
						<XCircle className="size-10 text-destructive" aria-hidden="true" />
						<p className="font-semibold">Mã QR đã hết hạn</p>
						<p className="text-sm text-muted-foreground">
							Giao dịch chuyển khoản quá 10 phút. Vui lòng tạo mã mới để tiếp tục.
						</p>
						<Button className="mt-2" onClick={() => onOpenChange(false)}>
							Đóng
						</Button>
					</div>
				) : (
					<div className="space-y-3">
						<div className="flex flex-col sm:flex-row items-center gap-4">
							<div className="bg-white p-2 rounded-lg border shadow-sm shrink-0">
								{/* biome-ignore lint/performance/noImgElement: dynamic external qr code */}
								<img
									src={current.qr_url}
									alt="VietQR Napas 24/7"
									className="w-40 h-40 object-contain rounded"
								/>
							</div>
							<div className="w-full space-y-2 text-xs">
								<div className="flex items-center justify-between border-b pb-1.5">
									<span className="text-muted-foreground flex items-center gap-1">
										<Building2 className="size-3.5 text-emerald-500" aria-hidden="true" />
										Ngân hàng
									</span>
									<span className="font-semibold">{current.bank_name}</span>
								</div>
								<div className="flex items-center justify-between border-b pb-1.5">
									<span className="text-muted-foreground">Số tài khoản</span>
									<button
										type="button"
										onClick={() => copyToClipboard(current.bank_account_number, "Số tài khoản")}
										className="font-mono font-bold text-emerald-600 dark:text-emerald-400 hover:underline flex items-center gap-1 cursor-pointer"
									>
										{current.bank_account_number}
										{copiedField === "Số tài khoản" ? (
											<Check className="size-3 text-emerald-500" aria-hidden="true" />
										) : (
											<Copy className="size-3" aria-hidden="true" />
										)}
									</button>
								</div>
								<div className="flex items-center justify-between border-b pb-1.5">
									<span className="text-muted-foreground">Tên thụ hưởng</span>
									<span className="font-semibold uppercase">{current.bank_account_name}</span>
								</div>
								<div className="flex items-center justify-between border-b pb-1.5">
									<span className="text-muted-foreground">Số tiền</span>
									<button
										type="button"
										onClick={() => copyToClipboard(String(current.amount_vnd), "Số tiền")}
										className="font-bold text-foreground hover:underline flex items-center gap-1 cursor-pointer tabular-nums"
									>
										{formatVnd(current.amount_vnd)}
										{copiedField === "Số tiền" ? (
											<Check className="size-3 text-emerald-500" aria-hidden="true" />
										) : (
											<Copy className="size-3" aria-hidden="true" />
										)}
									</button>
								</div>
								<div className="flex items-center justify-between">
									<span className="text-muted-foreground">Nội dung CK</span>
									<button
										type="button"
										onClick={() => copyToClipboard(current.transfer_memo, "Nội dung chuyển khoản")}
										className="font-mono font-bold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 px-1.5 py-0.5 rounded hover:bg-emerald-500/20 flex items-center gap-1 cursor-pointer"
									>
										{current.transfer_memo}
										{copiedField === "Nội dung chuyển khoản" ? (
											<Check className="size-3 text-emerald-500" aria-hidden="true" />
										) : (
											<Copy className="size-3" aria-hidden="true" />
										)}
									</button>
								</div>
							</div>
						</div>
						<p className="text-[11px] text-center text-muted-foreground">
							⚡ Credits tự động cộng trong ~5 giây sau khi Napas xác nhận chuyển khoản. Giữ nguyên
							nội dung CK để hệ thống đối soát.
						</p>
					</div>
				)}
			</DialogContent>
		</Dialog>
	);
}

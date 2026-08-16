"use client";

import { useQuery as useZeroQuery } from "@rocicorp/zero/react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { Building2, Check, Copy, CreditCard, Minus, Plus, QrCode } from "lucide-react";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { stripeApiService } from "@/lib/apis/stripe-api.service";
import { AppError } from "@/lib/error";
import { getWorkspaceIdNumber } from "@/lib/route-params";
import { cn } from "@/lib/utils";
import { queries } from "@/zero/queries";

// One pack = $1.00 of credit, stored as 1_000_000 micro-USD on the backend.
const CREDIT_PER_PACK_MICROS = 1_000_000;
const PRICE_PER_PACK_USD = 1;
const USD_TO_VND_RATE = 25400;
const PRESET_MULTIPLIERS = [1, 2, 5, 10, 25, 50, 100] as const;
const MIN_QUANTITY = 1;
const MAX_QUANTITY = 10_000;

const clampQuantity = (value: number) =>
	Math.min(MAX_QUANTITY, Math.max(MIN_QUANTITY, Math.floor(value)));

const formatUsd = (micros: number) => {
	const dollars = Math.max(0, micros) / 1_000_000;
	if (dollars >= 100) return `$${dollars.toFixed(0)}`;
	if (dollars >= 1) return `$${dollars.toFixed(2)}`;
	if (dollars > 0) return `$${dollars.toFixed(3)}`;
	return "$0.00";
};

export function BuyCreditsContent() {
	const params = useParams();
	const workspaceId = getWorkspaceIdNumber(params) ?? 0;
	const [quantity, setQuantity] = useState(5);
	const [amountInput, setAmountInput] = useState("5");
	const [paymentMethod, setPaymentMethod] = useState<"stripe" | "vietqr">("vietqr");
	const [copiedField, setCopiedField] = useState<string | null>(null);

	const { data: currentUser } = useAtomValue(currentUserAtom);

	const commitQuantity = (value: number) => {
		const clamped = clampQuantity(Number.isFinite(value) ? value : MIN_QUANTITY);
		setQuantity(clamped);
		setAmountInput(String(clamped));
	};

	// Server config flag
	const { data: creditStatus } = useQuery({
		queryKey: ["credit-status"],
		queryFn: () => stripeApiService.getCreditStatus(),
	});

	// Live per-user balance via Zero
	const [me] = useZeroQuery(queries.user.me({}));

	const purchaseMutation = useMutation({
		mutationFn: stripeApiService.createCreditCheckoutSession,
		onSuccess: (response) => {
			window.location.assign(response.checkout_url);
		},
		onError: (error) => {
			if (error instanceof AppError && error.message) {
				toast.error(error.message);
				return;
			}
			toast.error("Failed to start checkout. Please try again.");
		},
	});

	const totalCreditMicros = quantity * CREDIT_PER_PACK_MICROS;
	const totalPriceUsd = quantity * PRICE_PER_PACK_USD;
	const totalPriceVnd = quantity * USD_TO_VND_RATE;
	const balanceMicros =
		me?.creditMicrosBalance ??
		creditStatus?.credit_micros_balance ??
		currentUser?.credit_micros_balance ??
		0;

	const userCode = currentUser?.id
		? String(currentUser.id).replace(/-/g, "").slice(0, 8).toUpperCase()
		: "NOWING";
	const transferMemo = `NOWING ${userCode}`;

	const copyToClipboard = (text: string, field: string) => {
		navigator.clipboard.writeText(text);
		setCopiedField(field);
		toast.success(`Đã sao chép ${field}`);
		setTimeout(() => setCopiedField(null), 2000);
	};

	const qrUrl = `https://img.vietqr.io/image/970436-1028384950-compact2.png?amount=${totalPriceVnd}&addInfo=${encodeURIComponent(transferMemo)}&accountName=NOWING%20VIETNAM`;

	return (
		<div className="w-full space-y-4">
			<div className="text-center">
				<h2 className="font-serif text-2xl sm:text-3xl font-normal tracking-tight">Nạp Credits</h2>
				<p className="text-xs text-muted-foreground mt-1">
					1 USD = 100 Credits = 25.400đ (Chi trả theo thực tế sử dụng)
				</p>
			</div>

			{/* Balance Card */}
			<div className="rounded-lg border bg-muted/20 p-3">
				<div className="flex items-center justify-between text-sm">
					<span className="text-muted-foreground">Số dư hiện tại</span>
					<span className="font-semibold tabular-nums text-emerald-600 dark:text-emerald-400">
						{formatUsd(balanceMicros)} ({(balanceMicros / 10_000).toLocaleString("vi-VN")} Credits)
					</span>
				</div>
			</div>

			{/* Payment Method Switcher */}
			<div className="grid grid-cols-2 gap-2 p-1 bg-muted/40 rounded-lg border">
				<button
					type="button"
					onClick={() => setPaymentMethod("vietqr")}
					className={cn(
						"flex items-center justify-center gap-2 py-2 text-xs font-semibold rounded-md transition-all cursor-pointer",
						paymentMethod === "vietqr"
							? "bg-background text-foreground shadow-sm border border-emerald-500/30 text-emerald-600 dark:text-emerald-400"
							: "text-muted-foreground hover:text-foreground"
					)}
				>
					<QrCode className="size-4 text-emerald-500" />
					VietQR Chuyển Khoản 24/7
				</button>
				<button
					type="button"
					onClick={() => setPaymentMethod("stripe")}
					className={cn(
						"flex items-center justify-center gap-2 py-2 text-xs font-semibold rounded-md transition-all cursor-pointer",
						paymentMethod === "stripe"
							? "bg-background text-foreground shadow-sm border border-primary/30 text-primary"
							: "text-muted-foreground hover:text-foreground"
					)}
				>
					<CreditCard className="size-4" />
					Thẻ Quốc Tế (Stripe)
				</button>
			</div>

			{/* Quantity Selection */}
			<div className="space-y-3">
				<div className="flex items-center justify-center gap-3">
					<Button
						type="button"
						variant="ghost"
						size="icon"
						onClick={() => commitQuantity(quantity - 1)}
						disabled={quantity <= MIN_QUANTITY || purchaseMutation.isPending}
						className="size-8 text-muted-foreground shadow-none transition-colors hover:bg-muted hover:text-foreground disabled:opacity-40"
					>
						<Minus className="h-3.5 w-3.5" />
					</Button>
					<div className="flex items-baseline gap-1.5">
						<span className="text-lg font-semibold">$</span>
						<input
							type="text"
							inputMode="numeric"
							value={amountInput}
							onChange={(e) => {
								const raw = e.target.value.replace(/[^0-9]/g, "");
								setAmountInput(raw);
								const parsed = Number.parseInt(raw, 10);
								if (Number.isFinite(parsed)) {
									setQuantity(clampQuantity(parsed));
								}
							}}
							onBlur={() => commitQuantity(Number.parseInt(amountInput, 10))}
							disabled={purchaseMutation.isPending}
							aria-label="Credit amount in US dollars"
							className="w-20 rounded-md border bg-transparent px-2 py-1 text-center text-lg font-semibold tabular-nums outline-none focus:ring-2 focus:ring-ring disabled:opacity-60"
						/>
						<span className="text-sm text-muted-foreground">
							({(quantity * 100).toLocaleString("vi-VN")} Credits)
						</span>
					</div>
					<Button
						type="button"
						variant="ghost"
						size="icon"
						onClick={() => commitQuantity(quantity + 1)}
						disabled={quantity >= MAX_QUANTITY || purchaseMutation.isPending}
						className="size-8 text-muted-foreground shadow-none transition-colors hover:bg-muted hover:text-foreground disabled:opacity-40"
					>
						<Plus className="h-3.5 w-3.5" />
					</Button>
				</div>

				<div className="flex flex-wrap justify-center gap-1.5">
					{PRESET_MULTIPLIERS.map((m) => (
						<Button
							key={m}
							type="button"
							variant="ghost"
							onClick={() => commitQuantity(m)}
							disabled={purchaseMutation.isPending}
							className={cn(
								"h-auto rounded-md px-2.5 py-1 text-xs font-medium tabular-nums transition-colors disabled:opacity-60",
								quantity === m
									? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30"
									: "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
							)}
						>
							${m} ({m * 100} Cr)
						</Button>
					))}
				</div>

				{/* VietQR View */}
				{paymentMethod === "vietqr" && (
					<div className="space-y-3 rounded-xl border bg-muted/20 p-4 animate-in fade-in-50">
						<div className="flex flex-col sm:flex-row items-center gap-4">
							<div className="bg-white p-2 rounded-lg border shadow-sm shrink-0">
								{/* biome-ignore lint/performance/noImgElement: dynamic external qr code */}
								<img
									src={qrUrl}
									alt="VietQR Napas 24/7"
									className="w-36 h-36 object-contain rounded"
								/>
							</div>
							<div className="w-full space-y-2 text-xs">
								<div className="flex items-center justify-between border-b pb-1.5">
									<span className="text-muted-foreground flex items-center gap-1">
										<Building2 className="size-3.5 text-emerald-500" /> Ngân hàng
									</span>
									<span className="font-semibold">Vietcombank (VCB)</span>
								</div>
								<div className="flex items-center justify-between border-b pb-1.5">
									<span className="text-muted-foreground">Số tài khoản</span>
									<button
										type="button"
										onClick={() => copyToClipboard("1028384950", "Số tài khoản")}
										className="font-mono font-bold text-emerald-600 dark:text-emerald-400 hover:underline flex items-center gap-1 cursor-pointer"
									>
										1028384950
										{copiedField === "Số tài khoản" ? (
											<Check className="size-3 text-emerald-500" />
										) : (
											<Copy className="size-3" />
										)}
									</button>
								</div>
								<div className="flex items-center justify-between border-b pb-1.5">
									<span className="text-muted-foreground">Tên thụ hưởng</span>
									<span className="font-semibold uppercase">NOWING VIETNAM</span>
								</div>
								<div className="flex items-center justify-between border-b pb-1.5">
									<span className="text-muted-foreground">Số tiền</span>
									<button
										type="button"
										onClick={() => copyToClipboard(String(totalPriceVnd), "Số tiền")}
										className="font-bold text-foreground hover:underline flex items-center gap-1 cursor-pointer tabular-nums"
									>
										{totalPriceVnd.toLocaleString("vi-VN")} đ (${totalPriceUsd})
										{copiedField === "Số tiền" ? (
											<Check className="size-3 text-emerald-500" />
										) : (
											<Copy className="size-3" />
										)}
									</button>
								</div>
								<div className="flex items-center justify-between">
									<span className="text-muted-foreground">Nội dung CK</span>
									<button
										type="button"
										onClick={() => copyToClipboard(transferMemo, "Nội dung chuyển khoản")}
										className="font-mono font-bold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 px-1.5 py-0.5 rounded hover:bg-emerald-500/20 flex items-center gap-1 cursor-pointer"
									>
										{transferMemo}
										{copiedField === "Nội dung chuyển khoản" ? (
											<Check className="size-3 text-emerald-500" />
										) : (
											<Copy className="size-3" />
										)}
									</button>
								</div>
							</div>
						</div>
						<p className="text-[11px] text-center text-muted-foreground">
							⚡ Hệ thống tự động kiểm tra và cộng credits trong vòng 30 - 60 giây sau khi chuyển
							khoản.
						</p>
					</div>
				)}

				{/* Stripe View */}
				{paymentMethod === "stripe" && (
					<div className="space-y-3">
						<div className="flex items-center justify-between rounded-lg border bg-muted/30 px-3 py-2">
							<span className="text-sm font-medium tabular-nums">
								${(totalCreditMicros / 1_000_000).toFixed(0)} of credit (
								{(quantity * 100).toLocaleString("vi-VN")} Credits)
							</span>
							<span className="text-sm font-semibold tabular-nums">${totalPriceUsd}</span>
						</div>

						<Button
							className="w-full"
							disabled={purchaseMutation.isPending}
							onClick={() => purchaseMutation.mutate({ quantity, workspace_id: workspaceId })}
						>
							{purchaseMutation.isPending ? (
								<>
									<Spinner size="xs" />
									Đang khởi tạo thanh toán…
								</>
							) : (
								<>Thanh toán qua Stripe (${totalPriceUsd})</>
							)}
						</Button>
						<p className="text-center text-[11px] text-muted-foreground">
							Bảo mật thanh toán quốc tế qua Stripe
						</p>
					</div>
				)}
			</div>
		</div>
	);
}

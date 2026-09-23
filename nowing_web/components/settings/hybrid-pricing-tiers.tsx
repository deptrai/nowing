"use client";

import { useQuery as useZeroQuery } from "@rocicorp/zero/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { BadgeCheck, Calculator, CreditCard, Crown, QrCode, Users } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Spinner } from "@/components/ui/spinner";
import type { PricingTier, TopupIntent } from "@/contracts/types/vietqr.types";
import { stripeApiService } from "@/lib/apis/stripe-api.service";
import { vietqrApiService } from "@/lib/apis/vietqr-api.service";
import { AppError } from "@/lib/error";
import { getWorkspaceIdNumber } from "@/lib/route-params";
import { cn } from "@/lib/utils";
import { queries } from "@/zero/queries";
import { VietQRCheckoutModal } from "./vietqr-checkout-modal";

// 1 USD = 100 credits — matches the buy-credits conversion. The VND rate is
// server-provided (vnd_per_usd on /vietqr/pricing-tiers).
const CREDITS_PER_USD = 100;
const MIN_CUSTOM_CREDITS = 100;
const MAX_CUSTOM_CREDITS = 50_000;
const CREDIT_STEP = 100;

const formatVnd = (vnd: number) => `${vnd.toLocaleString("vi-VN")}đ`;

const customAmountVnd = (credits: number, vndPerUsd: number) =>
	Math.round((credits / CREDITS_PER_USD) * vndPerUsd);

const TIER_FEATURES: Record<string, string[]> = {
	starter: ["1.000 credits / tháng", "1 seat", "Báo cáo cơ bản"],
	professional: ["3.500 credits / tháng", "3 seats", "Ưu tiên hỗ trợ", "Auto-refund bảo đảm"],
	business: [
		"10.000 credits / tháng",
		"Không giới hạn seats",
		"Ưu tiên cao nhất",
		"Auto-refund bảo đảm",
	],
};

/**
 * Hybrid Vietnamese pricing tiers + credit calculator (Story 37.7 / AC-1).
 *
 * Tier and custom-amount selections both open the dynamic VietQR checkout
 * modal backed by a server-side 10-minute payment intent.
 */
export function HybridPricingTiers() {
	const params = useParams();
	const workspaceId = getWorkspaceIdNumber(params) ?? 0;
	const queryClient = useQueryClient();

	const [customCredits, setCustomCredits] = useState(2_000);
	const [activeIntent, setActiveIntent] = useState<TopupIntent | null>(null);
	const [modalOpen, setModalOpen] = useState(false);

	const { data: currentUser } = useAtomValue(currentUserAtom);
	const { data: creditStatus } = useQuery({
		queryKey: ["credit-status"],
		queryFn: () => stripeApiService.getCreditStatus(),
	});
	const [me] = useZeroQuery(queries.user.me({}));

	const {
		data: tiersData,
		isLoading: tiersLoading,
		isError: tiersError,
	} = useQuery({
		queryKey: ["vietqr-pricing-tiers"],
		queryFn: () => vietqrApiService.getPricingTiers(),
	});
	const vndPerUsd = tiersData?.vnd_per_usd ?? null;

	const intentMutation = useMutation({
		mutationFn: vietqrApiService.createTopupIntent,
		onSuccess: (intent) => {
			setActiveIntent(intent);
			setModalOpen(true);
		},
		onError: (error) => {
			if (error instanceof AppError && error.message) {
				toast.error(error.message);
				return;
			}
			toast.error("Không khởi tạo được giao dịch. Vui lòng thử lại.");
		},
	});

	const balanceMicros =
		me?.creditMicrosBalance ??
		creditStatus?.credit_micros_balance ??
		currentUser?.credit_micros_balance ??
		0;

	const handleCompleted = () => {
		queryClient.invalidateQueries({ queryKey: ["credit-status"] });
		toast.success("Credits đã được cộng vào ví!");
	};

	return (
		<div className="w-full space-y-6">
			<div className="text-center">
				<h2 className="font-serif text-2xl sm:text-3xl font-normal tracking-tight">
					Gói Cước & Credits
				</h2>
				<p className="text-xs text-muted-foreground mt-1">
					1 USD = 100 Credits
					{vndPerUsd ? ` = ${formatVnd(vndPerUsd)}` : ""} — Hoàn 100% credits nếu liên hệ không hợp
					lệ.
				</p>
				<p className="text-xs mt-1">
					<Link
						href={`/dashboard/${workspaceId}/buy-more`}
						className="text-emerald-600 dark:text-emerald-400 hover:underline inline-flex items-center gap-1"
					>
						<CreditCard className="size-3" aria-hidden="true" />
						Thanh toán bằng thẻ quốc tế (Stripe)
					</Link>
				</p>
			</div>

			{/* Balance Card */}
			<div className="rounded-lg border bg-muted/20 p-3">
				<div className="flex items-center justify-between text-sm">
					<span className="text-muted-foreground">Số dư hiện tại</span>
					<span className="font-semibold tabular-nums text-emerald-600 dark:text-emerald-400">
						{(balanceMicros / 10_000).toLocaleString("vi-VN")} Credits
					</span>
				</div>
			</div>

			{/* Tier Cards */}
			{tiersLoading ? (
				<div className="flex justify-center py-8">
					<Spinner size="md" />
				</div>
			) : tiersError || !tiersData?.tiers?.length ? (
				<div className="rounded-xl border border-dashed bg-muted/20 p-6 text-center text-sm text-muted-foreground">
					Không tải được bảng giá. Vui lòng thử lại sau.
				</div>
			) : (
				<div className="grid grid-cols-1 md:grid-cols-3 gap-3">
					{tiersData?.tiers.map((tier: PricingTier) => (
						<div
							key={tier.id}
							className={cn(
								"relative rounded-xl border p-4 flex flex-col gap-3 transition-shadow",
								tier.highlighted
									? "border-emerald-500/50 shadow-md shadow-emerald-500/10 bg-emerald-500/5"
									: "bg-muted/20"
							)}
						>
							{tier.highlighted && (
								<span className="absolute -top-2.5 left-1/2 -translate-x-1/2 inline-flex items-center gap-1 rounded-full bg-emerald-500 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white">
									<Crown className="size-3" aria-hidden="true" />
									Phổ biến nhất
								</span>
							)}
							<div>
								<h3 className="font-semibold">{tier.name}</h3>
								<p className="mt-1">
									<span className="text-2xl font-bold tabular-nums">
										{formatVnd(tier.price_vnd)}
									</span>
									<span className="text-xs text-muted-foreground"> /tháng</span>
								</p>
							</div>
							<ul className="space-y-1.5 text-xs text-muted-foreground flex-1">
								{(TIER_FEATURES[tier.id] ?? []).map((feature) => (
									<li key={feature} className="flex items-center gap-1.5">
										{feature.includes("seat") ? (
											<Users className="size-3.5 text-emerald-500 shrink-0" aria-hidden="true" />
										) : (
											<BadgeCheck
												className="size-3.5 text-emerald-500 shrink-0"
												aria-hidden="true"
											/>
										)}
										{feature}
									</li>
								))}
							</ul>
							<Button
								variant={tier.highlighted ? "default" : "outline"}
								size="sm"
								disabled={intentMutation.isPending}
								onClick={() =>
									intentMutation.mutate({
										workspace_id: workspaceId,
										tier_id: tier.id,
									})
								}
								className={cn(
									"w-full",
									tier.highlighted && "bg-emerald-600 hover:bg-emerald-700 text-white"
								)}
							>
								<QrCode className="size-4 mr-1" aria-hidden="true" />
								Chọn {tier.name}
							</Button>
						</div>
					))}
				</div>
			)}

			{/* Credit Calculator */}
			<div className="rounded-xl border bg-muted/20 p-4 space-y-4">
				<div className="flex items-center gap-2">
					<Calculator className="size-4 text-emerald-500" aria-hidden="true" />
					<h3 className="text-sm font-semibold">Tính credits tuỳ ý</h3>
				</div>
				<div className="space-y-2">
					<Slider
						value={[customCredits]}
						onValueChange={([v]) => setCustomCredits(v)}
						min={MIN_CUSTOM_CREDITS}
						max={MAX_CUSTOM_CREDITS}
						step={CREDIT_STEP}
						aria-label="Số credits cần mua"
					/>
					<div className="flex items-center justify-between text-xs text-muted-foreground tabular-nums">
						<span>{MIN_CUSTOM_CREDITS.toLocaleString("vi-VN")}</span>
						<span>{MAX_CUSTOM_CREDITS.toLocaleString("vi-VN")}</span>
					</div>
				</div>
				<div className="flex flex-col sm:flex-row items-center justify-between gap-3 rounded-lg border bg-background px-3 py-2">
					<div className="text-sm tabular-nums">
						<span className="font-bold">{customCredits.toLocaleString("vi-VN")} Credits</span>
						<span className="text-muted-foreground"> = </span>
						<span className="font-bold text-emerald-600 dark:text-emerald-400">
							{vndPerUsd ? formatVnd(customAmountVnd(customCredits, vndPerUsd)) : "—"}
						</span>
					</div>
					<Button
						size="sm"
						variant="outline"
						disabled={intentMutation.isPending || vndPerUsd === null}
						onClick={() => {
							if (vndPerUsd === null) return;
							intentMutation.mutate({
								workspace_id: workspaceId,
								amount_vnd: customAmountVnd(customCredits, vndPerUsd),
							});
						}}
					>
						{intentMutation.isPending ? (
							<Spinner size="xs" />
						) : (
							<QrCode className="size-4 mr-1" aria-hidden="true" />
						)}
						Nạp qua VietQR
					</Button>
				</div>
			</div>

			<VietQRCheckoutModal
				intent={activeIntent}
				open={modalOpen}
				onOpenChange={setModalOpen}
				onCompleted={handleCompleted}
			/>
		</div>
	);
}

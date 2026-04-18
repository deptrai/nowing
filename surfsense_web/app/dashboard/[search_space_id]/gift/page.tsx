"use client";

import { useAtomValue } from "jotai";
import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { stripeApiService } from "@/lib/apis/stripe-api.service";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import type { GiftPlanId } from "@/contracts/types/stripe.types";

type GiftTier = {
	id: GiftPlanId;
	name: string;
	tagline: string;
	pricing: Record<number, { price: number; label: string; savings?: string }>;
};

// Pricing aligned with subscription plans in pricing-section.tsx:
// Pro: $12/mo monthly, $96/yr annual (save $48/yr)
// Max: $100/mo monthly, $960/yr annual (save $240/yr)
const GIFT_TIERS: GiftTier[] = [
	{
		id: "pro_monthly",
		name: "Pro",
		tagline: "$12/tháng — dành cho cá nhân",
		pricing: {
			1: { price: 12, label: "1 tháng" },
			3: { price: 36, label: "3 tháng" },
			6: { price: 72, label: "6 tháng" },
			12: { price: 96, label: "12 tháng", savings: "Tiết kiệm $48" },
		},
	},
	{
		id: "max_monthly",
		name: "Max",
		tagline: "$100/tháng — cho team & power users",
		pricing: {
			1: { price: 100, label: "1 tháng" },
			3: { price: 300, label: "3 tháng" },
			6: { price: 600, label: "6 tháng" },
			12: { price: 960, label: "12 tháng", savings: "Tiết kiệm $240" },
		},
	},
];

export default function GiftPage() {
	const userQuery = useAtomValue(currentUserAtom);
	const currentUser = userQuery.data;
	const [selectedTierId, setSelectedTierId] = useState<GiftPlanId>("pro_monthly");
	const [selectedDuration, setSelectedDuration] = useState<1 | 3 | 6 | 12>(1);
	const [isLoading, setIsLoading] = useState(false);

	const selectedTier = GIFT_TIERS.find((t) => t.id === selectedTierId) ?? GIFT_TIERS[0];
	const selectedPricing = selectedTier.pricing[selectedDuration];

	const handlePurchaseGift = async () => {
		setIsLoading(true);
		try {
			const res = await stripeApiService.createGiftCheckout(selectedTierId, selectedDuration);
			if (res.admin_approval_mode) {
				try {
					await stripeApiService.requestGift(selectedTierId, selectedDuration);
					toast.success(
						"🎁 Yêu cầu gift đã được ghi nhận! Admin sẽ xử lý và bạn nhận được gift code qua trang Settings → Subscription."
					);
				} catch (err) {
					const msg = err instanceof Error ? err.message : "";
					if (msg.includes("409") || msg.toLowerCase().includes("đang chờ")) {
						toast.info("Bạn đã có yêu cầu đang chờ xử lý cho gói này.");
					} else {
						toast.error("Không thể tạo yêu cầu gift. Vui lòng thử lại sau.");
					}
				}
				return;
			}
			if (!res.checkout_url) {
				toast.error("Stripe checkout URL is missing. Please try again or contact support.");
				return;
			}
			window.location.href = res.checkout_url;
		} catch {
			toast.error("Failed to create gift checkout. Please try again.");
		} finally {
			setIsLoading(false);
		}
	};

	return (
		<div className="container max-w-2xl mx-auto py-8 px-4">
			<div className="mb-8">
				<h1 className="text-2xl font-bold text-zinc-100">🎁 Mua Gift Subscription</h1>
				<p className="text-zinc-400 mt-2">
					Tặng gói PRO hoặc MAX cho bạn bè / đồng nghiệp. Họ sẽ nhận được gift code để kích hoạt
					subscription.
				</p>
			</div>

			{/* Tier Selector */}
			<Card className="mb-6 bg-zinc-900 border-zinc-800">
				<CardHeader>
					<CardTitle className="text-zinc-100 text-lg">Chọn gói</CardTitle>
					<CardDescription>Chọn tier muốn tặng (Pro hoặc Max)</CardDescription>
				</CardHeader>
				<CardContent>
					<div className="grid grid-cols-2 gap-3">
						{GIFT_TIERS.map((tier) => {
							const isSelected = selectedTierId === tier.id;
							return (
								<button
									key={tier.id}
									type="button"
									onClick={() => setSelectedTierId(tier.id)}
									className={`p-4 rounded-lg border-2 text-left transition-colors ${
										isSelected
											? "border-indigo-500 bg-indigo-950"
											: "border-zinc-700 bg-zinc-800 hover:border-zinc-600"
									}`}
								>
									<div className="font-semibold text-zinc-100">{tier.name}</div>
									<div className="text-zinc-400 text-xs mt-1">{tier.tagline}</div>
								</button>
							);
						})}
					</div>
				</CardContent>
			</Card>

			{/* Duration Selector */}
			<Card className="mb-6 bg-zinc-900 border-zinc-800">
				<CardHeader>
					<CardTitle className="text-zinc-100 text-lg">Chọn thời hạn</CardTitle>
					<CardDescription>
						Gói 12 tháng được hưởng giá annual — tiết kiệm so với mua từng tháng
					</CardDescription>
				</CardHeader>
				<CardContent>
					<div className="grid grid-cols-2 gap-3">
						{([1, 3, 6, 12] as const).map((duration) => {
							const info = selectedTier.pricing[duration];
							const isSelected = selectedDuration === duration;
							return (
								<button
									key={duration}
									type="button"
									onClick={() => setSelectedDuration(duration)}
									className={`relative p-4 rounded-lg border-2 text-left transition-colors ${
										isSelected
											? "border-indigo-500 bg-indigo-950"
											: "border-zinc-700 bg-zinc-800 hover:border-zinc-600"
									}`}
								>
									<div className="font-semibold text-zinc-100">{info.label}</div>
									<div className="text-zinc-400 text-sm mt-1">${info.price}</div>
									{info.savings && (
										<Badge
											variant="secondary"
											className="absolute top-2 right-2 text-xs bg-indigo-900 text-indigo-300"
										>
											{info.savings}
										</Badge>
									)}
								</button>
							);
						})}
					</div>
				</CardContent>
			</Card>

			{/* How it works */}
			<Card className="mb-6 bg-zinc-900 border-zinc-800">
				<CardHeader>
					<CardTitle className="text-zinc-100 text-base">Cách thức hoạt động</CardTitle>
				</CardHeader>
				<CardContent className="text-zinc-400 text-sm space-y-2">
					<p>1. Thanh toán qua Stripe Checkout</p>
					<p>2. Nhận gift code qua trang Settings → Subscription</p>
					<p>
						3. Gửi code cho người nhận — họ truy cập{" "}
						<code className="text-indigo-400">/redeem</code> để kích hoạt
					</p>
				</CardContent>
			</Card>

			{/* Purchase Button */}
			<div className="flex flex-col gap-2">
				<Button
					onClick={handlePurchaseGift}
					disabled={isLoading}
					className="w-full bg-indigo-600 hover:bg-indigo-700 text-white"
					size="lg"
				>
					{isLoading
						? "Đang xử lý..."
						: `Mua Gift ${selectedTier.name} ${selectedPricing.label} — $${selectedPricing.price}`}
				</Button>
				{currentUser && (
					<p className="text-xs text-zinc-500 text-center">
						Thanh toán với tài khoản: {currentUser.email}
					</p>
				)}
			</div>
		</div>
	);
}

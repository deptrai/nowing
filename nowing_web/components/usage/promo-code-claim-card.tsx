"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Gift, Loader2, Sparkles } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { promoCodeApiService } from "@/lib/apis/promo-code-api.service";

export function cleanPromoCode(code: string): string {
	return code.trim().toUpperCase();
}

export function validatePromoCodeFormat(code: string): boolean {
	const cleaned = cleanPromoCode(code);
	return cleaned.length >= 3 && /^[A-Z0-9_-]+$/.test(cleaned);
}

export function formatCreditDisplay(micros: number): string {
	const credits = micros / 40_000;
	const vnd = (credits * 1_000).toLocaleString("vi-VN");
	const usd = (micros / 1_000_000).toFixed(2);
	return `${credits.toLocaleString()} Credits (${vnd}đ / $${usd})`;
}

export function PromoCodeClaimCard() {
	const [code, setCode] = useState("");
	const queryClient = useQueryClient();

	const claimMutation = useMutation({
		mutationFn: (promoCode: string) => promoCodeApiService.claimPromoCode(promoCode),
		onSuccess: (data) => {
			toast.success(data.message || "Nhận mã khuyến mãi thành công!", {
				description: `Đã cộng ${formatCreditDisplay(data.credit_micros_granted)} vào ví của bạn.`,
			});
			setCode("");
			queryClient.invalidateQueries({ queryKey: ["usage"] });
		},
		onError: (err: unknown) => {
			const errorObj = err as {
				response?: { data?: { detail?: { message?: string } | string } };
				message?: string;
			};
			const detail = errorObj?.response?.data?.detail;
			const message =
				(typeof detail === "object" ? detail?.message : detail) ||
				errorObj?.message ||
				"Không thể sử dụng mã khuyến mãi này. Vui lòng kiểm tra lại.";
			toast.error("Không thể nhận khuyến mãi", {
				description: message,
			});
		},
	});

	const handleSubmit = (e: React.FormEvent) => {
		e.preventDefault();
		const cleaned = cleanPromoCode(code);
		if (!validatePromoCodeFormat(cleaned)) {
			toast.error("Mã không hợp lệ", {
				description: "Mã khuyến mãi phải có ít nhất 3 ký tự (chữ hoa, số, gạch ngang).",
			});
			return;
		}
		claimMutation.mutate(cleaned);
	};

	return (
		<Card className="border-primary/20 bg-gradient-to-br from-card to-primary/5">
			<CardHeader className="pb-3">
				<div className="flex items-center gap-2">
					<div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
						<Gift className="h-4 w-4" />
					</div>
					<div>
						<CardTitle className="text-base font-semibold">Nhận mã quà tặng / Voucher</CardTitle>
						<CardDescription className="text-xs">
							Nhập mã ưu đãi hoặc gift card để nạp credit vào ví tức thì.
						</CardDescription>
					</div>
				</div>
			</CardHeader>
			<CardContent>
				<form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-2">
					<div className="relative flex-1">
						<Input
							id="promo-code-input"
							value={code}
							onChange={(e) => setCode(e.target.value.toUpperCase())}
							placeholder="VD: WELCOME50, VIP2026"
							className="font-mono uppercase placeholder:normal-case"
							disabled={claimMutation.isPending}
						/>
					</div>
					<Button
						type="submit"
						id="claim-promo-code-button"
						disabled={claimMutation.isPending || !code.trim()}
						className="gap-2 shrink-0"
					>
						{claimMutation.isPending ? (
							<Loader2 className="h-4 w-4 animate-spin" />
						) : (
							<Sparkles className="h-4 w-4" />
						)}
						Áp dụng
					</Button>
				</form>
				<p className="mt-2 text-[11px] text-muted-foreground">
					💡 Quy đổi: 1 Credit = 1.000đ = $0.04 (40.000 micros). Chat & Prompt = 0đ ($0).
				</p>
			</CardContent>
		</Card>
	);
}

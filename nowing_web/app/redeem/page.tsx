"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardFooter,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { stripeApiService } from "@/lib/apis/stripe-api.service";
import { getBearerToken } from "@/lib/auth-utils";
import { AppError } from "@/lib/error";
import { USER_QUERY_KEY } from "@/atoms/user/user-query.atoms";
import type { RedeemGiftResponse } from "@/contracts/types/stripe.types";

function LoadingSpinner() {
	return (
		<div className="min-h-screen flex items-center justify-center bg-zinc-950">
			<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500" />
		</div>
	);
}

function UnauthenticatedView() {
	return (
		<div className="min-h-screen flex items-center justify-center bg-zinc-950 px-4">
			<Card className="w-full max-w-md bg-zinc-900 border-zinc-800">
				<CardHeader>
					<CardTitle className="text-zinc-100">🎁 Kích hoạt Gift Code</CardTitle>
					<CardDescription>Đăng nhập để sử dụng gift code</CardDescription>
				</CardHeader>
				<CardContent>
					<p className="text-zinc-400 text-sm mb-4">
						Bạn cần đăng nhập để kích hoạt gift subscription.
					</p>
					<Button asChild className="w-full bg-indigo-600 hover:bg-indigo-700 text-white">
						<Link href="/auth?redirect=/redeem">Đăng nhập</Link>
					</Button>
				</CardContent>
			</Card>
		</div>
	);
}

function AuthenticatedRedeemForm() {
	const queryClient = useQueryClient();
	const [code, setCode] = useState("");
	const [isLoading, setIsLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [successData, setSuccessData] = useState<RedeemGiftResponse | null>(null);

	const handleRedeem = async () => {
		if (!code.trim() || isLoading) return;
		setIsLoading(true);
		setError(null);
		try {
			const res = await stripeApiService.redeemGiftCode(code.trim().toUpperCase());
			await queryClient.invalidateQueries({ queryKey: USER_QUERY_KEY });
			setSuccessData(res);
		} catch (err: unknown) {
			const msg =
				err instanceof AppError
					? err.message
					: err instanceof Error
						? err.message
						: "Có lỗi xảy ra. Vui lòng thử lại.";
			setError(msg);
		} finally {
			setIsLoading(false);
		}
	};

	if (successData) {
		const expiryParsed = new Date(successData.new_expiry);
		const expiryDate = Number.isNaN(expiryParsed.getTime())
			? successData.new_expiry
			: expiryParsed.toLocaleDateString("vi-VN", {
					year: "numeric",
					month: "long",
					day: "numeric",
				});
		return (
			<div className="min-h-screen flex items-center justify-center bg-zinc-950 px-4">
				<Card className="w-full max-w-md bg-zinc-900 border-zinc-800">
					<CardHeader>
						<CardTitle className="text-zinc-100">🎉 Đã kích hoạt thành công!</CardTitle>
					</CardHeader>
					<CardContent>
						<p className="text-zinc-300">
							Subscription đã được gia hạn đến{" "}
							<strong className="text-zinc-100">{expiryDate}</strong>
						</p>
					</CardContent>
					<CardFooter>
						<Button asChild className="w-full bg-indigo-600 hover:bg-indigo-700 text-white">
							<Link href="/dashboard">Vào Dashboard</Link>
						</Button>
					</CardFooter>
				</Card>
			</div>
		);
	}

	return (
		<div className="min-h-screen flex items-center justify-center bg-zinc-950 px-4">
			<Card className="w-full max-w-md bg-zinc-900 border-zinc-800">
				<CardHeader>
					<CardTitle className="text-zinc-100">🎁 Kích hoạt Gift Code</CardTitle>
					<CardDescription>
						Nhập gift code bạn nhận được để kích hoạt subscription PRO
					</CardDescription>
				</CardHeader>
				<CardContent className="space-y-3">
					<Input
						value={code}
						onChange={(e) => {
							setCode(e.target.value);
							setError(null);
						}}
						placeholder="GIFT-XXXX-XXXX-XXXX"
						className={`bg-zinc-800 border-zinc-700 text-zinc-100 placeholder:text-zinc-500 ${
							error ? "border-red-500" : ""
						}`}
						disabled={isLoading}
					/>
					{error && <p className="text-sm text-red-500">{error}</p>}
					<Button
						onClick={handleRedeem}
						disabled={isLoading || !code.trim()}
						className="w-full bg-indigo-600 hover:bg-indigo-700 text-white"
					>
						{isLoading ? "Đang xử lý..." : "Kích hoạt"}
					</Button>
				</CardContent>
			</Card>
		</div>
	);
}

export default function RedeemPage() {
	const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);

	useEffect(() => {
		setIsAuthenticated(!!getBearerToken());
	}, []);

	if (isAuthenticated === null) return <LoadingSpinner />;
	if (!isAuthenticated) return <UnauthenticatedView />;
	return <AuthenticatedRedeemForm />;
}

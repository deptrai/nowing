"use client";

import {
	IconAffiliate,
	IconBuildingBank,
	IconCheck,
	IconCoins,
	IconCopy,
	IconDownload,
	IconLoader2,
	IconQrcode,
	IconRefresh,
	IconWallet,
} from "@tabler/icons-react";
import Image from "next/image";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type {
	PartnerCommissionItem,
	PartnerPayoutItem,
	PartnerProfileResponse,
	PartnerReferralItem,
	VietQrBankItem,
} from "@/contracts/types/partners.types";
import { partnersApiService } from "@/lib/apis/partners-api.service";
import { PayoutHistoryTable } from "./components/PayoutHistoryTable";

export default function PartnerDashboardPage() {
	const [isLoading, setIsLoading] = useState(true);
	const [profile, setProfile] = useState<PartnerProfileResponse | null>(null);
	const [banks, setBanks] = useState<VietQrBankItem[]>([]);
	const [commissions, setCommissions] = useState<PartnerCommissionItem[]>([]);
	const [referrals, setReferrals] = useState<PartnerReferralItem[]>([]);
	const [payouts, setPayouts] = useState<PartnerPayoutItem[]>([]);
	const [copied, setCopied] = useState(false);

	// Onboarding state for non-partners
	const [claimCode, setClaimCode] = useState("");
	const [partnerType, setPartnerType] = useState("agency");
	const [selectedBank, setSelectedBank] = useState("970436");
	const [accountNumber, setAccountNumber] = useState("");
	const [accountName, setAccountName] = useState("");
	const [isSubmittingApply, setIsSubmittingApply] = useState(false);

	// Payout modal state
	const [isPayoutOpen, setIsPayoutOpen] = useState(false);
	const [payoutMethod, setPayoutMethod] = useState<"vietqr" | "credit_wallet">("vietqr");
	const [payoutAmountUsd, setPayoutAmountUsd] = useState("20");
	const [isSubmittingPayout, setIsSubmittingPayout] = useState(false);

	const loadDashboard = useCallback(async () => {
		setIsLoading(true);
		try {
			// Fetch banks
			try {
				const bankList = await partnersApiService.getSupportedBanks();
				setBanks(bankList);
			} catch {
				// Non-fatal
			}

			// Fetch profile
			const p = await partnersApiService.getProfile();
			setProfile(p);

			// Fetch lists in parallel
			const [commsRes, refsRes, paysRes] = await Promise.all([
				partnersApiService.getCommissions(50, 0),
				partnersApiService.getReferrals(50, 0),
				partnersApiService.getPayouts(50, 0),
			]);
			setCommissions(commsRes.commissions || []);
			setReferrals(refsRes.referrals || []);
			setPayouts(paysRes.payouts || []);
		} catch (err: unknown) {
			const errorObj = err as { status?: number; message?: string };
			if (errorObj?.status !== 404) {
				toast.error(errorObj?.message || "Failed to load partner dashboard");
			}
			setProfile(null);
		} finally {
			setIsLoading(false);
		}
	}, []);

	useEffect(() => {
		loadDashboard();
	}, [loadDashboard]);

	const handleApply = async (e: React.FormEvent) => {
		e.preventDefault();
		if (!claimCode.trim()) {
			toast.error("Please enter a referral code");
			return;
		}
		setIsSubmittingApply(true);
		try {
			const bankObj = banks.find((b) => b.bin === selectedBank);
			const newProfile = await partnersApiService.apply({
				referral_code: claimCode.trim().toUpperCase(),
				partner_type: partnerType,
				payout_method: "vietqr",
				payout_details: {
					bank_bin: selectedBank,
					bank_name: bankObj?.name || "Vietcombank",
					bank_short_name: bankObj?.short_name || "VCB",
					account_number: accountNumber.trim(),
					account_holder: accountName.trim().toUpperCase(),
				},
			});
			toast.success("Welcome to the Nowing Partner Program!");
			setProfile(newProfile);
			loadDashboard();
		} catch (err: unknown) {
			const errorObj = err as { message?: string };
			toast.error(errorObj?.message || "Failed to create partner profile");
		} finally {
			setIsSubmittingApply(false);
		}
	};

	const handleCopyLink = () => {
		if (!profile?.referral_url) return;
		navigator.clipboard.writeText(profile.referral_url);
		setCopied(true);
		toast.success("Referral link copied to clipboard!");
		setTimeout(() => setCopied(false), 2000);
	};

	const handleRequestPayout = async (e: React.FormEvent) => {
		e.preventDefault();
		const amount = parseFloat(payoutAmountUsd);
		if (Number.isNaN(amount) || amount < 20) {
			toast.error("Minimum payout is $20.00");
			return;
		}
		const amountMicros = Math.round(amount * 1_000_000);
		if (profile && profile.balance_micros < amountMicros) {
			toast.error("Insufficient balance");
			return;
		}

		setIsSubmittingPayout(true);
		try {
			await partnersApiService.requestPayout({
				amount_micros: amountMicros,
				payout_method: payoutMethod,
				payout_details: profile?.payout_details,
			});
			toast.success(
				payoutMethod === "credit_wallet"
					? "Credits with +10% bonus added to your wallet!"
					: "Payout request submitted! Transfer will be processed via VietQR Napas 24/7."
			);
			setIsPayoutOpen(false);
			loadDashboard();
		} catch (err: unknown) {
			const errorObj = err as { message?: string };
			toast.error(errorObj?.message || "Failed to request payout");
		} finally {
			setIsSubmittingPayout(false);
		}
	};

	if (isLoading) {
		return (
			<div className="min-h-[60vh] flex flex-col items-center justify-center gap-3">
				<IconLoader2 className="size-8 animate-spin text-emerald-600" />
				<p className="text-sm text-neutral-500">Loading your partner portal...</p>
			</div>
		);
	}

	// If user is not yet a partner, display Onboarding Form
	if (!profile) {
		return (
			<div className="max-w-2xl mx-auto px-4 py-16">
				<div className="rounded-3xl border border-emerald-200 dark:border-emerald-800 bg-white dark:bg-neutral-900 p-8 md:p-10 shadow-xl">
					<div className="text-center mb-8">
						<div className="size-12 rounded-2xl bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800 flex items-center justify-center mx-auto mb-4">
							<IconAffiliate className="size-6" />
						</div>
						<h1 className="font-serif text-2xl md:text-3xl font-normal text-neutral-900 dark:text-white">
							Join the Nowing Partner Program
						</h1>
						<p className="text-sm text-neutral-600 dark:text-neutral-400 mt-2">
							Claim your unique code to earn 15% lifetime recurring commissions with instant VietQR
							Napas 24/7 payouts.
						</p>
					</div>

					<form onSubmit={handleApply} className="space-y-5">
						<div className="space-y-2">
							<Label htmlFor="refCode">Choose Custom Referral Code</Label>
							<div className="relative">
								<Input
									id="refCode"
									placeholder="e.g. AGENCY2026 or YOURNAME"
									value={claimCode}
									onChange={(e) =>
										setClaimCode(e.target.value.toUpperCase().replace(/[^A-Z0-9_-]/g, ""))
									}
									maxLength={32}
									className="font-mono font-bold uppercase tracking-wider text-base"
									required
								/>
							</div>
							<p className="text-xs text-neutral-500">
								Your link will be: https://nowing.net/?ref={claimCode || "CODE"}
							</p>
						</div>

						<div className="space-y-2">
							<Label htmlFor="partnerType">Partner Category</Label>
							<Select value={partnerType} onValueChange={setPartnerType}>
								<SelectTrigger>
									<SelectValue placeholder="Select type" />
								</SelectTrigger>
								<SelectContent>
									<SelectItem value="agency">Marketing & Growth Agency</SelectItem>
									<SelectItem value="b2b_sales">B2B Sales & Outreach Consultant</SelectItem>
									<SelectItem value="real_estate">Real Estate & Broker Network</SelectItem>
									<SelectItem value="creator">Creator / Educator / Tech Blogger</SelectItem>
									<SelectItem value="other">Individual Affiliate</SelectItem>
								</SelectContent>
							</Select>
						</div>

						<div className="pt-4 border-t border-neutral-100 dark:border-neutral-800 space-y-4">
							<h3 className="font-semibold text-sm text-neutral-800 dark:text-neutral-200">
								Default VietQR Bank Details (Napas 24/7)
							</h3>

							<div className="space-y-2">
								<Label htmlFor="bank">Receiving Bank</Label>
								<Select value={selectedBank} onValueChange={setSelectedBank}>
									<SelectTrigger>
										<SelectValue placeholder="Select Bank" />
									</SelectTrigger>
									<SelectContent className="max-h-60">
										{banks.map((b) => (
											<SelectItem key={b.bin} value={b.bin}>
												{b.short_name} - {b.name}
											</SelectItem>
										))}
									</SelectContent>
								</Select>
							</div>

							<div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
								<div className="space-y-2">
									<Label htmlFor="accNo">Bank Account Number</Label>
									<Input
										id="accNo"
										placeholder="e.g. 1903333333"
										value={accountNumber}
										onChange={(e) => setAccountNumber(e.target.value)}
										className="font-mono"
									/>
								</div>
								<div className="space-y-2">
									<Label htmlFor="accName">Account Holder Name</Label>
									<Input
										id="accName"
										placeholder="NGUYEN VAN A"
										value={accountName}
										onChange={(e) => setAccountName(e.target.value.toUpperCase())}
									/>
								</div>
							</div>
						</div>

						<Button
							type="submit"
							disabled={isSubmittingApply}
							className="w-full bg-emerald-500 hover:bg-emerald-600 text-neutral-950 font-bold py-6 rounded-xl mt-6 shadow-lg shadow-emerald-500/20"
						>
							{isSubmittingApply ? (
								<IconLoader2 className="size-5 animate-spin" />
							) : (
								"Create Partner Profile & Get Link"
							)}
						</Button>
					</form>
				</div>
			</div>
		);
	}

	const qrCodeUrl = `https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=${encodeURIComponent(
		profile.referral_url
	)}`;

	return (
		<div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
			{/* Top Header */}
			<div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-neutral-200 dark:border-neutral-800 pb-6">
				<div>
					<div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 text-xs font-semibold uppercase tracking-wider mb-2">
						<IconAffiliate className="size-3.5" />
						<span>Affiliate Partner Dashboard</span>
					</div>
					<h1 className="font-serif text-2xl sm:text-3xl font-normal text-neutral-900 dark:text-white">
						Partner Portal
					</h1>
					<p className="text-sm text-neutral-600 dark:text-neutral-400 mt-1">
						Referral Code:{" "}
						<span className="font-mono font-bold text-emerald-600">{profile.referral_code}</span> •
						Rate:{" "}
						<span className="font-semibold text-neutral-800 dark:text-neutral-200">
							15% Lifetime Recurring
						</span>
					</p>
				</div>

				<div className="flex items-center gap-3">
					<Button
						variant="outline"
						size="sm"
						onClick={loadDashboard}
						className="flex items-center gap-1.5 text-xs"
					>
						<IconRefresh className="size-3.5" />
						<span>Refresh Data</span>
					</Button>
					<Button
						onClick={() => setIsPayoutOpen(true)}
						className="bg-emerald-500 hover:bg-emerald-600 text-neutral-950 font-bold text-xs md:text-sm px-4 py-2 rounded-xl flex items-center gap-1.5 shadow-md shadow-emerald-500/20"
					>
						<IconWallet className="size-4" />
						<span>Request Payout</span>
					</Button>
				</div>
			</div>

			{/* Referral Link & QR Card */}
			<div className="rounded-3xl border border-emerald-200/80 dark:border-emerald-800/60 bg-gradient-to-r from-emerald-50/40 via-white to-white dark:from-emerald-950/20 dark:via-neutral-900 dark:to-neutral-900 p-6 md:p-8 shadow-xs">
				<div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
					<div className="space-y-3 max-w-2xl">
						<h2 className="text-xl font-bold text-neutral-900 dark:text-white flex items-center gap-2">
							<IconQrcode className="size-5 text-emerald-600" />
							<span>Your Unique Referral Link</span>
						</h2>
						<p className="text-sm text-neutral-600 dark:text-neutral-400">
							Share this link with your audience. Any user who registers within 30 days of clicking
							is bound to your account permanently.
						</p>

						<div className="flex items-center gap-2">
							<div className="flex-1 bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 px-4 py-2.5 rounded-xl font-mono text-sm text-neutral-800 dark:text-neutral-200 truncate select-all">
								{profile.referral_url}
							</div>
							<Button
								onClick={handleCopyLink}
								className="bg-neutral-900 hover:bg-neutral-800 dark:bg-emerald-500 dark:hover:bg-emerald-600 dark:text-neutral-950 text-white font-semibold rounded-xl shrink-0 flex items-center gap-1.5"
							>
								{copied ? <IconCheck className="size-4" /> : <IconCopy className="size-4" />}
								<span>{copied ? "Copied" : "Copy Link"}</span>
							</Button>
						</div>
					</div>

					{/* QR Code Preview */}
					<div className="flex items-center gap-4 bg-white dark:bg-neutral-800/80 p-3 rounded-2xl border border-neutral-200 dark:border-neutral-700 shadow-2xs shrink-0 self-start lg:self-auto">
						<Image
							src={qrCodeUrl}
							alt="Partner QR Code"
							width={96}
							height={96}
							unoptimized
							className="size-24 rounded-lg bg-white p-1"
						/>
						<div className="text-xs space-y-1">
							<div className="font-bold text-neutral-800 dark:text-neutral-200">Scan QR Code</div>
							<div className="text-neutral-500">Scan on phone to test</div>
							<a
								href={qrCodeUrl}
								target="_blank"
								rel="noreferrer"
								className="inline-flex items-center gap-1 text-emerald-600 hover:underline font-medium"
							>
								<IconDownload className="size-3" />
								<span>Download QR</span>
							</a>
						</div>
					</div>
				</div>
			</div>

			{/* KPI Cards Grid */}
			<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
				{/* Card 1: Available Balance */}
				<div className="p-6 rounded-3xl border border-neutral-200/80 dark:border-neutral-800 bg-white dark:bg-neutral-900 shadow-xs relative overflow-hidden">
					<div className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-2">
						Available Balance
					</div>
					<div className="text-3xl font-black font-mono text-emerald-600 dark:text-emerald-400">
						${profile.balance_usd.toFixed(2)}
					</div>
					<div className="text-xs font-bold text-neutral-600 dark:text-neutral-400 mt-1 font-mono">
						≈ {profile.balance_vnd.toLocaleString("vi-VN")} VND
					</div>
				</div>

				{/* Card 2: Total Lifetime Earned */}
				<div className="p-6 rounded-3xl border border-neutral-200/80 dark:border-neutral-800 bg-white dark:bg-neutral-900 shadow-xs">
					<div className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-2">
						Total Lifetime Earned
					</div>
					<div className="text-3xl font-black font-mono text-neutral-900 dark:text-white">
						${profile.total_earned_usd.toFixed(2)}
					</div>
					<div className="text-xs font-mono text-neutral-500 mt-1">
						≈ {profile.total_earned_vnd.toLocaleString("vi-VN")} VND
					</div>
				</div>

				{/* Card 3: Total Referrals */}
				<div className="p-6 rounded-3xl border border-neutral-200/80 dark:border-neutral-800 bg-white dark:bg-neutral-900 shadow-xs">
					<div className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-2">
						Referred Customers
					</div>
					<div className="text-3xl font-black font-mono text-neutral-900 dark:text-white">
						{profile.total_referrals}
					</div>
					<div className="text-xs text-neutral-500 mt-1">
						{profile.total_clicks} estimated link clicks
					</div>
				</div>

				{/* Card 4: Active Paying Referrals */}
				<div className="p-6 rounded-3xl border border-neutral-200/80 dark:border-neutral-800 bg-white dark:bg-neutral-900 shadow-xs">
					<div className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-2">
						Active Paying Clients Paying Customers
					</div>
					<div className="text-3xl font-black font-mono text-neutral-900 dark:text-white">
						{profile.active_paying_referrals}
					</div>
					<div className="text-xs text-neutral-500 mt-1">15% lifetime recurring split</div>
				</div>
			</div>

			{/* Tabs Section */}
			<Tabs defaultValue="commissions" className="space-y-6">
				<TabsList className="bg-neutral-100 dark:bg-neutral-800/60 p-1 rounded-2xl">
					<TabsTrigger value="commissions" className="rounded-xl text-xs md:text-sm font-semibold">
						Commissions ({commissions.length})
					</TabsTrigger>
					<TabsTrigger value="referrals" className="rounded-xl text-xs md:text-sm font-semibold">
						Referred Accounts ({referrals.length})
					</TabsTrigger>
					<TabsTrigger value="payouts" className="rounded-xl text-xs md:text-sm font-semibold">
						Payout History ({payouts.length})
					</TabsTrigger>
				</TabsList>

				{/* Tab 1: Commissions Ledger */}
				<TabsContent value="commissions" className="space-y-4">
					<div className="rounded-2xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 overflow-hidden shadow-xs">
						<div className="p-5 border-b border-neutral-100 dark:border-neutral-800 flex justify-between items-center">
							<h3 className="font-bold text-neutral-900 dark:text-white text-base">
								Commission Ledger
							</h3>
							<span className="text-xs text-neutral-500 font-mono">15% Recurring Split</span>
						</div>

						{commissions.length === 0 ? (
							<div className="p-12 text-center text-neutral-500 text-sm">
								No commissions earned yet. Share your referral link to get started!
							</div>
						) : (
							<div className="overflow-x-auto">
								<table className="w-full text-left text-sm">
									<thead className="bg-neutral-50 dark:bg-neutral-800/50 text-xs text-neutral-500 uppercase font-semibold">
										<tr>
											<th className="px-6 py-3.5">Date</th>
											<th className="px-6 py-3.5">Customer Purchase</th>
											<th className="px-6 py-3.5">Your Cut (15%)</th>
											<th className="px-6 py-3.5">Amount (VND)</th>
											<th className="px-6 py-3.5">Status</th>
										</tr>
									</thead>
									<tbody className="divide-y divide-neutral-100 dark:divide-neutral-800">
										{commissions.map((comm) => (
											<tr
												key={comm.id}
												className="hover:bg-neutral-50/50 dark:hover:bg-neutral-800/30"
											>
												<td className="px-6 py-4 text-xs font-mono text-neutral-600 dark:text-neutral-400">
													{new Date(comm.created_at).toLocaleDateString()}
												</td>
												<td className="px-6 py-4 font-mono font-medium">
													${comm.source_amount_usd.toFixed(2)}
												</td>
												<td className="px-6 py-4 font-mono font-bold text-emerald-600">
													+${comm.commission_usd.toFixed(2)}
												</td>
												<td className="px-6 py-4 font-mono text-xs text-neutral-500">
													{comm.commission_vnd.toLocaleString("vi-VN")} VND
												</td>
												<td className="px-6 py-4">
													<span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300">
														{comm.status}
													</span>
												</td>
											</tr>
										))}
									</tbody>
								</table>
							</div>
						)}
					</div>
				</TabsContent>

				{/* Tab 2: Referred Users */}
				<TabsContent value="referrals" className="space-y-4">
					<div className="rounded-2xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 overflow-hidden shadow-xs">
						<div className="p-5 border-b border-neutral-100 dark:border-neutral-800 flex justify-between items-center">
							<h3 className="font-bold text-neutral-900 dark:text-white text-base">
								Referred Accounts
							</h3>
							<span className="text-xs text-neutral-500 font-mono">
								{referrals.length} customers
							</span>
						</div>

						{referrals.length === 0 ? (
							<div className="p-12 text-center text-neutral-500 text-sm">
								No referred users registered yet.
							</div>
						) : (
							<div className="overflow-x-auto">
								<table className="w-full text-left text-sm">
									<thead className="bg-neutral-50 dark:bg-neutral-800/50 text-xs text-neutral-500 uppercase font-semibold">
										<tr>
											<th className="px-6 py-3.5">Customer Email</th>
											<th className="px-6 py-3.5">Attribution</th>
											<th className="px-6 py-3.5">Total Spent</th>
											<th className="px-6 py-3.5">Your Earnings</th>
											<th className="px-6 py-3.5">Joined Date</th>
										</tr>
									</thead>
									<tbody className="divide-y divide-neutral-100 dark:divide-neutral-800">
										{referrals.map((ref) => (
											<tr
												key={ref.id}
												className="hover:bg-neutral-50/50 dark:hover:bg-neutral-800/30"
											>
												<td className="px-6 py-4 font-mono text-xs font-semibold text-neutral-800 dark:text-neutral-200">
													{ref.masked_email}
												</td>
												<td className="px-6 py-4 text-xs text-neutral-500">
													{ref.attribution_source}
												</td>
												<td className="px-6 py-4 font-mono font-medium">
													${(ref.total_spent_micros / 1_000_000).toFixed(2)}
												</td>
												<td className="px-6 py-4 font-mono font-bold text-emerald-600">
													${(ref.total_commission_micros / 1_000_000).toFixed(2)}
												</td>
												<td className="px-6 py-4 text-xs font-mono text-neutral-500">
													{new Date(ref.created_at).toLocaleDateString()}
												</td>
											</tr>
										))}
									</tbody>
								</table>
							</div>
						)}
					</div>
				</TabsContent>

				{/* Tab 3: Payout History */}
				<TabsContent value="payouts" className="space-y-4">
					<PayoutHistoryTable payouts={payouts} onNewPayoutClick={() => setIsPayoutOpen(true)} />
				</TabsContent>
			</Tabs>

			{/* Request Payout Dialog */}
			<Dialog open={isPayoutOpen} onOpenChange={setIsPayoutOpen}>
				<DialogContent className="sm:max-w-md rounded-3xl">
					<DialogHeader>
						<DialogTitle className="text-xl font-bold">Request Commission Payout</DialogTitle>
						<DialogDescription>
							Available balance: ${profile.balance_usd.toFixed(2)} (
							{profile.balance_vnd.toLocaleString("vi-VN")} VND). Minimum withdrawal is $20.00.
						</DialogDescription>
					</DialogHeader>

					<form onSubmit={handleRequestPayout} className="space-y-4 py-2">
						<div className="space-y-2">
							<Label>Payout Method</Label>
							<div className="grid grid-cols-2 gap-3">
								<button
									type="button"
									onClick={() => setPayoutMethod("vietqr")}
									className={`p-3 rounded-2xl border text-left text-xs transition-all ${
										payoutMethod === "vietqr"
											? "border-emerald-500 bg-emerald-50/50 dark:bg-emerald-950/30 text-emerald-900 dark:text-emerald-200 font-semibold"
											: "border-neutral-200 dark:border-neutral-800 text-neutral-600 dark:text-neutral-400"
									}`}
								>
									<IconBuildingBank className="size-4 mb-1 text-emerald-600" />
									<div className="font-bold">VietQR Napas 24/7</div>
									<div className="text-[10px] text-neutral-500">Direct to bank (0% fee)</div>
								</button>

								<button
									type="button"
									onClick={() => setPayoutMethod("credit_wallet")}
									className={`p-3 rounded-2xl border text-left text-xs transition-all ${
										payoutMethod === "credit_wallet"
											? "border-emerald-500 bg-emerald-50/50 dark:bg-emerald-950/30 text-emerald-900 dark:text-emerald-200 font-semibold"
											: "border-neutral-200 dark:border-neutral-800 text-neutral-600 dark:text-neutral-400"
									}`}
								>
									<IconCoins className="size-4 mb-1 text-emerald-600" />
									<div className="font-bold">Platform Credits</div>
									<div className="text-[10px] text-emerald-600 font-bold">+10% Bonus added</div>
								</button>
							</div>
						</div>

						<div className="space-y-2">
							<Label htmlFor="payoutAmount">Amount (USD)</Label>
							<Input
								id="payoutAmount"
								type="number"
								min="20"
								step="1"
								value={payoutAmountUsd}
								onChange={(e) => setPayoutAmountUsd(e.target.value)}
								className="font-mono text-lg font-bold"
							/>
							<p className="text-xs text-neutral-500">
								≈ {(parseFloat(payoutAmountUsd || "0") * 25400).toLocaleString("vi-VN")} VND
								{payoutMethod === "credit_wallet" && (
									<span className="text-emerald-600 font-semibold ml-1">
										(+10% bonus = ${(parseFloat(payoutAmountUsd || "0") * 1.1).toFixed(2)} in
										platform credits)
									</span>
								)}
							</p>
						</div>

						{payoutMethod === "vietqr" && profile.payout_details && (
							<div className="p-3.5 rounded-xl bg-neutral-50 dark:bg-neutral-800/60 border border-neutral-200 dark:border-neutral-700 text-xs space-y-1">
								<div className="font-semibold text-neutral-700 dark:text-neutral-300">
									Receiving Account:
								</div>
								<div className="text-neutral-600 dark:text-neutral-400 font-mono">
									{String(
										profile.payout_details.bank_short_name ||
											profile.payout_details.bank_name ||
											"Bank"
									)}{" "}
									• {String(profile.payout_details.account_number || "")}
								</div>
								<div className="text-neutral-500 font-bold">
									{String(profile.payout_details.account_holder || "")}
								</div>
							</div>
						)}

						<DialogFooter className="mt-4">
							<Button
								type="button"
								variant="outline"
								onClick={() => setIsPayoutOpen(false)}
								className="rounded-xl"
							>
								Cancel
							</Button>
							<Button
								type="submit"
								disabled={isSubmittingPayout}
								className="bg-emerald-500 hover:bg-emerald-600 text-neutral-950 font-bold rounded-xl"
							>
								{isSubmittingPayout ? (
									<IconLoader2 className="size-4 animate-spin" />
								) : (
									"Confirm Withdrawal"
								)}
							</Button>
						</DialogFooter>
					</form>
				</DialogContent>
			</Dialog>
		</div>
	);
}

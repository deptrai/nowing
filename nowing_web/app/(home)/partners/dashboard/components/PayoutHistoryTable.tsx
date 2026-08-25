"use client";

import {
	IconAlertCircle,
	IconCheck,
	IconCopy,
	IconFileInvoice,
	IconLoader2,
	IconShieldCheck,
} from "@tabler/icons-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import type { PartnerPayoutItem } from "@/contracts/types/partners.types";

interface PayoutHistoryTableProps {
	payouts: PartnerPayoutItem[];
	onNewPayoutClick: () => void;
}

export function PayoutHistoryTable({ payouts, onNewPayoutClick }: PayoutHistoryTableProps) {
	const [selectedReceipt, setSelectedReceipt] = useState<PartnerPayoutItem | null>(null);

	const handleCopy = (text: string, label: string) => {
		navigator.clipboard.writeText(text);
		toast.success(`${label} copied to clipboard!`);
	};

	return (
		<div className="rounded-2xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 overflow-hidden shadow-xs">
			<div className="p-5 border-b border-neutral-100 dark:border-neutral-800 flex justify-between items-center">
				<div>
					<h3 className="font-bold text-neutral-900 dark:text-white text-base">
						Payout Withdrawals & VietQR Ledger
					</h3>
					<p className="text-xs text-neutral-500 mt-0.5">
						Automated 24/7 Napas settlements & PIT (TNCN) tax compliance
					</p>
				</div>
				<Button
					size="sm"
					onClick={onNewPayoutClick}
					className="bg-emerald-500 hover:bg-emerald-600 text-neutral-950 font-bold text-xs rounded-xl"
				>
					New Withdrawal
				</Button>
			</div>

			{payouts.length === 0 ? (
				<div className="p-12 text-center text-neutral-500 text-sm">
					No payout requests submitted yet.
				</div>
			) : (
				<div className="overflow-x-auto">
					<table className="w-full text-left text-sm">
						<thead className="bg-neutral-50 dark:bg-neutral-800/50 text-xs text-neutral-500 uppercase font-semibold">
							<tr>
								<th className="px-6 py-3.5">Requested Date</th>
								<th className="px-6 py-3.5">Gross Amount</th>
								<th className="px-6 py-3.5">PIT Tax (TNCN)</th>
								<th className="px-6 py-3.5">Net Received</th>
								<th className="px-6 py-3.5">Method</th>
								<th className="px-6 py-3.5">Status</th>
								<th className="px-6 py-3.5">Napas / Ref</th>
								<th className="px-6 py-3.5 text-right">Receipt</th>
							</tr>
						</thead>
						<tbody className="divide-y divide-neutral-100 dark:divide-neutral-800">
							{payouts.map((payout) => {
								const hasTax = (payout.tax_deducted_micros ?? 0) > 0;
								const netVnd = payout.net_amount_vnd ?? payout.amount_vnd;
								const netUsd = (payout.net_amount_micros ?? payout.amount_micros) / 1_000_000;

								return (
									<tr
										key={payout.id}
										className="hover:bg-neutral-50/50 dark:hover:bg-neutral-800/30 transition-colors"
									>
										<td className="px-6 py-4 text-xs font-mono text-neutral-600 dark:text-neutral-400">
											{new Date(payout.requested_at).toLocaleDateString("vi-VN", {
												year: "numeric",
												month: "2-digit",
												day: "2-digit",
												hour: "2-digit",
												minute: "2-digit",
											})}
										</td>
										<td className="px-6 py-4 font-mono font-bold text-neutral-900 dark:text-white">
											${payout.amount_usd.toFixed(2)}
											<div className="text-[11px] font-normal text-neutral-500">
												{payout.amount_vnd.toLocaleString("vi-VN")} VND
											</div>
										</td>
										<td className="px-6 py-4 font-mono text-xs">
											{hasTax ? (
												<div className="space-y-0.5">
													<span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300">
														-10% TT111
													</span>
													<div className="text-amber-700 dark:text-amber-400 font-semibold">
														-{(payout.tax_deducted_vnd ?? 0).toLocaleString("vi-VN")} VND
													</div>
												</div>
											) : (
												<span className="text-neutral-400 text-xs">0 VND (Miễn)</span>
											)}
										</td>
										<td className="px-6 py-4 font-mono font-black text-emerald-600 dark:text-emerald-400">
											${netUsd.toFixed(2)}
											<div className="text-[11px] font-bold text-emerald-700 dark:text-emerald-300">
												{netVnd.toLocaleString("vi-VN")} VND
											</div>
										</td>
										<td className="px-6 py-4 text-xs">
											{payout.payout_method === "credit_wallet" ? (
												<span className="font-semibold text-purple-600 dark:text-purple-400">
													Credit (+10%)
												</span>
											) : (
												<span className="font-medium text-neutral-700 dark:text-neutral-300">
													VietQR Napas
												</span>
											)}
										</td>
										<td className="px-6 py-4">
											{payout.status === "completed" && (
												<span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300">
													<IconCheck className="size-3" aria-hidden="true" />
													<span>Thành công</span>
												</span>
											)}
											{payout.status === "processing" && (
												<span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300">
													<IconLoader2 className="size-3 animate-spin" aria-hidden="true" />
													<span>Đang chuyển</span>
												</span>
											)}
											{payout.status === "pending" && (
												<span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300">
													<span>Chờ duyệt</span>
												</span>
											)}
											{payout.status === "failed" && (
												<span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300">
													<IconAlertCircle className="size-3" aria-hidden="true" />
													<span>Thất bại (Đã hoàn)</span>
												</span>
											)}
										</td>
										<td className="px-6 py-4 font-mono text-xs text-neutral-600 dark:text-neutral-400 max-w-[180px] truncate">
											{payout.napas_ref ? (
												<button
													type="button"
													className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-neutral-100 dark:bg-neutral-800 font-mono text-[11px] cursor-pointer hover:bg-neutral-200 dark:hover:bg-neutral-700"
													onClick={() => handleCopy(payout.napas_ref || "", "Napas Reference")}
													title="Click to copy Napas Reference"
												>
													<span className="truncate">{payout.napas_ref}</span>
													<IconCopy
														className="size-3 shrink-0 text-neutral-400"
														aria-hidden="true"
													/>
												</button>
											) : (
												<span className="text-neutral-400">
													{payout.tx_reference || "Pending Batch"}
												</span>
											)}
										</td>
										<td className="px-6 py-4 text-right">
											{payout.status === "completed" && (
												<Button
													variant="ghost"
													size="sm"
													onClick={() => setSelectedReceipt(payout)}
													className="h-8 px-2.5 text-xs text-neutral-600 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-white"
												>
													<IconFileInvoice
														className="size-3.5 mr-1 text-emerald-600"
														aria-hidden="true"
													/>
													<span>Biên lai</span>
												</Button>
											)}
										</td>
									</tr>
								);
							})}
						</tbody>
					</table>
				</div>
			)}

			{/* Cryptographic Audit Receipt Dialog */}
			<Dialog open={!!selectedReceipt} onOpenChange={() => setSelectedReceipt(null)}>
				<DialogContent className="sm:max-w-lg rounded-3xl p-6">
					<DialogHeader>
						<DialogTitle className="text-xl font-bold flex items-center gap-2">
							<IconShieldCheck className="size-6 text-emerald-600" aria-hidden="true" />
							<span>VietQR Napas Audit Receipt</span>
						</DialogTitle>
						<DialogDescription>
							Cryptographically verified payout transaction record
						</DialogDescription>
					</DialogHeader>

					{selectedReceipt && (
						<div className="space-y-4 py-3 text-sm">
							<div className="p-4 rounded-2xl bg-neutral-50 dark:bg-neutral-800/60 border border-neutral-200 dark:border-neutral-700 space-y-2.5">
								<div className="flex justify-between">
									<span className="text-neutral-500">Transaction ID:</span>
									<span className="font-mono font-bold text-xs">{selectedReceipt.id}</span>
								</div>
								<div className="flex justify-between">
									<span className="text-neutral-500">Napas Reference:</span>
									<span className="font-mono font-bold text-emerald-600">
										{selectedReceipt.napas_ref || "N/A"}
									</span>
								</div>
								<div className="flex justify-between">
									<span className="text-neutral-500">Gross Payout:</span>
									<span className="font-mono font-semibold">
										{(selectedReceipt.amount_vnd ?? 0).toLocaleString("vi-VN")} VND ($
										{(selectedReceipt.amount_usd ?? 0).toFixed(2)})
									</span>
								</div>
								<div className="flex justify-between">
									<span className="text-neutral-500">PIT Tax Withheld (10%):</span>
									<span className="font-mono text-amber-600 font-semibold">
										-{(selectedReceipt.tax_deducted_vnd ?? 0).toLocaleString("vi-VN")} VND
									</span>
								</div>
								<div className="border-t border-neutral-200 dark:border-neutral-700 pt-2 flex justify-between">
									<span className="font-bold text-neutral-900 dark:text-white">Net Deposited:</span>
									<span className="font-mono font-black text-emerald-600 text-base">
										{(
											selectedReceipt.net_amount_vnd ??
											selectedReceipt.amount_vnd ??
											0
										).toLocaleString("vi-VN")}{" "}
										VND
									</span>
								</div>
							</div>

							{selectedReceipt.hmac_audit_hash && (
								<div className="space-y-1">
									<div className="text-xs font-semibold text-neutral-600 dark:text-neutral-400">
										HMAC-SHA256 Audit Seal:
									</div>
									<div className="p-2.5 rounded-xl bg-neutral-100 dark:bg-neutral-800 text-[11px] font-mono text-neutral-700 dark:text-neutral-300 break-all select-all flex items-center justify-between gap-2">
										<span>{selectedReceipt.hmac_audit_hash}</span>
										<button
											type="button"
											onClick={() =>
												handleCopy(selectedReceipt.hmac_audit_hash || "", "Audit Seal Hash")
											}
											className="p-1 hover:text-emerald-600"
										>
											<IconCopy className="size-3.5" aria-hidden="true" />
										</button>
									</div>
								</div>
							)}
						</div>
					)}
				</DialogContent>
			</Dialog>
		</div>
	);
}

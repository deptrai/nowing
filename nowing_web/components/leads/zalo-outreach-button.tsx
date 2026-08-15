"use client";

import { Check, Copy, ExternalLink, MessageCircle, Send, Sparkles } from "lucide-react";
import type React from "react";
import { useState } from "react";
import { leadsApiService } from "@/lib/apis/leads-api.service";
import { cn } from "@/lib/utils";

export interface ZaloOutreachButtonProps {
	leadId: string;
	workspaceId?: number | string;
	phone?: string | null;
	companyName?: string;
	intent?: string | null;
	source?: string | null;
	contentSnippet?: string | null;
	className?: string;
	size?: "sm" | "md";
}

export const cleanPhoneForZalo = (phone?: string | null): string => {
	if (!phone) return "";
	const digits = phone.replace(/\D/g, "");
	if (digits.startsWith("84") && digits.length >= 11) {
		return `0${digits.slice(2)}`;
	}
	if (digits.startsWith("0") && digits.length === 10) {
		return digits;
	}
	if (digits.length === 9) {
		return `0${digits}`;
	}
	return digits;
};

export const ZaloOutreachButton: React.FC<ZaloOutreachButtonProps> = ({
	leadId,
	workspaceId = "1",
	phone,
	companyName = "Khách hàng",
	intent,
	source,
	contentSnippet,
	className,
	size = "sm",
}) => {
	const [loading, setLoading] = useState(false);
	const [copied, setCopied] = useState(false);
	const [showModal, setShowModal] = useState(false);
	const [draftText, setDraftText] = useState("");
	const [customPrompt, setCustomPrompt] = useState("");

	const cleanPhone = cleanPhoneForZalo(phone);
	const fallbackZaloUrl = cleanPhone ? `https://zalo.me/${cleanPhone}` : "https://zalo.me";

	const handleQuickOutreach = async (e: React.MouseEvent) => {
		e.stopPropagation();
		if (loading) return;

		setLoading(true);
		try {
			const res = await leadsApiService.getZaloDraft(workspaceId, leadId, customPrompt || undefined);
			const targetUrl = res.zalo_url || fallbackZaloUrl;
			const textToCopy = res.draft;

			if (navigator.clipboard) {
				await navigator.clipboard.writeText(textToCopy);
			}

			setDraftText(textToCopy);
			setCopied(true);
			setTimeout(() => setCopied(false), 3000);

			// Open Zalo Deep-link
			window.open(targetUrl, "_blank", "noopener,noreferrer");
		} catch {
			// Fallback: copy local contextual template and open deep link
			const fallbackText = `Chào ${companyName}, mình liên hệ từ Nowing liên quan đến bài đăng ${source || "BĐS/Tuyển dụng"}. Mình kết nối trao đổi nhanh nhé!`;
			if (navigator.clipboard) {
				await navigator.clipboard.writeText(fallbackText);
			}
			setCopied(true);
			setTimeout(() => setCopied(false), 3000);
			window.open(fallbackZaloUrl, "_blank", "noopener,noreferrer");
		} finally {
			setLoading(false);
		}
	};

	const handleOpenModal = async (e: React.MouseEvent) => {
		e.stopPropagation();
		setShowModal(true);
		if (!draftText) {
			setLoading(true);
			try {
				const res = await leadsApiService.getZaloDraft(workspaceId, leadId);
				setDraftText(res.draft);
			} catch {
				setDraftText(
					`Chào ${companyName}, mình liên hệ từ Nowing liên quan đến thông tin bên bạn. Mình kết nối trao đổi nhanh nhé!`
				);
			} finally {
				setLoading(false);
			}
		}
	};

	const handleCopyAndLaunch = async () => {
		if (navigator.clipboard && draftText) {
			await navigator.clipboard.writeText(draftText);
		}
		setCopied(true);
		setTimeout(() => setCopied(false), 3000);
		window.open(fallbackZaloUrl, "_blank", "noopener,noreferrer");
		setShowModal(false);
	};

	return (
		<>
			<div className="inline-flex items-center gap-1">
				<button
					type="button"
					onClick={handleQuickOutreach}
					disabled={loading}
					className={cn(
						"inline-flex items-center gap-1.5 font-medium rounded-lg transition-all duration-200 shadow-sm",
						"bg-blue-600/15 text-blue-400 border border-blue-500/30 hover:bg-blue-600/25 hover:border-blue-400/50 hover:text-blue-300",
						size === "sm" ? "px-2.5 py-1 text-xs" : "px-3.5 py-1.5 text-sm",
						copied && "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
						loading && "opacity-75 cursor-wait",
						className
					)}
					title="Mở Zalo Chat kèm tự động sao chép kịch bản AI"
				>
					{loading ? (
						<div className="w-3.5 h-3.5 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
					) : copied ? (
						<Check className="w-3.5 h-3.5 text-emerald-400" />
					) : (
						<MessageCircle className="w-3.5 h-3.5 text-blue-400 fill-blue-400/20" />
					)}
					<span>{copied ? "Đã copy & Mở Zalo" : "Nhắn Zalo"}</span>
				</button>

				<button
					type="button"
					onClick={handleOpenModal}
					className="p-1 rounded-md text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors border border-transparent hover:border-zinc-700"
					title="Xem & chỉnh sửa kịch bản AI trước khi gửi"
				>
					<Sparkles className="w-3.5 h-3.5 text-blue-400" />
				</button>
			</div>

			{/* AI Script Preview & Edit Modal */}
			{showModal && (
				<div
					className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200"
					onClick={() => setShowModal(false)}
				>
					<div
						className="w-full max-w-lg rounded-2xl bg-zinc-900 border border-zinc-800 p-5 space-y-4 shadow-2xl"
						onClick={(e) => e.stopPropagation()}
					>
						{/* Header */}
						<div className="flex items-center justify-between border-b border-zinc-800 pb-3">
							<div className="flex items-center gap-2">
								<div className="p-2 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-400">
									<MessageCircle className="w-5 h-5" />
								</div>
								<div>
									<h3 className="text-sm font-bold text-zinc-100 flex items-center gap-1.5">
										<span>Assisted Zalo Outbound Co-pilot</span>
										<span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 font-mono">
											ToS-Safe
										</span>
									</h3>
									<p className="text-xs text-zinc-400">
										Gửi tới: <strong className="text-zinc-200">{companyName}</strong> ({cleanPhone || "Chưa có SĐT"})
									</p>
								</div>
							</div>
							<button
								type="button"
								onClick={() => setShowModal(false)}
								className="text-xs text-zinc-400 hover:text-zinc-200 px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700"
							>
								Đóng
							</button>
						</div>

						{/* Context Summary */}
						{(intent || source || contentSnippet) && (
							<div className="p-2.5 rounded-lg bg-zinc-950/60 border border-zinc-800/80 text-xs space-y-1">
								<div className="flex items-center justify-between text-[11px] text-zinc-400">
									<span>Nguồn: <strong className="text-zinc-300">{source || "N/A"}</strong></span>
									<span>Intent: <strong className="text-blue-400">{intent || "BÁN"}</strong></span>
								</div>
								{contentSnippet && (
									<p className="text-zinc-400 line-clamp-2 italic text-[11px]">
										"{contentSnippet}"
									</p>
								)}
							</div>
						)}

						{/* Draft Textarea */}
						<div className="space-y-1.5">
							<label className="text-xs font-semibold text-zinc-300 flex items-center justify-between">
								<span>Kịch bản AI soạn sẵn (Có thể chỉnh sửa):</span>
								<span className="text-[11px] text-zinc-500 font-normal">Tự động tối ưu tỷ lệ phản hồi</span>
							</label>
							<textarea
								value={draftText}
								onChange={(e) => setDraftText(e.target.value)}
								rows={4}
								className="w-full p-3 text-xs rounded-xl bg-zinc-950 border border-zinc-800 text-zinc-200 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none font-sans"
								placeholder="Đang soạn kịch bản..."
							/>
						</div>

						{/* Actions */}
						<div className="flex items-center justify-between gap-3 pt-2 border-t border-zinc-800">
							<button
								type="button"
								onClick={async () => {
									if (navigator.clipboard) {
										await navigator.clipboard.writeText(draftText);
									}
									setCopied(true);
									setTimeout(() => setCopied(false), 2000);
								}}
								className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 transition-colors"
							>
								{copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
								<span>{copied ? "Đã sao chép!" : "Chỉ sao chép"}</span>
							</button>

							<button
								type="button"
								onClick={handleCopyAndLaunch}
								className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-all shadow-md shadow-blue-500/20"
							>
								<Send className="w-3.5 h-3.5" />
								<span>Sao chép & Mở Zalo</span>
								<ExternalLink className="w-3 h-3 text-blue-200" />
							</button>
						</div>
					</div>
				</div>
			)}
		</>
	);
};

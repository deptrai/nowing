"use client";

import { Check, Loader2, MessageCircle, Send, Sparkles } from "lucide-react";
import type React from "react";
import { useState } from "react";
import { leadsApiService } from "@/lib/apis/leads-api.service";
import { cn } from "@/lib/utils";
import { ZnsSendModal } from "./zns-send-modal";

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
	compact?: boolean;
	disabled?: boolean;
}

const sizeClasses: Record<"sm" | "md", string> = {
	sm: "h-7 px-2.5 text-xs gap-1.5 rounded-md",
	md: "h-8 px-3.5 text-sm gap-2 rounded-lg",
};

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
	source,
	className,
	size = "sm",
	compact = false,
	disabled = false,
}) => {
	const [loading, setLoading] = useState(false);
	const [copied, setCopied] = useState(false);
	const [showModal, setShowModal] = useState(false);
	const [showZnsModal, setShowZnsModal] = useState(false);
	const [draftText, setDraftText] = useState("");

	const cleanPhone = cleanPhoneForZalo(phone);
	const fallbackZaloUrl = cleanPhone ? `https://zalo.me/${cleanPhone}` : "https://zalo.me";

	const handleQuickOutreach = async (e: React.MouseEvent) => {
		e.stopPropagation();
		if (loading || disabled) return;

		setLoading(true);
		try {
			const res = await leadsApiService.getZaloDraft(workspaceId, leadId);
			const targetUrl = res.zalo_url || fallbackZaloUrl;
			const textToCopy = res.draft;

			if (textToCopy && navigator.clipboard) {
				await navigator.clipboard.writeText(textToCopy);
			}
			setCopied(true);
			setTimeout(() => setCopied(false), 3000);

			window.open(targetUrl, "_blank", "noopener,noreferrer");
		} catch {
			const defaultDraft = `Chào ${companyName}, mình liên hệ từ Nowing liên quan đến bài đăng ${source || "BĐS/Tuyển dụng"}. Mình kết nối trao đổi nhanh nhé!`;
			if (navigator.clipboard) {
				await navigator.clipboard.writeText(defaultDraft);
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
		if (disabled) return;
		setShowModal(true);
		if (!draftText) {
			setLoading(true);
			try {
				const res = await leadsApiService.getZaloDraft(workspaceId, leadId);
				setDraftText(res.draft);
			} catch {
				setDraftText(
					`Chào ${companyName}, mình liên hệ từ Nowing liên quan đến bài đăng ${source || "BĐS/Tuyển dụng"}. Mình kết nối trao đổi nhanh nhé!`
				);
			} finally {
				setLoading(false);
			}
		}
	};

	const handleCopyAndLaunch = async () => {
		if (disabled) return;
		if (draftText && navigator.clipboard) {
			await navigator.clipboard.writeText(draftText);
		}
		setCopied(true);
		setTimeout(() => setCopied(false), 3000);
		window.open(fallbackZaloUrl, "_blank", "noopener,noreferrer");
		setShowModal(false);
	};

	return (
		<>
			<div className={cn("inline-flex items-center gap-1", className)}>
				<button
					type="button"
					onClick={handleQuickOutreach}
					disabled={loading || disabled}
					data-testid="zalo-outreach-button"
					className={cn(
						"inline-flex items-center font-medium transition-all cursor-pointer select-none",
						"bg-blue-600 hover:bg-blue-500 text-white active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed shadow-2xs",
						compact ? "h-7 w-7 justify-center rounded-md" : sizeClasses[size]
					)}
					title={`Kích hoạt kịch bản AI & Mở Zalo chat (${cleanPhone || "Chưa có SĐT"})`}
				>
					{loading ? (
						<Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
					) : copied ? (
						<Check className="size-3.5 text-emerald-300" aria-hidden="true" />
					) : (
						<MessageCircle className="size-3.5" aria-hidden="true" />
					)}
					{!compact && <span>{copied ? "Đã copy!" : "Zalo"}</span>}
				</button>

				<button
					type="button"
					onClick={handleOpenModal}
					disabled={disabled}
					className="size-7 p-0 rounded-md flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted transition-colors border border-border/60 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
					title="Xem & chỉnh sửa kịch bản AI trước khi gửi"
				>
					<Sparkles className="size-3.5 text-blue-500" aria-hidden="true" />
				</button>

				<button
					type="button"
					onClick={(e) => {
						e.stopPropagation();
						if (disabled) return;
						setShowZnsModal(true);
					}}
					disabled={disabled}
					className={cn(
						"inline-flex items-center font-medium transition-all select-none",
						"bg-emerald-600 hover:bg-emerald-500 text-white active:scale-95 shadow-2xs",
						"disabled:opacity-50 disabled:cursor-not-allowed",
						compact ? "h-7 w-7 justify-center rounded-md" : sizeClasses[size]
					)}
					title="Gửi tin nhắn ZNS (Zalo Notification Service) với template đã duyệt"
				>
					<Send className="size-3.5" aria-hidden="true" />
					{!compact && <span>ZNS</span>}
				</button>
			</div>

			{/* AI Script Preview & Edit Modal */}
			{showModal && (
				<div className="fixed inset-0 z-50 flex items-center justify-center p-4">
					<button
						type="button"
						aria-label="Đóng cửa sổ"
						className="absolute inset-0 bg-black/60 backdrop-blur-xs"
						onClick={() => setShowModal(false)}
					/>
					<div className="relative w-full max-w-lg bg-card border border-border rounded-xl shadow-2xl p-5 z-10 animate-in fade-in zoom-in-95 duration-150">
						<div className="flex items-center justify-between pb-3 border-b border-border">
							<div className="flex items-center gap-2">
								<div className="p-1.5 rounded-lg bg-blue-500/10 text-blue-500">
									<MessageCircle className="w-4 h-4" aria-hidden="true" />
								</div>
								<div>
									<h3 className="font-semibold text-sm text-foreground">Soạn kịch bản Zalo AI</h3>
									<p className="text-xs text-muted-foreground">
										Gửi đến: <span className="font-medium text-foreground">{companyName}</span> (
										{cleanPhone || "Chưa có SĐT"})
									</p>
								</div>
							</div>
							<button
								type="button"
								onClick={() => setShowModal(false)}
								className="text-muted-foreground hover:text-foreground text-sm p-1 rounded-md hover:bg-muted"
							>
								✕
							</button>
						</div>

						<div className="py-4 space-y-3">
							<div className="text-xs text-muted-foreground">
								Nội dung tin nhắn được AI cá nhân hoá dựa trên bài đăng và dữ liệu cào:
							</div>
							{loading ? (
								<div className="h-32 flex items-center justify-center bg-muted/30 rounded-lg border border-border/50">
									<Loader2
										className="w-5 h-5 animate-spin text-muted-foreground"
										aria-hidden="true"
									/>
								</div>
							) : (
								<textarea
									rows={5}
									value={draftText}
									onChange={(e) => setDraftText(e.target.value)}
									className="w-full text-xs sm:text-sm p-3 rounded-lg border border-border bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500/50 resize-none font-sans"
									placeholder="Nội dung kịch bản..."
								/>
							)}
						</div>

						<div className="flex items-center justify-end gap-2 pt-2 border-t border-border">
							<button
								type="button"
								onClick={() => setShowModal(false)}
								className="px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground rounded-lg hover:bg-muted transition-colors"
							>
								Hủy
							</button>
							<button
								type="button"
								onClick={handleCopyAndLaunch}
								className="inline-flex items-center gap-1.5 px-4 py-1.5 text-xs font-semibold rounded-lg bg-blue-600 hover:bg-blue-500 text-white shadow-sm transition-all"
							>
								{copied ? (
									<>
										<Check className="w-3.5 h-3.5" aria-hidden="true" />
										<span>Đã copy &amp; Mở Zalo</span>
									</>
								) : (
									<>
										<MessageCircle className="w-3.5 h-3.5" aria-hidden="true" />
										<span>Copy &amp; Mở Zalo Chat</span>
									</>
								)}
							</button>
						</div>
					</div>
				</div>
			)}

			{/* ZNS Template Modal */}
			{showZnsModal && (
				<ZnsSendModal
					onClose={() => setShowZnsModal(false)}
					leadId={leadId}
					workspaceId={workspaceId}
					companyName={companyName}
					phone={phone || ""}
				/>
			)}
		</>
	);
};

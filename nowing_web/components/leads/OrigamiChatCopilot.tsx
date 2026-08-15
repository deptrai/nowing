"use client";

import { useAtom } from "jotai";
import { Bot, PanelLeftClose, RefreshCw, Send, Sparkles, Target, User, X, Zap } from "lucide-react";
import type React from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import {
	type CanvasMode,
	canvasModeAtom,
	isLeftPanelCollapsedAtom,
	selectedLeadContextAtom,
} from "@/atoms/leads/leads-canvas.atoms";
import { OrigamiLogo } from "@/components/origami/OrigamiLogo";
import { cn } from "@/lib/utils";

interface ChatMessage {
	id: string;
	role: "user" | "assistant" | "system";
	content: string;
	timestamp: string;
	actionType?: string;
	suggestedPills?: string[];
}

const MODE_PILLS: Record<CanvasMode, string[]> = {
	leads: [
		"Tìm 20 chủ nhà Thủ Đức giá < 10 Tỷ",
		"Lọc danh sách Fit Score >= 80%",
		"Trích xuất số điện thoại Zalo",
		"Soạn tin nhắn tiếp cận tự động",
	],
	research: [
		"Phân tích thị trường BĐS TP.HCM Q3/2026",
		"Tìm xu hướng tuyển dụng IT AI",
		"Nghiên cứu hồ sơ thầu công ty An Phú",
	],
	scrapers: [
		"Chạy Scraper Batdongsan.com.vn",
		"Quét bài viết Group Facebook BĐS",
		"Cào tin đăng kênh Telegram",
	],
};

export interface OrigamiChatCopilotProps {
	workspaceId?: string | number;
	onFilterApply?: (query: string) => void;
	onTriggerScraper?: (source: string) => void;
	className?: string;
}

export const OrigamiChatCopilot: React.FC<OrigamiChatCopilotProps> = ({
	workspaceId: _workspaceId = "1",
	onFilterApply,
	onTriggerScraper: _onTriggerScraper,
	className,
}) => {
	const [activeMode, setActiveMode] = useAtom(canvasModeAtom);
	const [selectedLead, setSelectedLead] = useAtom(selectedLeadContextAtom);
	const [, setIsCollapsed] = useAtom(isLeftPanelCollapsedAtom);

	const [inputPrompt, setInputPrompt] = useState("");
	const [isSending, setIsSending] = useState(false);
	const [messages, setMessages] = useState<ChatMessage[]>([
		{
			id: "welcome",
			role: "assistant",
			content:
				"Xin chào! Tôi là AI Co-pilot hỗ trợ tìm kiếm và chuyển đổi Leads. Bạn có thể chọn hàng bên phải để phân tích sâu hoặc nhập yêu cầu tìm kiếm khách hàng bằng ngôn ngữ tự nhiên.",
			timestamp: "09:00",
			suggestedPills: MODE_PILLS.leads,
		},
	]);

	const messagesEndRef = useRef<HTMLDivElement>(null);
	const textareaRef = useRef<HTMLTextAreaElement>(null);
	const timerRef = useRef<NodeJS.Timeout | null>(null);

	const scrollToBottom = useCallback(() => {
		messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
	}, []);

	useEffect(() => {
		scrollToBottom();
	}, [scrollToBottom]);

	// Cleanup timer on unmount
	useEffect(() => {
		return () => {
			if (timerRef.current) {
				clearTimeout(timerRef.current);
			}
		};
	}, []);

	// Global ⌘K / Ctrl+K shortcut to focus input
	useEffect(() => {
		const handleGlobalKeyDown = (e: KeyboardEvent) => {
			if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
				e.preventDefault();
				textareaRef.current?.focus();
			}
		};
		window.addEventListener("keydown", handleGlobalKeyDown);
		return () => window.removeEventListener("keydown", handleGlobalKeyDown);
	}, []);

	// Handle sending chat message
	const handleSendMessage = async (textToSend?: string) => {
		const query = (textToSend || inputPrompt).trim();
		if (!query || isSending) return;

		const contextParts = selectedLead
			? [selectedLead.company_name, selectedLead.location, selectedLead.price_estimate].filter(
					Boolean
				)
			: [];
		const contextPrefix =
			contextParts.length > 0 ? `[Đang chọn: ${contextParts.join(" - ")}] ` : "";

		const userMsg: ChatMessage = {
			id: `user-${Date.now()}`,
			role: "user",
			content: `${contextPrefix}${query}`,
			timestamp: new Date().toLocaleTimeString("vi-VN", {
				hour: "2-digit",
				minute: "2-digit",
			}),
		};

		setMessages((prev) => [...prev, userMsg]);
		setInputPrompt("");
		setIsSending(true);

		// If query looks like a search/filter, trigger onFilterApply
		if (
			onFilterApply &&
			(query.toLowerCase().includes("tìm") || query.toLowerCase().includes("lọc"))
		) {
			onFilterApply(query);
		}

		// Simulate AI Assistant response
		if (timerRef.current) clearTimeout(timerRef.current);
		timerRef.current = setTimeout(() => {
			let reply = `Tôi đã nhận lệnh và đang điều phối dữ liệu cho chế độ **${activeMode.toUpperCase()}**.`;
			if (selectedLead) {
				reply += `\n\nĐã phân tích lead **${selectedLead.company_name}** (${selectedLead.source}): Fit Score đạt ${selectedLead.fit_score ?? 85}%, sẵn sàng kích hoạt Zalo Outreach.`;
			} else {
				reply += `\n\nĐang quét và đồng bộ các lead mới nhất vào Live Data Matrix bên phải.`;
			}

			const aiMsg: ChatMessage = {
				id: `ai-${Date.now()}`,
				role: "assistant",
				content: reply,
				timestamp: new Date().toLocaleTimeString("vi-VN", {
					hour: "2-digit",
					minute: "2-digit",
				}),
				suggestedPills: MODE_PILLS[activeMode],
			};

			setMessages((prev) => [...prev, aiMsg]);
			setIsSending(false);
		}, 600);
	};

	const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
		if (e.key === "Enter" && !e.shiftKey) {
			e.preventDefault();
			handleSendMessage();
		}
	};

	return (
		<section
			aria-label="Khung điều khiển AI Copilot"
			data-testid="origami-chat-copilot"
			className={cn(
				"h-full flex flex-col bg-zinc-950/95 border-r border-zinc-800 text-zinc-100 select-none overflow-hidden",
				className
			)}
		>
			{/* Top Header with Origami Logo & Mode Switcher */}
			<div className="p-3.5 border-b border-zinc-800/80 bg-zinc-900/40 soc-caro-grid flex flex-col gap-3">
				<div className="flex items-center justify-between">
					<div className="flex items-center gap-2">
						<OrigamiLogo className="w-5 h-5 text-emerald-400" />
						<h2 className="text-xs font-bold font-sans tracking-tight text-zinc-100">
							AI Co-pilot Matrix
						</h2>
						<span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
							v2.1
						</span>
					</div>

					<button
						type="button"
						onClick={() => setIsCollapsed(true)}
						title="Thu gọn Co-pilot"
						className="p-1 rounded-md text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors cursor-pointer"
					>
						<PanelLeftClose className="w-4 h-4" />
					</button>
				</div>

				{/* 3-Mode Switcher */}
				<div
					data-testid="mode-switcher"
					className="grid grid-cols-3 gap-1 p-1 rounded-xl bg-zinc-950 border border-zinc-800 text-xs"
				>
					<button
						type="button"
						data-testid="mode-tab-leads"
						data-state={activeMode === "leads" ? "active" : "inactive"}
						onClick={() => setActiveMode("leads")}
						className={cn(
							"flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-lg font-medium transition-all cursor-pointer text-[11px]",
							activeMode === "leads"
								? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 shadow-xs font-semibold"
								: "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900"
						)}
					>
						<Target className="w-3.5 h-3.5" />🎯 Leads
					</button>

					<button
						type="button"
						data-testid="mode-tab-research"
						data-state={activeMode === "research" ? "active" : "inactive"}
						onClick={() => setActiveMode("research")}
						className={cn(
							"flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-lg font-medium transition-all cursor-pointer text-[11px]",
							activeMode === "research"
								? "bg-blue-500/20 text-blue-400 border border-blue-500/40 shadow-xs font-semibold"
								: "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900"
						)}
					>
						<Sparkles className="w-3.5 h-3.5" />🧠 Research
					</button>

					<button
						type="button"
						data-testid="mode-tab-scrapers"
						data-state={activeMode === "scrapers" ? "active" : "inactive"}
						onClick={() => setActiveMode("scrapers")}
						className={cn(
							"flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-lg font-medium transition-all cursor-pointer text-[11px]",
							activeMode === "scrapers"
								? "bg-amber-500/20 text-amber-400 border border-amber-500/40 shadow-xs font-semibold"
								: "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900"
						)}
					>
						<Zap className="w-3.5 h-3.5" />⚡ Scrapers
					</button>
				</div>
			</div>

			{/* Chat Messages Stream */}
			<div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin select-text">
				{messages.map((msg) => (
					<div
						key={msg.id}
						className={cn(
							"flex flex-col gap-1.5 text-xs max-w-[90%]",
							msg.role === "user" ? "ml-auto items-end" : "mr-auto items-start"
						)}
					>
						<div className="flex items-center gap-1.5 text-[10px] text-zinc-500 px-1">
							{msg.role === "user" ? (
								<>
									<span>{msg.timestamp}</span>
									<span className="font-semibold text-zinc-400">Bạn</span>
									<User className="w-3 h-3 text-zinc-400" />
								</>
							) : (
								<>
									<Bot className="w-3 h-3 text-emerald-400" />
									<span className="font-semibold text-emerald-400">Co-pilot</span>
									<span>{msg.timestamp}</span>
								</>
							)}
						</div>

						<div
							className={cn(
								"p-3 rounded-2xl leading-relaxed whitespace-pre-wrap",
								msg.role === "user"
									? "bg-emerald-600 text-white rounded-br-xs shadow-md shadow-emerald-950/40"
									: "bg-zinc-900/90 text-zinc-200 border border-zinc-800/80 rounded-bl-xs"
							)}
						>
							{msg.content}
						</div>

						{/* Suggested Action Pills under AI message */}
						{msg.suggestedPills && msg.suggestedPills.length > 0 && (
							<div
								data-testid="suggested-action-pills"
								className="flex flex-wrap gap-1.5 mt-1 pt-1"
							>
								{msg.suggestedPills.map((pill) => (
									<button
										key={pill}
										type="button"
										onClick={() => handleSendMessage(pill)}
										className="text-[11px] px-2.5 py-1 rounded-full bg-zinc-900 hover:bg-emerald-950/50 text-zinc-300 hover:text-emerald-400 border border-zinc-800 hover:border-emerald-500/30 transition-all cursor-pointer text-left"
									>
										⚡ {pill}
									</button>
								))}
							</div>
						)}
					</div>
				))}

				{isSending && (
					<div className="flex items-center gap-2 text-xs text-zinc-400 mr-auto p-3 rounded-xl bg-zinc-900/60 border border-zinc-800">
						<RefreshCw className="w-3.5 h-3.5 animate-spin text-emerald-400" />
						<span>Co-pilot đang phân tích yêu cầu...</span>
					</div>
				)}

				<div ref={messagesEndRef} />
			</div>

			{/* Bottom Input Area with Context Badge */}
			<div className="p-3 border-t border-zinc-800/80 bg-zinc-900/40 space-y-2">
				{/* Bi-directional Context Badge: Selected Lead */}
				{selectedLead && (
					<div className="flex items-center justify-between gap-2 px-2.5 py-1.5 rounded-lg bg-emerald-950/60 border border-emerald-500/40 text-[11px] text-emerald-300 animate-in fade-in duration-150">
						<div className="flex items-center gap-1.5 truncate">
							<span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
							<span className="font-semibold shrink-0">Đang chọn:</span>
							<span className="truncate">{selectedLead.company_name}</span>
							{selectedLead.price_estimate && (
								<span className="font-mono text-[10px] text-emerald-400 shrink-0">
									({selectedLead.price_estimate})
								</span>
							)}
						</div>
						<button
							type="button"
							onClick={() => setSelectedLead(null)}
							title="Bỏ chọn context"
							className="text-emerald-400 hover:text-emerald-200 cursor-pointer p-0.5"
						>
							<X className="w-3.5 h-3.5" />
						</button>
					</div>
				)}

				{/* Composer Box */}
				<div className="relative rounded-xl border border-zinc-800 bg-zinc-950 focus-within:border-emerald-500/50 focus-within:ring-1 focus-within:ring-emerald-500/30 transition-all">
					<textarea
						ref={textareaRef}
						aria-label="Nhập yêu cầu tìm kiếm hoặc lệnh cho AI Co-pilot"
						value={inputPrompt}
						onChange={(e) => setInputPrompt(e.target.value)}
						onKeyDown={handleKeyDown}
						placeholder={
							selectedLead
								? `Hỏi về lead "${selectedLead.company_name}" hoặc gõ lệnh...`
								: "Nhập yêu cầu tìm kiếm khách hàng, ví dụ: 'Tìm 20 chủ nhà quận 2' (Enter gửi)..."
						}
						rows={2}
						className="w-full resize-none bg-transparent px-3 py-2.5 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none scrollbar-thin"
					/>

					<div className="flex items-center justify-between px-3 py-1.5 border-t border-zinc-800/60 text-[10px] text-zinc-500">
						<span className="font-mono">⌘K để tìm kiếm nhanh</span>
						<button
							type="button"
							onClick={() => handleSendMessage()}
							disabled={!inputPrompt.trim() || isSending}
							className={cn(
								"inline-flex items-center gap-1 px-2.5 py-1 rounded-md font-semibold text-[11px] transition-all cursor-pointer",
								inputPrompt.trim() && !isSending
									? "bg-emerald-600 hover:bg-emerald-500 text-white shadow-xs"
									: "bg-zinc-800 text-zinc-500 cursor-not-allowed"
							)}
						>
							<Send className="w-3 h-3" />
							Gửi
						</button>
					</div>
				</div>
			</div>
		</section>
	);
};

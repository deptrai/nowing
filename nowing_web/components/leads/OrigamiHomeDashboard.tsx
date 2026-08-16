"use client";

import {
	ArrowUpRight,
	ChevronDown,
	CornerDownLeft,
	Lightbulb,
	Link2,
	Mic,
	Paperclip,
	Plus,
	Sparkles,
	X,
	Zap,
} from "lucide-react";
import type React from "react";
import { useState } from "react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

export interface OrigamiHomeDashboardProps {
	userName?: string;
	onSendPrompt: (prompt: string) => void;
	className?: string;
}

export const OrigamiHomeDashboard: React.FC<OrigamiHomeDashboardProps> = ({
	userName = "Crypto",
	onSendPrompt,
	className,
}) => {
	const [prompt, setPrompt] = useState("");
	const [showBanner, setShowBanner] = useState(true);

	const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
		if (e.key === "Enter" && !e.shiftKey) {
			e.preventDefault();
			handleSubmit();
		}
	};

	const handleSubmit = () => {
		const trimmed = prompt.trim();
		if (!trimmed) return;
		onSendPrompt(trimmed);
	};

	const suggestionChips = [
		{
			label: "Give me ideas",
			icon: <Lightbulb className="w-3.5 h-3.5 text-amber-500" />,
			prompt: "Gợi ý cho tôi 5 chiến dịch tìm kiếm khách hàng tiềm năng hiệu quả nhất tuần này",
		},
		{
			label: "New campaign",
			icon: <Plus className="w-3.5 h-3.5 text-emerald-500" />,
			prompt: "Tạo chiến dịch mới săn 20 doanh nghiệp Bất động sản tại Hà Nội",
		},
		{
			label: "Săn Lead BĐS Hà Nội",
			icon: <Sparkles className="w-3.5 h-3.5 text-blue-500" />,
			prompt: "Tìm kiếm 10 công ty Bất động sản uy tín tại Hà Nội và thêm vào bảng",
		},
		{
			label: "Tín hiệu tuyển dụng Tech",
			icon: <Zap className="w-3.5 h-3.5 text-purple-500" />,
			prompt: "Quét các công ty công nghệ đang tuyển dụng Senior Developer trên TopCV",
		},
	];

	return (
		<div
			className={cn(
				"min-h-full w-full bg-background text-foreground flex flex-col justify-between p-6 sm:p-10 font-sans relative overflow-y-auto",
				className
			)}
		>
			{/* Top Bar Credits */}
			<div className="w-full flex items-center justify-end">
				<div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-pink-500/10 dark:bg-pink-500/20 text-pink-600 dark:text-pink-400 text-xs font-semibold border border-pink-500/20 shadow-2xs">
					<span>🌸</span>
					<span className="font-mono font-bold">1,420</span> Credits
				</div>
			</div>

			{/* Center Hero Content Container */}
			<div className="max-w-3xl w-full mx-auto my-auto py-6 space-y-8">
				{/* Welcome Title */}
				<div className="text-center">
					<h1 className="text-3xl sm:text-4xl lg:text-5xl font-serif tracking-tight text-foreground font-normal">
						Welcome back, {userName}.
					</h1>
				</div>

				{/* Hero Central Prompt Box */}
				<div className="relative rounded-2xl border border-border/90 bg-card shadow-sm hover:border-border hover:shadow-md transition-all p-4 space-y-3">
					<textarea
						value={prompt}
						onChange={(e) => setPrompt(e.target.value)}
						onKeyDown={handleKeyDown}
						placeholder="Monitor Twitter for people complaining about our competitors or hunt real estate leads in Hanoi..."
						rows={3}
						className="w-full bg-transparent text-sm sm:text-base text-foreground placeholder:text-muted-foreground/70 resize-none outline-none focus:outline-none"
					/>

					{/* Composer Bottom Action Bar */}
					<div className="flex items-center justify-between pt-2 border-t border-border/50">
						<div className="flex items-center gap-1">
							<button
								type="button"
								title="Thêm công cụ"
								className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted/70 transition-colors cursor-pointer"
							>
								<Plus className="w-4 h-4" />
							</button>
							<button
								type="button"
								title="Đính kèm tệp tin"
								className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted/70 transition-colors cursor-pointer"
							>
								<Paperclip className="w-4 h-4" />
							</button>
							<button
								type="button"
								title="Thêm liên kết"
								className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted/70 transition-colors cursor-pointer"
							>
								<Link2 className="w-4 h-4" />
							</button>
						</div>

						<div className="flex items-center gap-2">
							<button
								type="button"
								className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors cursor-pointer"
							>
								<Zap className="w-3.5 h-3.5 text-amber-500" />
								<span>Lite</span>
								<ChevronDown className="w-3 h-3 opacity-60" />
							</button>

							<button
								type="button"
								title="Nhập giọng nói"
								className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors cursor-pointer"
							>
								<Mic className="w-4 h-4" />
							</button>

							<button
								type="button"
								onClick={handleSubmit}
								disabled={!prompt.trim()}
								title="Gửi yêu cầu"
								className="w-8 h-8 rounded-xl bg-pink-500 hover:bg-pink-600 dark:bg-pink-600 dark:hover:bg-pink-500 disabled:opacity-40 text-white flex items-center justify-center transition-transform hover:scale-105 active:scale-95 cursor-pointer shadow-xs"
							>
								<CornerDownLeft className="w-4 h-4" />
							</button>
						</div>
					</div>
				</div>

				{/* Quick Suggestion Chips */}
				<div className="flex flex-wrap items-center justify-center gap-2">
					{suggestionChips.map((chip) => (
						<button
							key={chip.label}
							type="button"
							onClick={() => onSendPrompt(chip.prompt)}
							className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-border/80 bg-card hover:bg-muted/70 text-xs font-medium text-foreground transition-all hover:scale-102 cursor-pointer shadow-2xs"
						>
							{chip.icon}
							<span>{chip.label}</span>
						</button>
					))}
				</div>

				{/* Beta Outreach Agent Setup Card */}
				{showBanner && (
					<div className="p-4 rounded-2xl border border-pink-500/20 bg-pink-500/5 dark:bg-pink-500/10 flex items-start sm:items-center justify-between gap-4 relative">
						<div className="flex items-center gap-3">
							<div className="w-10 h-10 rounded-2xl bg-pink-500/15 flex items-center justify-center text-xl shrink-0">
								🌸
							</div>
							<div>
								<div className="flex items-center gap-2">
									<h4 className="text-xs sm:text-sm font-bold text-foreground">
										Set up your Outreach Agent
									</h4>
									<span className="px-1.5 py-0.2 rounded bg-pink-500/20 text-pink-700 dark:text-pink-300 text-[10px] font-extrabold uppercase tracking-wider">
										BETA
									</span>
								</div>
								<p className="text-xs text-muted-foreground mt-0.5 max-w-xl">
									15 minutes of setup, then it maximizes your replies — keeping quality leads
									flowing and your senders at full speed.
								</p>
							</div>
						</div>

						<div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
							<button
								type="button"
								onClick={() => toast.success("Mở trình thiết lập Outreach Agent")}
								className="px-3.5 py-1.5 rounded-xl bg-zinc-900 hover:bg-zinc-800 dark:bg-zinc-100 dark:hover:bg-zinc-200 dark:text-zinc-900 text-white text-xs font-semibold transition-colors cursor-pointer shadow-xs"
							>
								Set it up
							</button>
							<button
								type="button"
								onClick={() => setShowBanner(false)}
								className="p-1 text-muted-foreground hover:text-foreground rounded-lg transition-colors cursor-pointer"
							>
								<X className="w-4 h-4" />
							</button>
						</div>
					</div>
				)}

				{/* Activity & Stats Row */}
				<div className="flex flex-wrap items-center justify-between gap-3 text-xs pt-2 border-t border-border/40">
					<div className="text-muted-foreground">
						Past 7 days <strong className="text-foreground font-mono font-bold">15</strong> new
						leads
					</div>
					<div className="flex items-center gap-3">
						<button
							type="button"
							onClick={() => toast.info("Kết nối kênh Email")}
							className="text-muted-foreground hover:text-foreground font-medium transition-colors cursor-pointer"
						>
							Connect email →
						</button>
						<button
							type="button"
							onClick={() => toast.info("Kết nối Zalo OA")}
							className="text-muted-foreground hover:text-foreground font-medium transition-colors cursor-pointer"
						>
							Connect Zalo →
						</button>
						<button
							type="button"
							onClick={() => toast.info("Kết nối LinkedIn")}
							className="text-muted-foreground hover:text-foreground font-medium transition-colors cursor-pointer"
						>
							Connect LinkedIn →
						</button>
					</div>
				</div>

				{/* Insight Cards (What's costing you replies) */}
				<div className="space-y-3">
					<div className="text-xs text-muted-foreground">
						<strong className="text-foreground">What&apos;s costing you replies</strong> • from your
						August 10 report
					</div>

					<div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
						{/* Card 1 */}
						<div className="p-4 rounded-2xl border border-border/80 bg-card hover:border-border transition-all flex flex-col justify-between gap-3 shadow-2xs">
							<div className="space-y-2">
								<div className="w-7 h-7 rounded-xl bg-muted flex items-center justify-center text-muted-foreground">
									<ArrowUpRight className="w-4 h-4" />
								</div>
								<h4 className="text-xs font-bold text-foreground leading-snug">
									No email or Zalo sender connected
								</h4>
								<p className="text-[11px] text-muted-foreground">
									15 qualified agarwood leads built, nothing sent yet
								</p>
							</div>
							<button
								type="button"
								onClick={() => toast.info("Xem chi tiết cài đặt kết nối")}
								className="text-left text-xs font-semibold text-pink-600 dark:text-pink-400 hover:underline cursor-pointer"
							>
								View details
							</button>
						</div>

						{/* Card 2 */}
						<div className="p-4 rounded-2xl border border-border/80 bg-card hover:border-border transition-all flex flex-col justify-between gap-3 shadow-2xs">
							<div className="space-y-2">
								<div className="w-7 h-7 rounded-xl bg-muted flex items-center justify-center text-muted-foreground">
									<ArrowUpRight className="w-4 h-4" />
								</div>
								<h4 className="text-xs font-bold text-foreground leading-snug">
									Your strongest list has never been sequenced
								</h4>
								<p className="text-[11px] text-muted-foreground">
									9 qualified Vietnamese agarwood companies, ready
								</p>
							</div>
							<button
								type="button"
								onClick={() => toast.info("Xem danh sách khách hàng sẵn sàng")}
								className="text-left text-xs font-semibold text-pink-600 dark:text-pink-400 hover:underline cursor-pointer"
							>
								View details
							</button>
						</div>

						{/* Card 3 */}
						<div className="p-4 rounded-2xl border border-border/80 bg-card hover:border-border transition-all flex flex-col justify-between gap-3 shadow-2xs">
							<div className="space-y-2">
								<div className="w-7 h-7 rounded-xl bg-muted flex items-center justify-center text-muted-foreground">
									<Sparkles className="w-4 h-4" />
								</div>
								<h4 className="text-xs font-bold text-foreground leading-snug">
									Your warmest leads have no contact channel
								</h4>
								<p className="text-[11px] text-muted-foreground">
									grow the reply-able business segment instead
								</p>
							</div>
							<button
								type="button"
								onClick={() => toast.info("Xem chi tiết kênh liên hệ")}
								className="text-left text-xs font-semibold text-pink-600 dark:text-pink-400 hover:underline cursor-pointer"
							>
								View details
							</button>
						</div>
					</div>
				</div>
			</div>
		</div>
	);
};

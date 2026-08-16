"use client";

import { ArrowRight, CheckCircle2, Flame, Globe, ShieldCheck, Target, Zap } from "lucide-react";
import { useRouter } from "next/navigation";
import type React from "react";
import { useState } from "react";
import { cn } from "@/lib/utils";

const QUICK_PROMPTS = [
	{
		label: "🏠 Nhà phố Tân Bình < 10 tỷ",
		query:
			"Tìm 30 môi giới và chính chủ bán nhà phố quận Tân Bình giá dưới 10 tỷ trên Batdongsan và Chợ Tốt kèm SĐT",
	},
	{
		label: "💼 Giám đốc IT / Founder Hà Nội",
		query:
			"Tìm 25 Giám đốc công nghệ (CTO), Founder công ty phần mềm tại Hà Nội đang tuyển dụng trên TopCV & ITviec",
	},
	{
		label: "👗 Shop sỉ thời trang Ninh Hiệp",
		query:
			"Tìm 40 đầu mối tổng kho, xưởng may sỉ thời trang chợ Ninh Hiệp & Tân Bình có tương tác cao trên Facebook",
	},
	{
		label: "🏗️ Thầu xây dựng & Mua sắm công",
		query: "Tìm các nhà thầu cơ điện và xây dựng vừa trúng gói thầu trên Mua Sắm Công tháng này",
	},
];

export const NowingHero: React.FC = () => {
	const router = useRouter();
	const [mode, setMode] = useState<"lead_gen" | "enrich" | "viral">("lead_gen");
	const [prompt, setPrompt] = useState("");
	const [urlInput, setUrlInput] = useState("");
	const [showUrlModal, setShowUrlModal] = useState(false);

	const handleSearch = (customPrompt?: string) => {
		const targetPrompt = customPrompt || prompt;
		if (!targetPrompt.trim()) return;
		router.push(`/dashboard?prompt=${encodeURIComponent(targetPrompt)}`);
	};

	const handleReverseIcp = () => {
		if (!urlInput.trim()) return;
		router.push(`/dashboard?reverse_icp=${encodeURIComponent(urlInput)}`);
	};

	return (
		<section className="relative pt-12 pb-16 md:pt-20 md:pb-24 overflow-hidden">
			{/* Grid Paper Caro & Mint Ambient Background */}
			<div
				className="absolute inset-0 -z-10 pointer-events-none opacity-80"
				style={{
					backgroundImage: `
						radial-gradient(circle at 50% 15%, rgba(16, 185, 129, 0.12) 0%, transparent 65%),
						linear-gradient(to right, rgba(15, 23, 42, 0.04) 1px, transparent 1px),
						linear-gradient(to bottom, rgba(15, 23, 42, 0.04) 1px, transparent 1px)
					`,
					backgroundSize: "100% 100%, 28px 28px, 28px 28px",
					maskImage: "linear-gradient(to bottom, black 80%, transparent 100%)",
					WebkitMaskImage: "linear-gradient(to bottom, black 80%, transparent 100%)",
				}}
			/>

			<div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
				{/* Top Launch Pill */}
				<div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border border-emerald-200/80 bg-emerald-50/80 text-emerald-800 dark:bg-emerald-950/50 dark:border-emerald-800/80 dark:text-emerald-300 text-xs font-semibold mb-6 shadow-xs backdrop-blur-xs">
					<span className="flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
					<span>Nowing 2.0 Lead Intelligence</span>
					<span className="text-emerald-400">·</span>
					<span>Nền tảng Săn Lead B2B Đa kênh</span>
				</div>

				{/* Instrument Serif / Display Headline */}
				<h1 className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-serif tracking-tight text-slate-900 dark:text-white leading-[1.08] mb-6">
					Tìm kiếm khách hàng & bất động sản mục tiêu{" "}
					<span className="italic text-emerald-600 dark:text-emerald-400 font-normal">
						chỉ với một câu lệnh.
					</span>
				</h1>

				{/* Subtitle */}
				<p className="text-lg sm:text-xl text-slate-600 dark:text-slate-300 max-w-3xl mx-auto mb-10 leading-relaxed">
					Nền tảng AI Lead Intelligence tự động cào dữ liệu từ <strong>15+ nguồn Việt Nam</strong>{" "}
					(Batdongsan, Chợ Tốt, TopCV, Facebook, Telegram), mở khóa số điện thoại chính chủ và kết
					nối Zalo tức thì.
				</p>

				{/* Mode Switcher Tabs */}
				<div className="inline-flex items-center p-1 rounded-full bg-slate-100 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 mb-4 shadow-xs">
					<button
						type="button"
						onClick={() => setMode("lead_gen")}
						className={cn(
							"flex items-center gap-2 px-4 py-2 rounded-full text-xs sm:text-sm font-semibold transition-all",
							mode === "lead_gen"
								? "bg-white dark:bg-slate-900 text-emerald-700 dark:text-emerald-400 shadow-xs border border-emerald-200/60"
								: "text-slate-600 dark:text-slate-400 hover:text-slate-900"
						)}
					>
						<Target className="w-3.5 h-3.5" />
						<span>Săn khách hàng (Lead Gen)</span>
					</button>

					<button
						type="button"
						onClick={() => setMode("enrich")}
						className={cn(
							"flex items-center gap-2 px-4 py-2 rounded-full text-xs sm:text-sm font-semibold transition-all",
							mode === "enrich"
								? "bg-white dark:bg-slate-900 text-emerald-700 dark:text-emerald-400 shadow-xs border border-emerald-200/60"
								: "text-slate-600 dark:text-slate-400 hover:text-slate-900"
						)}
					>
						<Zap className="w-3.5 h-3.5" />
						<span>Làm giàu dữ liệu & SĐT</span>
					</button>

					<button
						type="button"
						onClick={() => setMode("viral")}
						className={cn(
							"flex items-center gap-2 px-4 py-2 rounded-full text-xs sm:text-sm font-semibold transition-all",
							mode === "viral"
								? "bg-white dark:bg-slate-900 text-emerald-700 dark:text-emerald-400 shadow-xs border border-emerald-200/60"
								: "text-slate-600 dark:text-slate-400 hover:text-slate-900"
						)}
					>
						<Flame className="w-3.5 h-3.5" />
						<span>Nội dung Viral Outbound</span>
					</button>
				</div>

				{/* Prompt Input Box */}
				<div className="relative max-w-3xl mx-auto bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xl shadow-slate-200/40 dark:shadow-none p-3 sm:p-4 text-left transition-all focus-within:border-emerald-400 dark:focus-within:border-emerald-500 focus-within:ring-4 focus-within:ring-emerald-500/10">
					<textarea
						rows={3}
						value={prompt}
						onChange={(e) => setPrompt(e.target.value)}
						placeholder={
							mode === "lead_gen"
								? "VD: Tìm cho tôi 50 môi giới BĐS khu vực Thủ Đức đang có khách tìm mua nhà phố, hoặc các công ty IT tại Hà Nội đang tuyển ReactJS..."
								: mode === "enrich"
									? "VD: Dán danh sách 20 tên công ty hoặc URL website để mở khóa email Ban giám đốc và SĐT hotline..."
									: "VD: Phân tích 10 bài viết viral ngành BĐS trên Facebook tuần qua và viết lại theo văn phong của tôi..."
						}
						className="w-full bg-transparent border-none outline-none resize-none text-slate-800 dark:text-slate-100 placeholder:text-slate-400 text-sm sm:text-base leading-relaxed"
						onKeyDown={(e) => {
							if (e.key === "Enter" && !e.shiftKey) {
								e.preventDefault();
								handleSearch();
							}
						}}
					/>

					{/* Toolbar Actions */}
					<div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-100 dark:border-slate-800/80">
						<div className="flex items-center gap-2">
							<button
								type="button"
								onClick={() => setShowUrlModal(!showUrlModal)}
								className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 transition-colors"
							>
								<Globe className="w-3.5 h-3.5 text-emerald-600" />
								<span>1-Click Reverse-ICP từ URL</span>
							</button>

							<span className="hidden sm:inline-flex items-center gap-1 text-[11px] text-slate-400">
								<ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
								<span>Tuân thủ NĐ 91/2020 & 13/2023</span>
							</span>
						</div>

						<div className="flex items-center gap-2">
							<button
								type="button"
								onClick={() => handleSearch()}
								className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 dark:bg-emerald-600 dark:hover:bg-emerald-500 text-white text-xs sm:text-sm font-semibold shadow-md transition-all active:scale-95"
							>
								<span>Khởi tạo Danh sách</span>
								<ArrowRight className="w-4 h-4" />
							</button>
						</div>
					</div>

					{/* URL Modal Input */}
					{showUrlModal && (
						<div className="mt-3 p-3 rounded-xl bg-emerald-50/70 dark:bg-slate-800/90 border border-emerald-200 dark:border-emerald-800 animate-in fade-in-50 duration-150">
							<label
								htmlFor="reverse-icp-input"
								className="block text-xs font-semibold text-emerald-900 dark:text-emerald-300 mb-1.5"
							>
								Dán đường dẫn Website hoặc Landing Page dự án để tự động trích xuất ICP:
							</label>
							<div className="flex items-center gap-2">
								<input
									id="reverse-icp-input"
									type="url"
									value={urlInput}
									onChange={(e) => setUrlInput(e.target.value)}
									placeholder="https://vinhomes.vn hoặc https://topcv.vn..."
									className="flex-1 px-3 py-1.5 text-xs bg-white dark:bg-slate-900 border border-emerald-300 dark:border-emerald-700 rounded-lg outline-none focus:ring-2 focus:ring-emerald-500"
								/>
								<button
									type="button"
									onClick={handleReverseIcp}
									className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow-xs"
								>
									Phân tích ngay
								</button>
							</div>
						</div>
					)}
				</div>

				{/* Quick Suggestions Chips */}
				<div className="mt-4 flex flex-wrap items-center justify-center gap-2 text-xs text-slate-500">
					<span className="font-medium text-slate-400">Gợi ý nhanh:</span>
					{QUICK_PROMPTS.map((item) => (
						<button
							key={item.label}
							type="button"
							onClick={() => {
								setPrompt(item.query);
								handleSearch(item.query);
							}}
							className="px-2.5 py-1 rounded-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 hover:border-emerald-400 hover:text-emerald-700 dark:hover:text-emerald-300 transition-colors shadow-2xs"
						>
							{item.label}
						</button>
					))}
				</div>

				{/* Trust Stats Bar */}
				<div className="mt-12 pt-8 border-t border-slate-200/80 dark:border-slate-800 flex flex-wrap items-center justify-center gap-8 text-slate-500 dark:text-slate-400 text-xs sm:text-sm font-medium">
					<div className="flex items-center gap-2">
						<CheckCircle2 className="w-4 h-4 text-emerald-500" />
						<span>
							<strong>$0 Trọn đời</strong> tính năng Chat & Tạo chiến dịch
						</span>
					</div>
					<div className="flex items-center gap-2">
						<CheckCircle2 className="w-4 h-4 text-emerald-500" />
						<span>
							<strong>3 Tầng giải mã</strong> SĐT Batdongsan, Chợ Tốt & Zalo
						</span>
					</div>
					<div className="flex items-center gap-2">
						<CheckCircle2 className="w-4 h-4 text-emerald-500" />
						<span>
							<strong>100% Hoàn tiền</strong> tự động nếu SĐT không liên lạc được
						</span>
					</div>
				</div>
			</div>
		</section>
	);
};

"use client";

import {
	BookOpen,
	Download,
	ExternalLink,
	FileText,
	Headphones,
	Play,
	Sparkles,
} from "lucide-react";
import type React from "react";
import { useState } from "react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

export interface ResearchStudioPanelProps {
	workspaceId?: string | number;
	report?: {
		title: string;
		summary: string;
		keyFindings: string[];
		citations: Array<{ title: string; url: string; snippet?: string }>;
		wordCount?: number;
		readingTime?: string;
	};
	className?: string;
}

export const ResearchStudioPanel: React.FC<ResearchStudioPanelProps> = ({
	workspaceId: _workspaceId = "1",
	report,
	className,
}) => {
	const [activeSubTab, setActiveSubTab] = useState<"report" | "sources" | "podcast">("report");
	const [isPlayingPodcast, setIsPlayingPodcast] = useState(false);

	const reportTitle = report?.title || "Báo Cáo Nghiên Cứu Thị Trường";
	const reportSummary = report?.summary || "Tổng quan phân tích chuyên sâu về dữ liệu ngành.";
	const _findings = report?.keyFindings || [
		"Thị trường đang ghi nhận mức tăng trưởng nhu cầu tìm kiếm 24% so với cùng kỳ.",
		"Tỷ lệ phản hồi qua kênh Zalo cá nhân hóa đạt 38.5%, cao gấp 3 lần Email.",
	];
	const _citations = report?.citations || [];

	const handleExportMarkdown = () => {
		toast.success("Đang xuất báo cáo định dạng Markdown...", { duration: 1500 });
	};

	const handleExportPdf = () => {
		toast.success("Đang chuẩn bị file PDF nghiên cứu...", { duration: 1500 });
	};

	return (
		<div
			className={cn(
				"h-full flex flex-col bg-background text-foreground overflow-hidden font-sans",
				className
			)}
		>
			{/* Sub Navigation Bar */}
			<div className="h-10 border-b border-border/80 bg-muted/30 flex items-center justify-between px-4 shrink-0">
				<div className="flex items-center gap-1">
					<button
						type="button"
						onClick={() => setActiveSubTab("report")}
						className={cn(
							"flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-md transition-colors cursor-pointer",
							activeSubTab === "report"
								? "bg-background text-foreground shadow-xs border border-border/80"
								: "text-muted-foreground hover:text-foreground hover:bg-muted/60"
						)}
					>
						<FileText className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
						<span>Báo Cáo Nghiên Cứu</span>
					</button>
					<button
						type="button"
						onClick={() => setActiveSubTab("sources")}
						className={cn(
							"flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-md transition-colors cursor-pointer",
							activeSubTab === "sources"
								? "bg-background text-foreground shadow-xs border border-border/80"
								: "text-muted-foreground hover:text-foreground hover:bg-muted/60"
						)}
					>
						<BookOpen className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
						<span>Nguồn Trích Dẫn & RAG (8)</span>
					</button>
					<button
						type="button"
						onClick={() => setActiveSubTab("podcast")}
						className={cn(
							"flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-md transition-colors cursor-pointer",
							activeSubTab === "podcast"
								? "bg-background text-foreground shadow-xs border border-border/80"
								: "text-muted-foreground hover:text-foreground hover:bg-muted/60"
						)}
					>
						<Headphones className="w-3.5 h-3.5 text-purple-600 dark:text-purple-400" />
						<span>Audio Brief (3:20)</span>
					</button>
				</div>

				<div className="flex items-center gap-2">
					<button
						type="button"
						onClick={handleExportMarkdown}
						className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-md border border-border/80 bg-card hover:bg-muted text-foreground transition-colors cursor-pointer"
					>
						<Download className="w-3 h-3" />
						<span>Xuất .MD</span>
					</button>
					<button
						type="button"
						onClick={handleExportPdf}
						className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-md bg-emerald-600 hover:bg-emerald-500 text-white transition-colors cursor-pointer shadow-xs"
					>
						<Download className="w-3 h-3" />
						<span>Tải PDF</span>
					</button>
				</div>
			</div>

			{/* Main Content Area */}
			<div className="flex-1 overflow-y-auto p-6 scrollbar-thin">
				{activeSubTab === "report" && (
					<div className="max-w-3xl mx-auto space-y-6">
						{/* Report Header */}
						<div className="border-b border-border pb-4">
							<div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 text-[11px] font-semibold mb-2 border border-emerald-500/20">
								<Sparkles className="w-3 h-3" />
								Chainlens Deep Research Synthesis
							</div>
							<h1 className="text-lg sm:text-xl font-serif font-medium tracking-tight text-foreground">
								{reportTitle}
							</h1>
							<p className="text-xs text-muted-foreground mt-1">
								Tổng hợp từ dữ liệu thời gian thực và trích dẫn kiểm chứng của Nowing
							</p>
						</div>

						{/* Executive Summary Card */}
						<div className="p-4 rounded-xl bg-muted/40 border border-border/80 space-y-2">
							<h2 className="text-xs font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">
								Tóm Tắt Điều Hành (Executive Summary)
							</h2>
							<p className="text-xs text-foreground leading-relaxed">{reportSummary}</p>
						</div>

						{/* Market Highlights Grid */}
						<div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
							<div className="p-3.5 rounded-xl border border-border bg-card">
								<span className="text-[11px] text-muted-foreground block mb-1">
									Thanh Khoản Q2/2026
								</span>
								<span className="text-xl font-bold text-foreground font-mono">+18.4%</span>
								<span className="text-[10px] text-emerald-600 block mt-0.5">
									Tăng so với cùng kỳ
								</span>
							</div>
							<div className="p-3.5 rounded-xl border border-border bg-card">
								<span className="text-[11px] text-muted-foreground block mb-1">
									Phân Khúc Tiêu Biểu
								</span>
								<span className="text-base font-bold text-foreground">Chung Cư Cao Cấp</span>
								<span className="text-[10px] text-muted-foreground block mt-0.5">
									Tây Hồ & Nam Từ Liêm
								</span>
							</div>
							<div className="p-3.5 rounded-xl border border-border bg-card">
								<span className="text-[11px] text-muted-foreground block mb-1">
									Doanh Nghiệp Đang Săn Lead
								</span>
								<span className="text-xl font-bold text-emerald-600 font-mono">142+ Công ty</span>
								<span className="text-[10px] text-muted-foreground block mt-0.5">
									Trên hệ thống Nowing
								</span>
							</div>
						</div>

						{/* Key Findings Section */}
						<div className="space-y-3">
							<h3 className="text-sm font-bold text-foreground">Các Phát Hiện Trọng Yếu</h3>
							<ul className="space-y-2 text-xs text-foreground">
								<li className="flex items-start gap-2">
									<span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mt-1.5 shrink-0" />
									<span>
										<strong>Sự dịch chuyển kênh tiếp cận:</strong> 72% môi giới chuyển dịch từ gọi
										điện thoại lạnh (Cold Call) sang nhắn Zalo ZNS cá nhân hóa dựa trên dữ liệu định
										danh chính chủ.
									</span>
								</li>
								<li className="flex items-start gap-2">
									<span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mt-1.5 shrink-0" />
									<span>
										<strong>Tín hiệu từ các gói thầu hạ tầng:</strong> Các dự án Vành đai 4 mở ra
										làn sóng đầu tư đất nền vùng ven (Đan Phượng, Mê Linh, Hoài Đức).
									</span>
								</li>
							</ul>
						</div>
					</div>
				)}

				{activeSubTab === "sources" && (
					<div className="max-w-3xl mx-auto space-y-4">
						<div className="border-b border-border pb-3">
							<h2 className="text-base font-bold text-foreground">
								Nguồn Dữ Liệu & Tài Liệu RAG (8 Nguồn)
							</h2>
							<p className="text-xs text-muted-foreground">
								Các tài liệu và trang web được AI quét và trích xuất số liệu phục vụ báo cáo
							</p>
						</div>

						<div className="space-y-2.5">
							{[
								{
									title: "Báo cáo thị trường BĐS Hà Nội Q2/2026 — Savills Vietnam",
									domain: "savills.com.vn",
									type: "PDF Document",
									time: "10 phút trước",
								},
								{
									title: "Dữ liệu tin đăng mua bán nhà đất quận Cầu Giấy & Tây Hồ",
									domain: "batdongsan.com.vn",
									type: "Scraper Live Data",
									time: "Vừa cập nhật",
								},
								{
									title: "Quyết định phê duyệt quy hoạch phân khu đô thị sông Hồng",
									domain: "hanoi.gov.vn",
									type: "Government Portal",
									time: "Hôm qua",
								},
								{
									title: "Thống kê giao dịch bất động sản công chứng quý 2",
									domain: "moj.gov.vn",
									type: "Official Data",
									time: "2 ngày trước",
								},
							].map((source, i) => (
								<div
									key={source.title}
									className="p-3 rounded-xl border border-border bg-card flex items-center justify-between gap-3 hover:border-emerald-500/40 transition-colors"
								>
									<div className="flex items-center gap-3 overflow-hidden">
										<div className="w-8 h-8 rounded-lg bg-muted flex items-center justify-center text-xs font-bold text-muted-foreground font-mono shrink-0">
											#{i + 1}
										</div>
										<div className="overflow-hidden">
											<h4 className="text-xs font-semibold text-foreground truncate">
												{source.title}
											</h4>
											<div className="flex items-center gap-2 text-[11px] text-muted-foreground mt-0.5">
												<span className="font-mono">{source.domain}</span>
												<span>•</span>
												<span className="text-emerald-600 dark:text-emerald-400 font-medium">
													{source.type}
												</span>
												<span>•</span>
												<span>{source.time}</span>
											</div>
										</div>
									</div>
									<button
										type="button"
										className="p-1.5 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors shrink-0"
										title="Mở liên kết"
									>
										<ExternalLink className="w-3.5 h-3.5" />
									</button>
								</div>
							))}
						</div>
					</div>
				)}

				{activeSubTab === "podcast" && (
					<div className="max-w-md mx-auto py-8 text-center space-y-5">
						<div className="w-20 h-20 rounded-3xl bg-purple-500/10 border border-purple-500/30 flex items-center justify-center mx-auto text-purple-600 dark:text-purple-400 shadow-md">
							<Headphones className="w-10 h-10" />
						</div>
						<div>
							<h3 className="text-base font-bold text-foreground">
								AI Audio Brief — Tóm Tắt 3 Phút
							</h3>
							<p className="text-xs text-muted-foreground mt-1">
								Giọng đọc AI tự nhiên tóm tắt các điểm nhấn quan trọng của báo cáo
							</p>
						</div>
						<div className="p-4 rounded-2xl bg-card border border-border flex items-center justify-center gap-4">
							<button
								type="button"
								onClick={() => {
									setIsPlayingPodcast(!isPlayingPodcast);
									toast.info(isPlayingPodcast ? "Đã tạm dừng audio" : "Đang phát Audio Brief...");
								}}
								className="w-12 h-12 rounded-full bg-emerald-600 hover:bg-emerald-500 text-white flex items-center justify-center transition-transform hover:scale-105 shadow-md cursor-pointer"
							>
								<Play className={cn("w-5 h-5 ml-0.5", isPlayingPodcast && "fill-current")} />
							</button>
							<div className="text-left flex-1">
								<div className="text-xs font-semibold text-foreground">
									Bản tin nhanh BĐS Hà Nội
								</div>
								<div className="w-full bg-muted rounded-full h-1.5 mt-2 overflow-hidden">
									<div className="bg-emerald-500 h-1.5 rounded-full w-1/3" />
								</div>
								<div className="flex justify-between text-[10px] text-muted-foreground mt-1 font-mono">
									<span>01:12</span>
									<span>03:20</span>
								</div>
							</div>
						</div>
					</div>
				)}
			</div>
		</div>
	);
};

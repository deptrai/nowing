"use client";

import { CheckCircle, Flame, MessageCircle, Phone, Sparkles, Target, Zap } from "lucide-react";
import type React from "react";
import { useState } from "react";
import { cn } from "@/lib/utils";

export const ProductShowcaseTabs: React.FC = () => {
	const [activeTab, setActiveTab] = useState<"leads" | "enrich" | "viral">("leads");

	return (
		<section className="py-16 md:py-24 bg-slate-50/60 dark:bg-slate-900/40 border-y border-slate-200/80 dark:border-slate-800">
			<div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
				{/* Section Header */}
				<div className="text-center max-w-3xl mx-auto mb-12">
					<div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-100/70 dark:bg-emerald-950/70 text-emerald-800 dark:text-emerald-300 text-xs font-bold uppercase tracking-wider mb-3">
						<Sparkles className="w-3.5 h-3.5" />
						<span>Trải nghiệm sức mạnh trực quan</span>
					</div>
					<h2 className="text-3xl sm:text-4xl font-serif text-slate-900 dark:text-white tracking-tight">
						Từ một câu chat đến danh sách khách hàng chất lượng cao
					</h2>
					<p className="mt-3 text-base text-slate-600 dark:text-slate-400">
						Xem trực tiếp cách Nowing bóc tách dữ liệu đa kênh và hỗ trợ sales tiếp cận khách hàng
						trong chớp mắt.
					</p>
				</div>

				{/* Tab Nav Buttons */}
				<div className="flex justify-center mb-8">
					<div className="inline-flex p-1.5 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm">
						<button
							type="button"
							onClick={() => setActiveTab("leads")}
							className={cn(
								"flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs sm:text-sm font-semibold transition-all",
								activeTab === "leads"
									? "bg-emerald-600 text-white shadow-sm"
									: "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
							)}
						>
							<Target className="w-4 h-4" />
							<span>1. Bảng Leads Realtime</span>
						</button>

						<button
							type="button"
							onClick={() => setActiveTab("enrich")}
							className={cn(
								"flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs sm:text-sm font-semibold transition-all",
								activeTab === "enrich"
									? "bg-emerald-600 text-white shadow-sm"
									: "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
							)}
						>
							<Zap className="w-4 h-4" />
							<span>2. Giải mã SĐT 3 Tầng</span>
						</button>

						<button
							type="button"
							onClick={() => setActiveTab("viral")}
							className={cn(
								"flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs sm:text-sm font-semibold transition-all",
								activeTab === "viral"
									? "bg-emerald-600 text-white shadow-sm"
									: "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
							)}
						>
							<Flame className="w-4 h-4" />
							<span>3. Social Co-pilot Viral</span>
						</button>
					</div>
				</div>

				{/* Tab 1 Content: Live Table Matrix Preview */}
				{activeTab === "leads" && (
					<div className="bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xl overflow-hidden animate-in fade-in-50 duration-200">
						{/* Table Header Bar */}
						<div className="px-5 py-3.5 bg-slate-50 dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex flex-wrap items-center justify-between gap-3 text-xs">
							<div className="flex items-center gap-2">
								<span className="flex h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse" />
								<span className="font-bold text-slate-800 dark:text-slate-200">
									Bảng 1: Môi giới BĐS Nhà phố Thủ Đức (50 leads)
								</span>
								<span className="px-2 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 font-semibold text-[11px]">
									Live Zero-Cache Sync
								</span>
							</div>

							<div className="flex items-center gap-2">
								<span className="text-slate-400">Đã lọc DNC & Khử trùng</span>
							</div>
						</div>

						{/* Table Content */}
						<div className="overflow-x-auto">
							<table className="w-full text-left text-xs sm:text-sm border-collapse">
								<thead>
									<tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 text-slate-500 dark:text-slate-400">
										<th className="py-3 px-4 font-semibold">Khách hàng / Tiêu đề</th>
										<th className="py-3 px-4 font-semibold">Nguồn cào</th>
										<th className="py-3 px-4 font-semibold">SĐT Giải mã</th>
										<th className="py-3 px-4 font-semibold">Fit Score</th>
										<th className="py-3 px-4 font-semibold text-right">Tiếp cận 1-Click</th>
									</tr>
								</thead>
								<tbody className="divide-y divide-slate-100 dark:divide-slate-800/80">
									<tr className="hover:bg-emerald-50/30 dark:hover:bg-emerald-950/20 transition-colors">
										<td className="py-3.5 px-4">
											<div className="font-semibold text-slate-900 dark:text-white">
												Nguyễn Văn Hùng (Môi giới chuyên nhà phố)
											</div>
											<div className="text-xs text-slate-500">
												Bán nhà mặt tiền Đặng Văn Bi, Thủ Đức (8.5 tỷ)
											</div>
										</td>
										<td className="py-3.5 px-4">
											<span className="px-2 py-0.5 rounded bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300 text-xs font-medium border border-blue-200/50">
												Batdongsan.com.vn
											</span>
										</td>
										<td className="py-3.5 px-4">
											<span className="font-mono font-bold text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60 px-2 py-1 rounded border border-emerald-200/60">
												0908 123 456
											</span>
										</td>
										<td className="py-3.5 px-4">
											<div className="inline-flex items-center gap-1 font-semibold text-emerald-600">
												<span>96%</span>
												<span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 font-bold">
													Rất khớp
												</span>
											</div>
										</td>
										<td className="py-3.5 px-4 text-right">
											<button
												type="button"
												className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold shadow-xs transition-transform active:scale-95"
											>
												<MessageCircle className="w-3.5 h-3.5" />
												<span>Nhắn Zalo</span>
											</button>
										</td>
									</tr>

									<tr className="hover:bg-emerald-50/30 dark:hover:bg-emerald-950/20 transition-colors">
										<td className="py-3.5 px-4">
											<div className="font-semibold text-slate-900 dark:text-white">
												Trần Thị Thu Mai (Chính chủ đăng tin)
											</div>
											<div className="text-xs text-slate-500">
												Cần bán gấp nhà hẻm xe hơi Võ Văn Ngân
											</div>
										</td>
										<td className="py-3.5 px-4">
											<span className="px-2 py-0.5 rounded bg-orange-50 text-orange-700 dark:bg-orange-950 dark:text-orange-300 text-xs font-medium border border-orange-200/50">
												Chợ Tốt Nhà
											</span>
										</td>
										<td className="py-3.5 px-4">
											<span className="font-mono font-bold text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60 px-2 py-1 rounded border border-emerald-200/60">
												0982 456 789
											</span>
										</td>
										<td className="py-3.5 px-4">
											<div className="inline-flex items-center gap-1 font-semibold text-emerald-600">
												<span>92%</span>
												<span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 font-bold">
													Khớp cao
												</span>
											</div>
										</td>
										<td className="py-3.5 px-4 text-right">
											<button
												type="button"
												className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold shadow-xs transition-transform active:scale-95"
											>
												<MessageCircle className="w-3.5 h-3.5" />
												<span>Nhắn Zalo</span>
											</button>
										</td>
									</tr>

									<tr className="hover:bg-emerald-50/30 dark:hover:bg-emerald-950/20 transition-colors">
										<td className="py-3.5 px-4">
											<div className="font-semibold text-slate-900 dark:text-white">
												Lê Hoàng Nam (Founder - Công ty Công nghệ)
											</div>
											<div className="text-xs text-slate-500">
												Đang tuyển dụng 5 Senior Node.js & ReactJS
											</div>
										</td>
										<td className="py-3.5 px-4">
											<span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300 text-xs font-medium border border-emerald-200/50">
												TopCV & Masothue
											</span>
										</td>
										<td className="py-3.5 px-4">
											<span className="font-mono font-bold text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60 px-2 py-1 rounded border border-emerald-200/60">
												0912 888 999
											</span>
										</td>
										<td className="py-3.5 px-4">
											<div className="inline-flex items-center gap-1 font-semibold text-emerald-600">
												<span>95%</span>
												<span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 font-bold">
													Rất khớp
												</span>
											</div>
										</td>
										<td className="py-3.5 px-4 text-right">
											<button
												type="button"
												className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold shadow-xs transition-transform active:scale-95"
											>
												<Phone className="w-3.5 h-3.5" />
												<span>Gọi điện</span>
											</button>
										</td>
									</tr>
								</tbody>
							</table>
						</div>
					</div>
				)}

				{/* Tab 2 Content: 3-Tier Waterfall Engine */}
				{activeTab === "enrich" && (
					<div className="bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 sm:p-8 shadow-xl animate-in fade-in-50 duration-200">
						<div className="grid grid-cols-1 md:grid-cols-3 gap-6">
							<div className="p-5 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
								<div className="w-8 h-8 rounded-lg bg-emerald-100 text-emerald-700 font-bold flex items-center justify-center mb-3">
									1
								</div>
								<h3 className="font-bold text-slate-900 dark:text-white text-base mb-1">
									Tier 1: Token Pool Xoay Vòng
								</h3>
								<p className="text-xs text-slate-500 leading-relaxed">
									Sử dụng Redis Mutex Token Pool xoay vòng giải mã số điện thoại bị ẩn trên
									Batdongsan và Muaban.
								</p>
							</div>

							<div className="p-5 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
								<div className="w-8 h-8 rounded-lg bg-teal-100 text-teal-700 font-bold flex items-center justify-center mb-3">
									2
								</div>
								<h3 className="font-bold text-slate-900 dark:text-white text-base mb-1">
									Tier 2: Chợ Tốt Mobile API
								</h3>
								<p className="text-xs text-slate-500 leading-relaxed">
									Fallback gọi API trực tiếp với UUID device giả lập để trích xuất số điện thoại gốc
									của người đăng.
								</p>
							</div>

							<div className="p-5 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
								<div className="w-8 h-8 rounded-lg bg-blue-100 text-blue-700 font-bold flex items-center justify-center mb-3">
									3
								</div>
								<h3 className="font-bold text-slate-900 dark:text-white text-base mb-1">
									Tier 3: Zalo UID & Xác thực Nhà mạng
								</h3>
								<p className="text-xs text-slate-500 leading-relaxed">
									Kiểm tra đầu số Viettel/VNPT/Mobi và tra cứu Zalo UID để đảm bảo 100% số máy đang
									hoạt động.
								</p>
							</div>
						</div>
					</div>
				)}

				{/* Tab 3 Content: Viral Social Outbound Co-pilot */}
				{activeTab === "viral" && (
					<div className="bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 sm:p-8 shadow-xl animate-in fade-in-50 duration-200">
						<div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-center">
							<div>
								<span className="px-2.5 py-1 rounded bg-amber-100 text-amber-800 font-semibold text-xs mb-2 inline-block">
									Phát hiện bài viết Outlier (Tương tác gấp 5x trung bình)
								</span>
								<h3 className="text-xl font-bold text-slate-900 dark:text-white mb-2">
									Học văn phong & Tái tạo bài đăng Viral
								</h3>
								<p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 mb-4 leading-relaxed">
									AI tự động phân tích cấu trúc câu, Hook giữ chân người đọc từ các bài viết bán
									nhà/tuyển dụng hot nhất trên Facebook & Twitter, sau đó viết lại độc bản cho bạn.
								</p>
								<div className="space-y-2 text-xs text-slate-700 dark:text-slate-300">
									<div className="flex items-center gap-2">
										<CheckCircle className="w-4 h-4 text-emerald-500" />
										<span>Phân loại Hook: Tương phản, Câu chuyện cảm xúc, Danh sách giá trị</span>
									</div>
									<div className="flex items-center gap-2">
										<CheckCircle className="w-4 h-4 text-emerald-500" />
										<span>
											Kiểm soát Human-in-the-loop: Không tự động đăng, người dùng toàn quyền duyệt
										</span>
									</div>
								</div>
							</div>

							<div className="p-4 rounded-xl bg-slate-900 text-slate-100 font-mono text-xs border border-slate-800">
								<div className="text-emerald-400 font-bold mb-2">
									✨ AI Generated Hook (Văn phong: Chuyên gia BĐS)
								</div>
								<div className="text-slate-300 leading-relaxed">
									&quot;Nhiều người nghĩ mua nhà Thủ Đức giá 8 tỷ bây giờ là muộn. Nhưng đây là 3 lý
									do vì sao tuyến metro sắp thông sẽ thay đổi toàn bộ thị trường...&quot;
								</div>
							</div>
						</div>
					</div>
				)}
			</div>
		</section>
	);
};

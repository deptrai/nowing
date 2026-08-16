import { Check, ShieldCheck } from "lucide-react";
import Link from "next/link";
import type React from "react";

export const NowingPricingSection: React.FC = () => {
	return (
		<section
			className="py-16 md:py-24 bg-slate-50/70 dark:bg-slate-900/40 border-t border-slate-200/80 dark:border-slate-800"
			id="pricing"
		>
			<div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
				<div className="text-center max-w-3xl mx-auto mb-14">
					<span className="px-3 py-1 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 font-bold text-xs uppercase tracking-wider">
						Mô Hình Bảng Giá $0 Minh Bạch
					</span>
					<h2 className="mt-3 text-3xl sm:text-4xl font-serif text-slate-900 dark:text-white tracking-tight">
						Dùng AI & Tạo chiến dịch MIỄN PHÍ. Chỉ trả tiền khi có SĐT thật.
					</h2>
					<p className="mt-3 text-base text-slate-600 dark:text-slate-400">
						Không phí duy trì hàng tháng. Không giam tiền. Hoàn 100% credit tự động nếu số điện
						thoại không liên lạc được.
					</p>
				</div>

				<div className="grid grid-cols-1 md:grid-cols-3 gap-8">
					{/* Plan 1: Free $0 */}
					<div className="p-6 sm:p-8 rounded-2xl bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between">
						<div>
							<span className="text-xs font-bold uppercase tracking-wider text-slate-500">
								Miễn Phí
							</span>
							<h3 className="text-xl font-bold text-slate-900 dark:text-white mt-1">
								AI Co-pilot Core
							</h3>
							<div className="mt-4 mb-6">
								<span className="text-4xl font-extrabold text-slate-900 dark:text-white font-mono">
									0đ
								</span>
								<span className="text-slate-400 text-xs ml-1">/ trọn đời</span>
							</div>

							<ul className="space-y-3 text-xs sm:text-sm text-slate-600 dark:text-slate-400">
								<li className="flex items-center gap-2">
									<Check className="w-4 h-4 text-emerald-500 flex-shrink-0" />
									<span>Chat AI không giới hạn câu hỏi</span>
								</li>
								<li className="flex items-center gap-2">
									<Check className="w-4 h-4 text-emerald-500 flex-shrink-0" />
									<span>Cào và tạo tối đa 5 bảng Leads</span>
								</li>
								<li className="flex items-center gap-2">
									<Check className="w-4 h-4 text-emerald-500 flex-shrink-0" />
									<span>Xuất CSV & Google Sheets</span>
								</li>
								<li className="flex items-center gap-2">
									<Check className="w-4 h-4 text-emerald-500 flex-shrink-0" />
									<span>Tặng sẵn 10 Credits khi đăng ký</span>
								</li>
							</ul>
						</div>

						<div className="mt-8">
							<Link
								href="/register"
								className="w-full inline-flex items-center justify-center py-2.5 px-4 rounded-xl border border-slate-300 dark:border-slate-700 font-semibold text-xs sm:text-sm text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-900 transition-colors"
							>
								Đăng ký Miễn phí
							</Link>
						</div>
					</div>

					{/* Plan 2: Pay-as-you-go Credits (Featured) */}
					<div className="relative p-6 sm:p-8 rounded-2xl bg-white dark:bg-slate-950 border-2 border-emerald-500 shadow-xl shadow-emerald-500/10 flex flex-col justify-between">
						<div className="absolute -top-3.5 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-emerald-600 text-white text-[11px] font-bold uppercase tracking-wider shadow-sm">
							Phổ biến nhất
						</div>

						<div>
							<span className="text-xs font-bold uppercase tracking-wider text-emerald-600">
								Theo Nhu Cầu
							</span>
							<h3 className="text-xl font-bold text-slate-900 dark:text-white mt-1">
								Gói Credits Săn Lead
							</h3>
							<div className="mt-4 mb-6">
								<span className="text-4xl font-extrabold text-emerald-600 font-mono">1.500đ</span>
								<span className="text-slate-400 text-xs ml-1">/ SĐT mở khóa</span>
							</div>

							<ul className="space-y-3 text-xs sm:text-sm text-slate-600 dark:text-slate-400">
								<li className="flex items-center gap-2 font-medium text-slate-900 dark:text-white">
									<Check className="w-4 h-4 text-emerald-500 flex-shrink-0" />
									<span>Giải mã SĐT Batdongsan, Chợ Tốt</span>
								</li>
								<li className="flex items-center gap-2">
									<Check className="w-4 h-4 text-emerald-500 flex-shrink-0" />
									<span>Chấm điểm Fit Score tự động</span>
								</li>
								<li className="flex items-center gap-2">
									<Check className="w-4 h-4 text-emerald-500 flex-shrink-0" />
									<span>Nhắn Zalo 1-Click qua Assisted Link</span>
								</li>
								<li className="flex items-center gap-2 font-semibold text-emerald-600">
									<ShieldCheck className="w-4 h-4 text-emerald-500 flex-shrink-0" />
									<span>Auto-refund 100% nếu số rác</span>
								</li>
							</ul>
						</div>

						<div className="mt-8">
							<Link
								href="/dashboard"
								className="w-full inline-flex items-center justify-center py-2.5 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs sm:text-sm shadow-md transition-all"
							>
								Nạp Credits & Dùng ngay
							</Link>
						</div>
					</div>

					{/* Plan 3: Enterprise / Agency */}
					<div className="p-6 sm:p-8 rounded-2xl bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between">
						<div>
							<span className="text-xs font-bold uppercase tracking-wider text-slate-500">
								Doanh Nghiệp
							</span>
							<h3 className="text-xl font-bold text-slate-900 dark:text-white mt-1">
								Agency & Scale
							</h3>
							<div className="mt-4 mb-6">
								<span className="text-3xl font-extrabold text-slate-900 dark:text-white font-mono">
									Tùy biến
								</span>
								<span className="text-slate-400 text-xs ml-1">/ theo tháng</span>
							</div>

							<ul className="space-y-3 text-xs sm:text-sm text-slate-600 dark:text-slate-400">
								<li className="flex items-center gap-2">
									<Check className="w-4 h-4 text-emerald-500 flex-shrink-0" />
									<span>Dedicated Proxy Pool & Scraper riêng</span>
								</li>
								<li className="flex items-center gap-2">
									<Check className="w-4 h-4 text-emerald-500 flex-shrink-0" />
									<span>Tích hợp CRM trực tiếp (HubSpot, Lark)</span>
								</li>
								<li className="flex items-center gap-2">
									<Check className="w-4 h-4 text-emerald-500 flex-shrink-0" />
									<span>Quản trị phân quyền đa nhân viên</span>
								</li>
								<li className="flex items-center gap-2">
									<Check className="w-4 h-4 text-emerald-500 flex-shrink-0" />
									<span>Chiết khấu nạp Credit tới 30%</span>
								</li>
							</ul>
						</div>

						<div className="mt-8">
							<Link
								href="/contact"
								className="w-full inline-flex items-center justify-center py-2.5 px-4 rounded-xl border border-slate-300 dark:border-slate-700 font-semibold text-xs sm:text-sm text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-900 transition-colors"
							>
								Liên hệ tư vấn
							</Link>
						</div>
					</div>
				</div>
			</div>
		</section>
	);
};

import { Heart, ShieldCheck } from "lucide-react";
import Link from "next/link";
import type React from "react";
import { OrigamiLogo } from "@/components/origami/OrigamiLogo";

export const OrigamiFooter: React.FC = () => {
	return (
		<footer className="bg-slate-900 text-slate-300 py-16 border-t border-slate-800">
			<div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
				<div className="grid grid-cols-1 md:grid-cols-5 gap-10 pb-12 border-b border-slate-800">
					{/* Brand column */}
					<div className="md:col-span-2 space-y-4">
						<OrigamiLogo size={36} showText={true} textClassName="text-white" />
						<p className="text-xs sm:text-sm text-slate-400 max-w-sm leading-relaxed">
							Nowing là nền tảng AI Lead Intelligence hàng đầu Việt Nam. Tự động hóa săn khách hàng,
							giải mã số điện thoại và tiếp cận đa kênh Zalo & Email.
						</p>
						<div className="flex items-center gap-2 text-xs text-emerald-400">
							<ShieldCheck className="w-4 h-4" />
							<span>Tuân thủ Nghị định 91/2020/NĐ-CP & Nghị định 13/2023/NĐ-CP</span>
						</div>
					</div>

					{/* Links Col 1: Sản phẩm */}
					<div className="space-y-3">
						<h4 className="text-xs font-bold uppercase tracking-wider text-white">Sản phẩm</h4>
						<ul className="space-y-2 text-xs text-slate-400">
							<li>
								<Link href="/dashboard" className="hover:text-emerald-400 transition-colors">
									Săn khách hàng (Lead Gen)
								</Link>
							</li>
							<li>
								<Link href="/dashboard" className="hover:text-emerald-400 transition-colors">
									Làm giàu SĐT 3 Tầng
								</Link>
							</li>
							<li>
								<Link href="/dashboard" className="hover:text-emerald-400 transition-colors">
									Social Outbound Co-pilot
								</Link>
							</li>
							<li>
								<Link href="/pricing" className="hover:text-emerald-400 transition-colors">
									Bảng giá $0 & Credits
								</Link>
							</li>
						</ul>
					</div>

					{/* Links Col 2: Ngành dọc */}
					<div className="space-y-3">
						<h4 className="text-xs font-bold uppercase tracking-wider text-white">Ngành dọc</h4>
						<ul className="space-y-2 text-xs text-slate-400">
							<li>
								<Link href="/dashboard" className="hover:text-emerald-400 transition-colors">
									Bất Động Sản & Môi Giới
								</Link>
							</li>
							<li>
								<Link href="/dashboard" className="hover:text-emerald-400 transition-colors">
									Tuyển Dụng & Săn Đầu Người
								</Link>
							</li>
							<li>
								<Link href="/dashboard" className="hover:text-emerald-400 transition-colors">
									Bán Sỉ & Phân Phối B2B
								</Link>
							</li>
							<li>
								<Link href="/dashboard" className="hover:text-emerald-400 transition-colors">
									Đấu Thầu & Mua Sắm Công
								</Link>
							</li>
						</ul>
					</div>

					{/* Links Col 3: Đối tác & Pháp lý */}
					<div className="space-y-3">
						<h4 className="text-xs font-bold uppercase tracking-wider text-white">
							Đối tác & Pháp lý
						</h4>
						<ul className="space-y-2 text-xs text-slate-400">
							<li>
								<Link
									href="/partners"
									className="hover:text-emerald-400 transition-colors text-emerald-400 font-semibold"
								>
									Chương trình Đại lý 15%
								</Link>
							</li>
							<li>
								<Link href="/terms" className="hover:text-emerald-400 transition-colors">
									Điều khoản dịch vụ
								</Link>
							</li>
							<li>
								<Link href="/privacy" className="hover:text-emerald-400 transition-colors">
									Chính sách bảo mật PII
								</Link>
							</li>
							<li>
								<Link href="/contact" className="hover:text-emerald-400 transition-colors">
									Liên hệ hỗ trợ
								</Link>
							</li>
						</ul>
					</div>
				</div>

				<div className="pt-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-500">
					<div>© {new Date().getFullYear()} Nowing Lead Intelligence. All rights reserved.</div>
					<div className="flex items-center gap-1">
						<span>Phát triển với</span>
						<Heart className="w-3.5 h-3.5 text-rose-500 fill-rose-500" />
						<span>cho cộng đồng doanh nghiệp Việt Nam</span>
					</div>
				</div>
			</div>
		</footer>
	);
};

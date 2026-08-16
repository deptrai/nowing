import { Check } from "lucide-react";
import type React from "react";

export const NowingCompareTable: React.FC = () => {
	const FEATURES = [
		{
			title: "Nguồn dữ liệu BĐS & Doanh nghiệp Việt Nam",
			nowing: "15+ nguồn nội địa (Batdongsan, Chợ Tốt, TopCV, Masothue...)",
			apollo: "Rất ít data Việt Nam (chủ yếu US/EU)",
			clay: "Không có tích hợp nguồn VN",
			manual: "Phải mở 10 tab copy-paste tay",
		},
		{
			title: "Giải mã số điện thoại chính chủ",
			nowing: "3 Tầng Waterfall + Zalo UID tự động",
			apollo: "Chỉ có email, ít SĐT VN",
			clay: "Tính phí $0.50/lead qua bên thứ 3",
			manual: "Gõ tay từng số mất hàng giờ",
		},
		{
			title: "Chi phí Chat AI & Khởi tạo chiến dịch",
			nowing: "MIỄN PHÍ 100% ($0)",
			apollo: "Từ $49/tháng/người",
			clay: "Từ $149/tháng",
			manual: "Tốn tiền thuê nhân sự cào data",
		},
		{
			title: "Tự động hoàn tiền nếu SĐT không liên lạc được",
			nowing: "Hoàn 100% tự động trong 24h",
			apollo: "Không hỗ trợ",
			clay: "Không hỗ trợ",
			manual: "Không có",
		},
		{
			title: "Hỗ trợ Zalo Assisted Deep-Link & Telegram",
			nowing: "1-Click nhắn Zalo không sợ khóa nick",
			apollo: "Chỉ gửi Email & LinkedIn",
			clay: "Không hỗ trợ Zalo",
			manual: "Mở app Zalo tìm thủ công",
		},
	];

	return (
		<section className="py-16 md:py-24 bg-white dark:bg-slate-950">
			<div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
				<div className="text-center max-w-3xl mx-auto mb-12">
					<span className="px-3 py-1 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 font-bold text-xs uppercase tracking-wider">
						So Sánh Trực Diện
					</span>
					<h2 className="mt-3 text-3xl sm:text-4xl font-serif text-slate-900 dark:text-white tracking-tight">
						Vì sao Nowing vượt trội tại thị trường Việt Nam?
					</h2>
				</div>

				<div className="overflow-x-auto">
					<table className="w-full text-left text-xs sm:text-sm border-collapse rounded-2xl overflow-hidden shadow-lg border border-slate-200 dark:border-slate-800">
						<thead>
							<tr className="bg-slate-50 dark:bg-slate-900 text-slate-700 dark:text-slate-200 border-b border-slate-200 dark:border-slate-800">
								<th className="py-4 px-5 font-bold w-1/3">Tính năng & Trải nghiệm</th>
								<th className="py-4 px-5 font-extrabold text-emerald-700 dark:text-emerald-400 bg-emerald-50/70 dark:bg-emerald-950/40 w-1/4">
									🌿 Nowing Lead Intelligence
								</th>
								<th className="py-4 px-5 font-semibold text-slate-500 w-1/6">Apollo.io</th>
								<th className="py-4 px-5 font-semibold text-slate-500 w-1/6">Clay.com</th>
							</tr>
						</thead>
						<tbody className="divide-y divide-slate-100 dark:divide-slate-800/80 bg-white dark:bg-slate-950">
							{FEATURES.map((item) => (
								<tr key={item.title} className="hover:bg-slate-50/50 dark:hover:bg-slate-900/30">
									<td className="py-4 px-5 font-medium text-slate-900 dark:text-slate-100">
										{item.title}
									</td>
									<td className="py-4 px-5 font-bold text-emerald-700 dark:text-emerald-300 bg-emerald-50/40 dark:bg-emerald-950/20">
										<div className="flex items-start gap-2">
											<Check className="w-4 h-4 text-emerald-600 mt-0.5 flex-shrink-0" />
											<span>{item.nowing}</span>
										</div>
									</td>
									<td className="py-4 px-5 text-slate-500 dark:text-slate-400">{item.apollo}</td>
									<td className="py-4 px-5 text-slate-500 dark:text-slate-400">{item.clay}</td>
								</tr>
							))}
						</tbody>
					</table>
				</div>
			</div>
		</section>
	);
};

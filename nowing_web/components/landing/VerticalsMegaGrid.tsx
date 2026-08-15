import {
	ArrowRight,
	Briefcase,
	Building2,
	GraduationCap,
	HardHat,
	HeartPulse,
	Landmark,
	ShoppingBag,
	Store,
	Truck,
	Users,
	Utensils,
	Wheat,
} from "lucide-react";
import Link from "next/link";
import type React from "react";

const VERTICALS = [
	{
		icon: Building2,
		title: "Bất Động Sản & Môi Giới",
		description:
			"Cào chính chủ & môi giới từ Batdongsan, Chợ Tốt, Meeyland kèm số điện thoại giải mã.",
		tags: ["Batdongsan", "Chợ Tốt Nhà", "Zalo BĐS"],
		color: "text-emerald-600 bg-emerald-50 dark:bg-emerald-950/60",
	},
	{
		icon: Users,
		title: "Tuyển Dụng & Săn Đầu Người (HR)",
		description:
			"Tìm doanh nghiệp đang mở rộng quy mô, CTO, HR Manager từ TopCV, ITviec & LinkedIn.",
		tags: ["TopCV", "ITviec", "Headhunter"],
		color: "text-blue-600 bg-blue-50 dark:bg-blue-950/60",
	},
	{
		icon: ShoppingBag,
		title: "Bán Sỉ & Phân Phối B2B",
		description:
			"Quét các tổng kho, đại lý sỉ chợ Ninh Hiệp, Tân Bình, Đồng Xuân và nhóm sỉ Facebook.",
		tags: ["Facebook Groups", "Zalo sỉ", "Đại lý"],
		color: "text-amber-600 bg-amber-50 dark:bg-amber-950/60",
	},
	{
		icon: Utensils,
		title: "F&B, Nhà Hàng & Nhượng Quyền",
		description:
			"Tìm chủ quán cafe, nhà hàng chuẩn bị mở mới hoặc sang nhượng mặt bằng kinh doanh.",
		tags: ["Mặt bằng F&B", "Chủ quán", "ShopeeFood"],
		color: "text-orange-600 bg-orange-50 dark:bg-orange-950/60",
	},
	{
		icon: Truck,
		title: "Logistics, Vận Tải & Kho Bãi",
		description:
			"Săn đầu mối chủ hàng xuất nhập khẩu, đơn vị cần thuê kho xưởng và chành xe toàn quốc.",
		tags: ["Kho bãi", "Chủ hàng", "Xuất nhập khẩu"],
		color: "text-indigo-600 bg-indigo-50 dark:bg-indigo-950/60",
	},
	{
		icon: GraduationCap,
		title: "Giáo Dục, Đào Tạo & Du Học",
		description:
			"Tìm phụ huynh có nhu cầu, học viên tiềm năng và đối tác tuyển sinh trung tâm ngoại ngữ.",
		tags: ["Trung tâm", "Học viên", "Du học"],
		color: "text-purple-600 bg-purple-50 dark:bg-purple-950/60",
	},
	{
		icon: HeartPulse,
		title: "Y Tế, Thẩm Mỹ & Phòng Khám",
		description:
			"Dữ liệu bác sĩ, chủ spa, thẩm mỹ viện và phòng khám nha khoa trên khắp 63 tỉnh thành.",
		tags: ["Phòng khám", "Chủ Spa", "Bác sĩ"],
		color: "text-rose-600 bg-rose-50 dark:bg-rose-950/60",
	},
	{
		icon: Store,
		title: "Thương Mại Điện Tử & TikTok Shop",
		description:
			"Trích xuất danh sách Top nhà bán hàng, shop nghìn đơn và livestreamer thịnh hành.",
		tags: ["TikTok Shop", "Shopee Top", "KOC"],
		color: "text-pink-600 bg-pink-50 dark:bg-pink-950/60",
	},
	{
		icon: HardHat,
		title: "Xây Dựng & Đấu Thầu Mua Sắm Công",
		description:
			"Theo dõi các chủ đầu tư vừa mở thầu, nhà thầu trúng gói thầu xây lắp trên muasamcong.",
		tags: ["Mua Sắm Công", "Nhà thầu", "Vật liệu"],
		color: "text-cyan-600 bg-cyan-50 dark:bg-cyan-950/60",
	},
	{
		icon: Landmark,
		title: "Tài Chính, Bảo Hiểm & Đầu Tư",
		description:
			"Tiếp cận danh sách khách hàng có thu nhập cao, nhà đầu tư chứng khoán và đại lý bảo hiểm.",
		tags: ["Môi giới chứng khoán", "Đại lý BHNT"],
		color: "text-teal-600 bg-teal-50 dark:bg-teal-950/60",
	},
	{
		icon: Briefcase,
		title: "Dịch Vụ Doanh Nghiệp & Pháp Lý",
		description:
			"Tìm 10.000+ doanh nghiệp mới thành lập mỗi tháng từ Masothue & Cổng ĐKKD Quốc gia.",
		tags: ["Masothue", "ĐKKD", "DN mới"],
		color: "text-slate-600 bg-slate-100 dark:bg-slate-800",
	},
	{
		icon: Wheat,
		title: "Nông Nghiệp, Thủy Sản & Xuất Khẩu",
		description:
			"Đầu mối hợp tác xã, chủ vựa nông sản, doanh nghiệp chế biến xuất khẩu tôm cá miền Tây.",
		tags: ["Hợp tác xã", "Xuất khẩu", "Chủ vựa"],
		color: "text-lime-600 bg-lime-50 dark:bg-lime-950/60",
	},
];

export const VerticalsMegaGrid: React.FC = () => {
	return (
		<section className="py-16 md:py-24 bg-white dark:bg-slate-950">
			<div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
				{/* Header */}
				<div className="text-center max-w-3xl mx-auto mb-14">
					<span className="px-3 py-1 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 font-bold text-xs uppercase tracking-wider">
						12 Ngành Dọc Chuyên Biệt
					</span>
					<h2 className="mt-3 text-3xl sm:text-4xl font-serif text-slate-900 dark:text-white tracking-tight">
						Thiết kế dành riêng cho thị trường Việt Nam
					</h2>
					<p className="mt-3 text-base text-slate-600 dark:text-slate-400">
						Mỗi ngành dọc đều có bộ lọc và nguồn dữ liệu đặc thù đã được cấu hình sẵn, không cần mất
						công cài đặt.
					</p>
				</div>

				{/* 12 Grid Cards */}
				<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
					{VERTICALS.map((item) => {
						const IconComp = item.icon;
						return (
							<div
								key={item.title}
								className="group relative p-6 rounded-2xl bg-slate-50/70 dark:bg-slate-900/60 border border-slate-200/80 dark:border-slate-800 hover:border-emerald-400/80 dark:hover:border-emerald-500/80 transition-all hover:shadow-lg hover:shadow-emerald-500/5 flex flex-col justify-between"
							>
								<div>
									<div
										className={`w-10 h-10 rounded-xl flex items-center justify-center mb-4 ${item.color}`}
									>
										<IconComp className="w-5 h-5" />
									</div>

									<h3 className="text-base font-bold text-slate-900 dark:text-white group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors">
										{item.title}
									</h3>

									<p className="mt-2 text-xs sm:text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
										{item.description}
									</p>
								</div>

								<div className="mt-4 pt-4 border-t border-slate-200/60 dark:border-slate-800 flex flex-wrap items-center gap-1.5">
									{item.tags.map((t) => (
										<span
											key={`${item.title}-${t}`}
											className="px-2 py-0.5 rounded-md bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 text-[11px] font-medium border border-slate-200 dark:border-slate-700"
										>
											{t}
										</span>
									))}
								</div>
							</div>
						);
					})}
				</div>

				{/* Bottom Note */}
				<div className="mt-10 text-center">
					<Link
						href="/dashboard"
						className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 dark:bg-emerald-600 dark:hover:bg-emerald-500 text-white text-xs sm:text-sm font-semibold shadow-sm transition-all"
					>
						<span>Bắt đầu săn khách hàng theo ngành của bạn</span>
						<ArrowRight className="w-4 h-4" />
					</Link>
				</div>
			</div>
		</section>
	);
};

"use client";

import { ChevronDown } from "lucide-react";
import type React from "react";
import { useState } from "react";
import { cn } from "@/lib/utils";

const FAQS = [
	{
		q: "Nowing lấy dữ liệu từ những nguồn nào?",
		a: "Nowing cào dữ liệu công khai từ hơn 15 nền tảng lớn nhất Việt Nam bao gồm: Batdongsan.com.vn, Chợ Tốt Nhà, TopCV, ITviec, Masothue, Cổng Đăng Ký Kinh Doanh Quốc Gia, Mua Sắm Công (Đấu thầu), các Hội nhóm Facebook và Kênh Telegram BĐS/việc làm.",
	},
	{
		q: "Cơ chế giải mã số điện thoại 3 tầng hoạt động thế nào?",
		a: "Khi phát hiện số điện thoại bị che (ví dụ 0908 123 *** trên Batdongsan hoặc Chợ Tốt), Nowing tự động kích hoạt Token Pool nội bộ hoặc API di động với định danh giả lập để trích xuất số đầy đủ. Sau đó, hệ thống xác thực đầu số nhà mạng và kiểm tra Zalo UID để đảm bảo số đang hoạt động trước khi ghi nhận cho bạn.",
	},
	{
		q: "Nếu số điện thoại cào được là số rác hoặc không liên lạc được thì sao?",
		a: "Nowing có chính sách Auto-Refund SLA 100%. Nếu bạn phát hiện số điện thoại sai hoặc thuê bao trong vòng 24 giờ, hệ thống sẽ tự động hoàn lại 100% credits vào ví tài khoản của bạn ngay lập tức.",
	},
	{
		q: "Nhắn Zalo qua Nowing có sợ bị khóa tài khoản không?",
		a: "Không! Nowing sử dụng cơ chế Zalo Assisted Deep-Link (zalo.me/{phone}). Khi bạn bấm nút 'Nhắn Zalo', hệ thống sẽ mở ứng dụng Zalo cá nhân của bạn với nội dung tin nhắn đã được AI soạn sẵn, bạn chỉ cần bấm Gửi. Toàn bộ thao tác diễn ra trên ứng dụng chính chủ của bạn nên tuyệt đối an toàn và tuân thủ điều khoản của Zalo.",
	},
	{
		q: "Chi phí sử dụng Nowing được tính như thế nào?",
		a: "Tất cả các tính năng Chat với AI, tìm kiếm bài viết, tạo bảng và xuất file đều MIỄN PHÍ trọn đời ($0). Bạn chỉ thanh toán tiền Credits khi mở khóa thành công một số điện thoại chính chủ (1.500 VNĐ / số) hoặc khi yêu cầu nghiên cứu chuyên sâu về một công ty.",
	},
];

export const NowingFaq: React.FC = () => {
	const [openIdx, setOpenIdx] = useState<number | null>(0);

	return (
		<section className="py-16 md:py-24 bg-white dark:bg-slate-950">
			<div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
				<div className="text-center max-w-2xl mx-auto mb-12">
					<span className="px-3 py-1 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 font-bold text-xs uppercase tracking-wider">
						Giải Đáp Thắc Mắc
					</span>
					<h2 className="mt-3 text-3xl sm:text-4xl font-serif text-slate-900 dark:text-white tracking-tight">
						Câu hỏi thường gặp
					</h2>
				</div>

				<div className="space-y-4">
					{FAQS.map((faq, index) => {
						const isOpen = openIdx === index;
						return (
							<div
								key={faq.q}
								className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 overflow-hidden transition-colors"
							>
								<button
									type="button"
									onClick={() => setOpenIdx(isOpen ? null : index)}
									className="w-full py-4 px-6 text-left flex items-center justify-between gap-4 font-bold text-sm sm:text-base text-slate-900 dark:text-white"
								>
									<span>{faq.q}</span>
									<ChevronDown
										className={cn(
											"w-4 h-4 text-slate-400 transition-transform duration-200",
											isOpen && "rotate-180 text-emerald-600"
										)}
									/>
								</button>
								{isOpen && (
									<div className="px-6 pb-4 pt-1 text-xs sm:text-sm text-slate-600 dark:text-slate-300 leading-relaxed border-t border-slate-200/50 dark:border-slate-800/50 animate-in fade-in-50 duration-150">
										{faq.a}
									</div>
								)}
							</div>
						);
					})}
				</div>
			</div>
		</section>
	);
};

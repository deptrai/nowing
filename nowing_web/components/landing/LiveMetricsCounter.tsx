import type React from "react";

export const LiveMetricsCounter: React.FC = () => {
	return (
		<section className="py-12 bg-white dark:bg-slate-950 border-b border-slate-200/80 dark:border-slate-800">
			<div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
				<div className="grid grid-cols-2 md:grid-cols-4 gap-6 text-center">
					<div className="p-4 rounded-xl">
						<div className="text-3xl sm:text-4xl font-extrabold text-slate-900 dark:text-white font-mono tracking-tight">
							95%
						</div>
						<div className="text-xs sm:text-sm font-semibold text-emerald-600 dark:text-emerald-400 mt-1">
							SĐT Chính Chủ Xác Thực
						</div>
						<p className="text-xs text-slate-400 mt-1">Qua 3 tầng Waterfall & Zalo</p>
					</div>

					<div className="p-4 rounded-xl">
						<div className="text-3xl sm:text-4xl font-extrabold text-slate-900 dark:text-white font-mono tracking-tight">
							&lt; 10s
						</div>
						<div className="text-xs sm:text-sm font-semibold text-emerald-600 dark:text-emerald-400 mt-1">
							Tốc Độ Cào Dữ Liệu
						</div>
						<p className="text-xs text-slate-400 mt-1">Từ lúc chat đến lúc có bảng</p>
					</div>

					<div className="p-4 rounded-xl">
						<div className="text-3xl sm:text-4xl font-extrabold text-slate-900 dark:text-white font-mono tracking-tight">
							15+
						</div>
						<div className="text-xs sm:text-sm font-semibold text-emerald-600 dark:text-emerald-400 mt-1">
							Nguồn Dữ Liệu Việt Nam
						</div>
						<p className="text-xs text-slate-400 mt-1">BĐS, Tuyển dụng, FB, Telegram</p>
					</div>

					<div className="p-4 rounded-xl">
						<div className="text-3xl sm:text-4xl font-extrabold text-emerald-600 dark:text-emerald-400 font-mono tracking-tight">
							0 VNĐ
						</div>
						<div className="text-xs sm:text-sm font-semibold text-slate-900 dark:text-white mt-1">
							Chi Phí AI Chat & Sequencer
						</div>
						<p className="text-xs text-slate-400 mt-1">Chỉ tính phí khi mở khóa SĐT</p>
					</div>
				</div>
			</div>
		</section>
	);
};

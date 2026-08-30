"use client";

import { Calendar, ChevronLeft, Loader2, Play, Rocket } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardFooter,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

import { VERTICAL_PRESETS } from "../constants";
import type { UseCampaignBuilderReturn } from "../types";

const EXPORT_OPTIONS = [
	{ value: "workspace", label: "Nowing SDR Lead Workbench (Mặc định)" },
	{ value: "crm", label: "Đẩy sang CRM (HubSpot / Salesforce / Lark Base)" },
	{ value: "lark", label: "Bắn thông báo qua Lark Webhook" },
	{ value: "sheets", label: "Tự động đồng bộ Google Sheets" },
] as const;

export function LaunchScheduleStep({ builder }: { builder: UseCampaignBuilderReturn }) {
	return (
		<div className="space-y-6">
			<div className="grid grid-cols-1 md:grid-cols-12 gap-6">
				<div className="md:col-span-7 space-y-6">
					<Card className="bg-zinc-900/60 border-zinc-800/80">
						<CardHeader>
							<CardTitle className="text-base flex items-center gap-2 text-zinc-100">
								<Rocket className="w-4 h-4 text-emerald-400" />
								<span>3. Thông Tin & Thiết Lập Lên Lịch</span>
							</CardTitle>
							<CardDescription className="text-xs text-zinc-400">
								Đặt tên chiến dịch và chọn lịch trình chạy tự động
							</CardDescription>
						</CardHeader>
						<CardContent className="space-y-4">
							<div>
								<Label className="text-xs text-zinc-300">Tên chiến dịch</Label>
								<Input
									value={builder.campaignName}
									onChange={(e) => builder.setCampaignName(e.target.value)}
									placeholder="Ví dụ: SDR Outbound Q3 - B2B Fintech"
									className="mt-1.5 text-xs bg-zinc-950/70 border-zinc-800 text-zinc-200"
								/>
							</div>

							<div>
								<Label className="text-xs text-zinc-300">Mô tả / Ghi chú mục tiêu</Label>
								<Textarea
									value={builder.campaignDesc}
									onChange={(e) => builder.setCampaignDesc(e.target.value)}
									rows={2}
									placeholder="Mục tiêu cung cấp 200 leads cho team SDR Hà Nội..."
									className="mt-1.5 text-xs bg-zinc-950/70 border-zinc-800 text-zinc-200"
								/>
							</div>

							<div>
								<Label className="text-xs text-zinc-300">Chế độ vận hành</Label>
								<div className="grid grid-cols-2 gap-3 mt-1.5">
									<button
										type="button"
										onClick={() => builder.setScheduleType("once")}
										className={`text-left p-3 rounded-xl border cursor-pointer transition-all ${
											builder.scheduleType === "once"
												? "bg-emerald-500/10 border-emerald-500/50 text-emerald-300"
												: "bg-zinc-950/40 border-zinc-800 text-zinc-400 hover:border-zinc-700"
										}`}
									>
										<div className="flex items-center gap-2 font-bold text-xs">
											<Play className="w-3.5 h-3.5" />
											<span>Chạy một lần ngay (Run Once)</span>
										</div>
										<p className="text-[10px] text-zinc-500 mt-1">
											Quét dữ liệu và kết thúc chu kỳ ngay
										</p>
									</button>

									<button
										type="button"
										onClick={() => builder.setScheduleType("recurring")}
										className={`text-left p-3 rounded-xl border cursor-pointer transition-all ${
											builder.scheduleType === "recurring"
												? "bg-emerald-500/10 border-emerald-500/50 text-emerald-300"
												: "bg-zinc-950/40 border-zinc-800 text-zinc-400 hover:border-zinc-700"
										}`}
									>
										<div className="flex items-center gap-2 font-bold text-xs">
											<Calendar className="w-3.5 h-3.5" />
											<span>Định kỳ tự động (Recurring)</span>
										</div>
										<p className="text-[10px] text-zinc-500 mt-1">
											Lặp lại quét hàng ngày hoặc hàng tuần
										</p>
									</button>
								</div>
							</div>

							{builder.scheduleType === "recurring" && (
								<div>
									<Label className="text-xs text-zinc-300">
										Biểu thức Lịch Cron (Cron Expression)
									</Label>
									<Input
										value={builder.cronExp}
										onChange={(e) => builder.setCronExp(e.target.value)}
										placeholder="0 8 * * 1-5 (Mỗi 8:00 sáng từ thứ 2 - thứ 6)"
										className="mt-1.5 text-xs bg-zinc-950/70 border-zinc-800 font-mono"
									/>
								</div>
							)}

							<div>
								<Label className="text-xs text-zinc-300">
									Đích đến dữ liệu Leads sau khi phân tích
								</Label>
								<select
									value={builder.exportDestination}
									onChange={(e) =>
										builder.setExportDestination(
											e.target.value as "workspace" | "crm" | "lark" | "sheets"
										)
									}
									className="w-full mt-1.5 px-3 py-2 text-xs rounded-lg bg-zinc-950/70 border border-zinc-800 text-zinc-200 focus:ring-1 focus:ring-emerald-500"
								>
									{EXPORT_OPTIONS.map((opt) => (
										<option key={opt.value} value={opt.value}>
											{opt.label}
										</option>
									))}
								</select>
							</div>
						</CardContent>
					</Card>
				</div>

				<div className="md:col-span-5">
					<Card className="bg-zinc-900/80 border-emerald-500/30 sticky top-6 shadow-2xl">
						<CardHeader className="pb-3 border-b border-zinc-800">
							<CardTitle className="text-sm font-bold text-zinc-100 flex items-center justify-between">
								<span>Tóm Tắt Cấu Hình Chiến Dịch</span>
								<Badge
									variant="outline"
									className="bg-emerald-500/10 text-emerald-400 border-emerald-500/30 text-[10px]"
								>
									Ready to Launch
								</Badge>
							</CardTitle>
						</CardHeader>
						<CardContent className="space-y-3 pt-4 text-xs">
							<div className="space-y-1">
								<span className="text-zinc-500 text-[11px]">Tên chiến dịch:</span>
								<p className="font-semibold text-zinc-200">
									{builder.campaignName || "Chưa đặt tên"}
								</p>
							</div>

							<div className="grid grid-cols-2 gap-2 pt-2 border-t border-zinc-800/60">
								<div>
									<span className="text-zinc-500 text-[11px]">Mẫu ngành:</span>
									<p className="font-medium text-emerald-400">
										{VERTICAL_PRESETS[builder.selectedTemplate].label}
									</p>
								</div>
								<div>
									<span className="text-zinc-500 text-[11px]">Mục tiêu số Lead:</span>
									<p className="font-bold text-zinc-200">{builder.expectedLeadsTarget} leads</p>
								</div>
							</div>

							<div className="pt-2 border-t border-zinc-800/60">
								<span className="text-zinc-500 text-[11px]">
									Nguồn quét ({builder.selectedSources.length}):
								</span>
								<div className="flex flex-wrap gap-1 mt-1">
									{builder.selectedSources.map((s) => (
										<Badge
											key={s}
											variant="secondary"
											className="text-[10px] bg-zinc-800 text-zinc-300"
										>
											{s}
										</Badge>
									))}
								</div>
							</div>

							<div className="grid grid-cols-2 gap-2 pt-2 border-t border-zinc-800/60">
								<div>
									<span className="text-zinc-500 text-[11px]">Ngưỡng Fit Score:</span>
									<p className="font-bold text-emerald-400">{builder.minFitScore}/100</p>
								</div>
								<div>
									<span className="text-zinc-500 text-[11px]">Ngưỡng Intent Score:</span>
									<p className="font-bold text-amber-400">{builder.minIntentScore}/100</p>
								</div>
							</div>

							<div className="pt-2 border-t border-zinc-800/60">
								<span className="text-zinc-500 text-[11px]">Loại trừ DNC:</span>
								<p className="text-zinc-300 font-medium">
									{builder.excludeDnc ? "✅ Bật (Loại trừ số cấm)" : "❌ Tắt"}
								</p>
							</div>

							<div className="p-3 rounded-xl bg-emerald-950/30 border border-emerald-800/40 mt-4">
								<div className="flex justify-between items-center text-xs">
									<span className="text-zinc-300">Tổng ngân sách dự toán:</span>
									<span className="font-mono font-bold text-emerald-400 text-sm">
										{builder.estimatedCost.toLocaleString("vi-VN")} đ
									</span>
								</div>
							</div>
						</CardContent>
						<CardFooter className="flex flex-col gap-2 pt-2 border-t border-zinc-800">
							<Button
								type="button"
								disabled={builder.isSubmitting}
								onClick={() => builder.handleSaveCampaign(true)}
								className="w-full bg-emerald-500 hover:bg-emerald-400 text-black text-xs font-bold py-2.5 shadow-lg shadow-emerald-500/20"
							>
								{builder.isSubmitting ? (
									<>
										<Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
										Đang khởi chạy...
									</>
								) : (
									<>
										<Rocket className="w-3.5 h-3.5 mr-1.5" />
										Kích Hoạt Chiến Dịch Ngay (Launch)
									</>
								)}
							</Button>
							<Button
								type="button"
								variant="ghost"
								disabled={builder.isSubmitting}
								onClick={() => builder.handleSaveCampaign(false)}
								className="w-full text-xs text-zinc-400 hover:text-zinc-200"
							>
								Lưu bản nháp (Save Draft)
							</Button>
						</CardFooter>
					</Card>
				</div>
			</div>

			<div className="flex justify-start pt-4 border-t border-zinc-800">
				<Button
					type="button"
					variant="outline"
					onClick={() => builder.setCurrentStep(2)}
					className="text-xs text-zinc-300 border-zinc-700"
				>
					<ChevronLeft className="w-3.5 h-3.5 mr-1" />
					Quay lại Bước 2
				</Button>
			</div>
		</div>
	);
}

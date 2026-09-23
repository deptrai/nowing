"use client";

import { ArrowRight, ChevronLeft, Coins, Filter, Globe, ShieldCheck, Zap } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";

import { AVAILABLE_SOURCES } from "../constants";
import type { UseCampaignBuilderReturn } from "../types";

export function SourceBudgetStep({ builder }: { builder: UseCampaignBuilderReturn }) {
	return (
		<div className="space-y-6">
			<Card className="bg-zinc-900/60 border-zinc-800/80">
				<CardHeader>
					<CardTitle className="text-base flex items-center gap-2 text-zinc-100">
						<Globe className="w-4 h-4 text-emerald-400" />
						<span>2. Nguồn Thu Thập Tín Hiệu (Multi-Source Adapters)</span>
					</CardTitle>
				</CardHeader>
				<CardContent>
					<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
						{AVAILABLE_SOURCES.map((src) => {
							const isSelected = builder.selectedSources.includes(src.id);
							return (
								<button
									key={src.id}
									type="button"
									onClick={() => builder.toggleSource(src.id)}
									className={`text-left p-4 rounded-xl border cursor-pointer transition-all ${
										isSelected
											? "bg-emerald-500/10 border-emerald-500/40 ring-1 ring-emerald-500/30"
											: "bg-zinc-950/40 border-zinc-800/80 hover:border-zinc-700"
									}`}
								>
									<div className="flex items-center justify-between mb-1.5">
										<div className="flex items-center gap-2 font-bold text-xs text-zinc-200">
											<span className="text-base">{src.icon}</span>
											<span>{src.name}</span>
										</div>
										<input
											type="checkbox"
											checked={isSelected}
											onChange={() => {}}
											className="rounded border-zinc-700 text-emerald-500 focus:ring-emerald-500"
										/>
									</div>
									<p className="text-[11px] text-zinc-400">{src.description}</p>
								</button>
							);
						})}
					</div>
				</CardContent>
			</Card>

			<div className="grid grid-cols-1 md:grid-cols-2 gap-6">
				<Card className="bg-zinc-900/60 border-zinc-800/80">
					<CardHeader>
						<CardTitle className="text-sm flex items-center gap-2 text-zinc-100">
							<Filter className="w-4 h-4 text-emerald-400" />
							<span>Ngưỡng Điểm Lọc (Quality Thresholds)</span>
						</CardTitle>
					</CardHeader>
					<CardContent className="space-y-6">
						<div className="space-y-2">
							<div className="flex justify-between text-xs">
								<span className="text-zinc-300">Ngưỡng Fit Score tối thiểu:</span>
								<span className="font-bold text-emerald-400">{builder.minFitScore}/100</span>
							</div>
							<Slider
								value={[builder.minFitScore]}
								onValueChange={(val) => builder.setMinFitScore(val[0])}
								max={100}
								min={0}
								step={5}
							/>
							<p className="text-[11px] text-zinc-500">
								Chỉ lưu các lead đạt độ khớp cao so với ICP doanh nghiệp đã định nghĩa
							</p>
						</div>

						<div className="space-y-2">
							<div className="flex justify-between text-xs">
								<span className="text-zinc-300">Ngưỡng Intent Score tối thiểu:</span>
								<span className="font-bold text-amber-400">{builder.minIntentScore}/100</span>
							</div>
							<Slider
								value={[builder.minIntentScore]}
								onValueChange={(val) => builder.setMinIntentScore(val[0])}
								max={100}
								min={0}
								step={5}
							/>
							<p className="text-[11px] text-zinc-500">
								Đánh giá độ nóng và tính cấp thiết của nhu cầu từ nội dung bài đăng
							</p>
						</div>

						<div className="space-y-2">
							<div className="flex justify-between text-xs">
								<span className="text-zinc-300">Số liên hệ tối đa mở khóa / 1 Lead:</span>
								<span className="font-bold text-blue-400">{builder.maxContactsPerLead} người</span>
							</div>
							<Slider
								value={[builder.maxContactsPerLead]}
								onValueChange={(val) => builder.setMaxContactsPerLead(val[0])}
								max={10}
								min={1}
								step={1}
							/>
						</div>
					</CardContent>
				</Card>

				<Card className="bg-zinc-900/60 border-zinc-800/80">
					<CardHeader>
						<CardTitle className="text-sm flex items-center gap-2 text-zinc-100">
							<Coins className="w-4 h-4 text-emerald-400" />
							<span>Mục Tiêu Số Lượng & Dự Toán Chi Phí</span>
						</CardTitle>
					</CardHeader>
					<CardContent className="space-y-4">
						<div>
							<Label className="text-xs text-zinc-300">Mục tiêu số lượng Lead cần quét</Label>
							<Input
								type="number"
								value={builder.expectedLeadsTarget}
								onChange={(e) =>
									builder.setExpectedLeadsTarget(Math.max(10, parseInt(e.target.value, 10) || 0))
								}
								className="mt-1.5 text-xs bg-zinc-950/70 border-zinc-800"
							/>
						</div>

						<div className="p-3.5 rounded-xl bg-zinc-950/60 border border-zinc-800/80 space-y-3">
							<div className="flex items-center justify-between">
								<div className="space-y-0.5">
									<div className="text-xs font-semibold text-zinc-200 flex items-center gap-1.5">
										<ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
										<span>Tự động loại bỏ danh sách Do-Not-Call (DNC)</span>
									</div>
									<p className="text-[11px] text-zinc-400">
										Tuân thủ Nghị định 91/2020/NĐ-CP & Luật Quảng cáo
									</p>
								</div>
								<Switch checked={builder.excludeDnc} onCheckedChange={builder.setExcludeDnc} />
							</div>

							<div className="flex items-center justify-between pt-2 border-t border-zinc-800/60">
								<div className="space-y-0.5">
									<div className="text-xs font-semibold text-zinc-200 flex items-center gap-1.5">
										<Zap className="w-3.5 h-3.5 text-amber-400" />
										<span>Tự động giải mã SĐT đã xác thực Zalo</span>
									</div>
									<p className="text-[11px] text-zinc-400">
										Mở khóa số phone hợp lệ ngay khi quét thấy
									</p>
								</div>
								<Switch
									checked={builder.autoUnlockPhones}
									onCheckedChange={builder.setAutoUnlockPhones}
								/>
							</div>
						</div>

						<div className="p-3 rounded-xl bg-emerald-950/20 border border-emerald-800/40 text-xs space-y-1">
							<div className="flex justify-between text-zinc-300">
								<span>Ước tính chi phí chiến dịch:</span>
								<strong className="text-emerald-400 font-mono text-sm">
									{builder.estimatedCost.toLocaleString("vi-VN")} đ
								</strong>
							</div>
							<p className="text-[10px] text-zinc-400">
								Bao gồm chi phí quét dữ liệu, phân tích AI & mở khóa danh bạ chất lượng cao
							</p>
						</div>
					</CardContent>
				</Card>
			</div>

			<div className="flex justify-between gap-3 pt-4 border-t border-zinc-800">
				<Button
					type="button"
					variant="outline"
					onClick={() => builder.setCurrentStep(1)}
					className="text-xs text-zinc-300 border-zinc-700"
				>
					<ChevronLeft className="w-3.5 h-3.5 mr-1" />
					Quay lại Bước 1
				</Button>
				<Button
					type="button"
					onClick={() => builder.setCurrentStep(3)}
					className="bg-emerald-500 hover:bg-emerald-400 text-black text-xs font-bold px-6"
				>
					Tiếp tục: Launch & Kích hoạt
					<ArrowRight className="w-3.5 h-3.5 ml-1.5" />
				</Button>
			</div>
		</div>
	);
}

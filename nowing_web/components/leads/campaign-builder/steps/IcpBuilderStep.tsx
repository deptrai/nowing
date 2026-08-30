"use client";

import {
	ArrowRight,
	Bot,
	Building,
	Check,
	Cpu,
	Layers,
	Loader2,
	MapPin,
	Plus,
	Sparkles,
	Target,
	X,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { CampaignIntent, IcpVerticalTemplate } from "@/contracts/types/campaign.types";

import { VERTICAL_PRESETS } from "../constants";
import type { UseCampaignBuilderReturn } from "../types";

const ALL_INTENTS: CampaignIntent[] = ["BÁN", "MUA", "TUYỂN", "ĐẤU THẦU", "HỢP TÁC"];

export function IcpBuilderStep({
	builder,
	onCancel,
}: {
	builder: UseCampaignBuilderReturn;
	onCancel?: () => void;
}) {
	return (
		<div className="space-y-6">
			<Card className="bg-zinc-900/60 border-zinc-800/80">
				<CardHeader>
					<CardTitle className="text-base flex items-center gap-2 text-zinc-100">
						<Layers className="w-4 h-4 text-emerald-400" />
						<span>1. Chọn Mẫu Ngành Dọc (Vertical Template)</span>
					</CardTitle>
					<CardDescription className="text-xs text-zinc-400">
						Chọn ngành mẫu để Nowing tự động cấu hình bộ từ khóa và tiêu chí đo lường phù hợp
					</CardDescription>
				</CardHeader>
				<CardContent>
					<div className="grid grid-cols-1 md:grid-cols-3 gap-3">
						{(Object.keys(VERTICAL_PRESETS) as IcpVerticalTemplate[]).map((key) => {
							const preset = VERTICAL_PRESETS[key];
							const isSelected = builder.selectedTemplate === key;
							return (
								<button
									key={key}
									type="button"
									onClick={() => builder.selectTemplate(key)}
									className={`text-left p-4 rounded-xl border cursor-pointer transition-all ${
										isSelected
											? "bg-emerald-500/10 border-emerald-500/50 ring-1 ring-emerald-500 shadow-md"
											: "bg-zinc-950/40 border-zinc-800/80 hover:border-zinc-700 text-zinc-300"
									}`}
								>
									<div className="flex items-center justify-between mb-1.5">
										<h4
											className={`text-xs font-bold ${isSelected ? "text-emerald-400" : "text-zinc-200"}`}
										>
											{preset.label}
										</h4>
										{isSelected && <Check className="w-3.5 h-3.5 text-emerald-400" />}
									</div>
									<p className="text-[11px] text-zinc-400 line-clamp-2">{preset.description}</p>
								</button>
							);
						})}
					</div>
				</CardContent>
			</Card>

			<Card className="bg-gradient-to-r from-emerald-950/20 via-zinc-900/60 to-zinc-900/60 border-emerald-900/40">
				<CardHeader>
					<CardTitle className="text-sm flex items-center justify-between text-zinc-100">
						<span className="flex items-center gap-2">
							<Sparkles className="w-4 h-4 text-emerald-400" />
							<span>1-Click Reverse ICP từ Website</span>
						</span>
						<Badge
							variant="outline"
							className="text-[10px] bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
						>
							AI Powered
						</Badge>
					</CardTitle>
					<CardDescription className="text-xs text-zinc-400">
						Nhập website khách hàng lý tưởng hoặc đối thủ để AI tự động phân tích và trích xuất hồ
						sơ ICP
					</CardDescription>
				</CardHeader>
				<CardContent className="space-y-3">
					<div className="flex gap-2">
						<Input
							type="url"
							value={builder.reverseIcpUrl}
							onChange={(e) => builder.setReverseIcpUrl(e.target.value)}
							placeholder="https://example.com (URL công ty mục tiêu)"
							className="bg-zinc-950/80 border-zinc-800 text-xs"
						/>
						<Button
							type="button"
							disabled={builder.isAnalyzingIcp || !builder.reverseIcpUrl}
							onClick={builder.handleAnalyzeReverseIcp}
							className="bg-emerald-500 hover:bg-emerald-400 text-black text-xs font-semibold shrink-0"
						>
							{builder.isAnalyzingIcp ? (
								<>
									<Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
									Đang phân tích...
								</>
							) : (
								<>
									<Bot className="w-3.5 h-3.5 mr-1.5" />
									Trích xuất ICP
								</>
							)}
						</Button>
					</div>
				</CardContent>
			</Card>

			<div className="grid grid-cols-1 md:grid-cols-2 gap-6">
				<Card className="bg-zinc-900/60 border-zinc-800/80">
					<CardHeader>
						<CardTitle className="text-sm flex items-center gap-2 text-zinc-100">
							<Building className="w-4 h-4 text-emerald-400" />
							<span>Ngành nghề & Địa lý mục tiêu</span>
						</CardTitle>
					</CardHeader>
					<CardContent className="space-y-4">
						<div>
							<Label className="text-xs text-zinc-300">Ngành nghề trọng tâm</Label>
							<div className="flex gap-2 mt-1.5">
								<Input
									value={builder.industryInput}
									onChange={(e) => builder.setIndustryInput(e.target.value)}
									onKeyDown={(e) => {
										if (e.key === "Enter") {
											e.preventDefault();
											builder.addIndustry();
										}
									}}
									placeholder="Nhập ngành & nhấn Enter..."
									className="text-xs bg-zinc-950/70 border-zinc-800"
								/>
								<Button type="button" size="sm" variant="secondary" onClick={builder.addIndustry}>
									<Plus className="w-3.5 h-3.5" />
								</Button>
							</div>
							<div className="flex flex-wrap gap-1.5 mt-2">
								{builder.targetIndustries.map((ind, idx) => (
									<span
										key={ind}
										className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-[11px] bg-emerald-500/10 text-emerald-300 border border-emerald-500/20"
									>
										{ind}
										<X
											className="w-3 h-3 cursor-pointer hover:text-white"
											onClick={() => builder.removeIndustry(idx)}
										/>
									</span>
								))}
							</div>
						</div>

						<div>
							<Label className="text-xs text-zinc-300">Khu vực / Tỉnh thành</Label>
							<div className="flex gap-2 mt-1.5">
								<Input
									value={builder.locationInput}
									onChange={(e) => builder.setLocationInput(e.target.value)}
									onKeyDown={(e) => {
										if (e.key === "Enter") {
											e.preventDefault();
											builder.addLocation();
										}
									}}
									placeholder="Hà Nội, TP.HCM, Bình Dương..."
									className="text-xs bg-zinc-950/70 border-zinc-800"
								/>
								<Button type="button" size="sm" variant="secondary" onClick={builder.addLocation}>
									<Plus className="w-3.5 h-3.5" />
								</Button>
							</div>
							<div className="flex flex-wrap gap-1.5 mt-2">
								{builder.locations.map((loc, idx) => (
									<span
										key={loc}
										className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-[11px] bg-zinc-800 text-zinc-300 border border-zinc-700"
									>
										<MapPin className="w-3 h-3 text-zinc-400" />
										{loc}
										<X
											className="w-3 h-3 cursor-pointer hover:text-white"
											onClick={() => builder.removeLocation(idx)}
										/>
									</span>
								))}
							</div>
						</div>

						<div>
							<Label className="text-xs text-zinc-300">Quy mô nhân sự</Label>
							<select
								value={builder.companySize}
								onChange={(e) => builder.setCompanySize(e.target.value)}
								className="w-full mt-1.5 px-3 py-2 text-xs rounded-lg bg-zinc-950/70 border border-zinc-800 text-zinc-200 focus:ring-1 focus:ring-emerald-500"
							>
								<option value="1-10 nhân sự">1-10 nhân sự (Micro / Startups)</option>
								<option value="10-50 nhân sự">10-50 nhân sự (Small Business)</option>
								<option value="50-200 nhân sự">50-200 nhân sự (Medium Business)</option>
								<option value="200-500 nhân sự">200-500 nhân sự (Mid-Enterprise)</option>
								<option value="500+ nhân sự">500+ nhân sự (Enterprise / Corp)</option>
							</select>
						</div>
					</CardContent>
				</Card>

				<Card className="bg-zinc-900/60 border-zinc-800/80">
					<CardHeader>
						<CardTitle className="text-sm flex items-center gap-2 text-zinc-100">
							<Target className="w-4 h-4 text-amber-400" />
							<span>Ý định thị trường & Từ khóa loại trừ</span>
						</CardTitle>
					</CardHeader>
					<CardContent className="space-y-4">
						<div>
							<Label className="text-xs text-zinc-300">
								Ý định tín hiệu mua bán (Market Intents)
							</Label>
							<div className="flex flex-wrap gap-2 mt-2">
								{ALL_INTENTS.map((intent) => {
									const isSelected = builder.selectedIntents.includes(intent);
									return (
										<button
											key={intent}
											type="button"
											onClick={() => builder.toggleIntent(intent)}
											className={`px-3 py-1 text-xs font-semibold rounded-lg border transition-all ${
												isSelected
													? "bg-amber-500/20 text-amber-300 border-amber-500/50 shadow-sm"
													: "bg-zinc-950/40 text-zinc-400 border-zinc-800 hover:border-zinc-700"
											}`}
										>
											🎯 INTENT: {intent}
										</button>
									);
								})}
							</div>
						</div>

						<div>
							<Label className="text-xs text-zinc-300">Công nghệ & Công cụ (Tech Stack)</Label>
							<div className="flex gap-2 mt-1.5">
								<Input
									value={builder.techInput}
									onChange={(e) => builder.setTechInput(e.target.value)}
									onKeyDown={(e) => {
										if (e.key === "Enter") {
											e.preventDefault();
											builder.addTech();
										}
									}}
									placeholder="React, AWS, SAP, Salesforce..."
									className="text-xs bg-zinc-950/70 border-zinc-800"
								/>
								<Button type="button" size="sm" variant="secondary" onClick={builder.addTech}>
									<Plus className="w-3.5 h-3.5" />
								</Button>
							</div>
							<div className="flex flex-wrap gap-1.5 mt-2">
								{builder.techStack.map((tech, idx) => (
									<span
										key={tech}
										className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-[11px] bg-blue-500/10 text-blue-300 border border-blue-500/20"
									>
										<Cpu className="w-3 h-3 text-blue-400" />
										{tech}
										<X
											className="w-3 h-3 cursor-pointer hover:text-white"
											onClick={() => builder.removeTech(idx)}
										/>
									</span>
								))}
							</div>
						</div>

						<div>
							<Label className="text-xs text-zinc-300">Từ khóa phủ định (Negative Keywords)</Label>
							<div className="flex gap-2 mt-1.5">
								<Input
									value={builder.negativeInput}
									onChange={(e) => builder.setNegativeInput(e.target.value)}
									onKeyDown={(e) => {
										if (e.key === "Enter") {
											e.preventDefault();
											builder.addNegativeKeyword();
										}
									}}
									placeholder="Từ khóa cần lọc bỏ (spam, lừa đảo...)"
									className="text-xs bg-zinc-950/70 border-zinc-800"
								/>
								<Button
									type="button"
									size="sm"
									variant="secondary"
									onClick={builder.addNegativeKeyword}
								>
									<Plus className="w-3.5 h-3.5" />
								</Button>
							</div>
							<div className="flex flex-wrap gap-1.5 mt-2">
								{builder.negativeKeywords.map((neg, idx) => (
									<span
										key={neg}
										className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-[11px] bg-red-500/10 text-red-300 border border-red-500/20"
									>
										🚫 {neg}
										<X
											className="w-3 h-3 cursor-pointer hover:text-white"
											onClick={() => builder.removeNegativeKeyword(idx)}
										/>
									</span>
								))}
							</div>
						</div>
					</CardContent>
				</Card>
			</div>

			<div className="flex justify-end gap-3 pt-4 border-t border-zinc-800">
				{onCancel && (
					<Button variant="ghost" onClick={onCancel} className="text-xs text-zinc-400">
						Hủy bỏ
					</Button>
				)}
				<Button
					type="button"
					onClick={() => builder.setCurrentStep(2)}
					className="bg-emerald-500 hover:bg-emerald-400 text-black text-xs font-bold px-6"
				>
					Tiếp tục: Nguồn & Ngân sách
					<ArrowRight className="w-3.5 h-3.5 ml-1.5" />
				</Button>
			</div>
		</div>
	);
}

"use client";

import {
	AlertCircle,
	ArrowRight,
	Bot,
	Check,
	Copy,
	Filter,
	Globe,
	Loader2,
	Plus,
	Search,
	Sparkles,
	Target,
	X,
	Zap,
} from "lucide-react";
import { useRouter } from "next/navigation";
import type React from "react";
import { useEffect, useState } from "react";
import type {
	BuyerPersona,
	FilterPresets,
	ReverseIcpResponse,
} from "@/contracts/types/leads.types";
import { leadsApiService } from "@/lib/apis/leads-api.service";

interface ReverseIcpModalProps {
	isOpen: boolean;
	onClose: () => void;
	workspaceId: string;
	onApplyFilterPresets?: (presets: FilterPresets) => void;
	onCreateTableFromIcp?: (name: string, icon: string, presets: FilterPresets) => Promise<void>;
}

const SAMPLE_DOMAINS = [
	{ label: "Vinhomes (BĐS)", url: "vinhomes.vn" },
	{ label: "TopCV (Tuyển dụng)", url: "topcv.vn" },
	{ label: "Haravan (E-Commerce)", url: "haravan.com" },
	{ label: "Base.vn (B2B SaaS)", url: "base.vn" },
];

export const ReverseIcpModal: React.FC<ReverseIcpModalProps> = ({
	isOpen,
	onClose,
	workspaceId,
	onApplyFilterPresets,
	onCreateTableFromIcp,
}) => {
	const router = useRouter();
	const [url, setUrl] = useState<string>("");
	const [customInstructions, setCustomInstructions] = useState<string>("");
	const [loading, setLoading] = useState<boolean>(false);
	const [error, setError] = useState<string | null>(null);
	const [result, setResult] = useState<ReverseIcpResponse | null>(null);
	const [selectedPersonaIdx, setSelectedPersonaIdx] = useState<number>(0);
	const [progressStep, setProgressStep] = useState<number>(1);
	const [copiedQuery, setCopiedQuery] = useState<string | null>(null);

	// Reset state when modal opens
	useEffect(() => {
		if (isOpen) {
			setError(null);
		}
	}, [isOpen]);

	// Simulate fast progress steps
	useEffect(() => {
		if (loading) {
			setProgressStep(1);
			const t1 = setTimeout(() => setProgressStep(2), 700);
			const t2 = setTimeout(() => setProgressStep(3), 1500);
			return () => {
				clearTimeout(t1);
				clearTimeout(t2);
			};
		}
	}, [loading]);

	if (!isOpen) return null;

	const handleAnalyze = async (e?: React.FormEvent) => {
		if (e) e.preventDefault();
		const trimmedUrl = url.trim();
		if (!trimmedUrl) {
			setError("Vui lòng nhập đường dẫn website hoặc landing page dự án.");
			return;
		}

		setError(null);
		setLoading(true);
		setResult(null);

		try {
			const data = await leadsApiService.analyzeReverseIcp(
				workspaceId,
				trimmedUrl,
				customInstructions.trim() || undefined
			);
			setResult(data);
			setSelectedPersonaIdx(0);
		} catch (err: unknown) {
			const errMsg =
				err instanceof Error
					? err.message
					: "Không thể phân tích URL. Vui lòng kiểm tra lại liên kết.";
			setError(errMsg);
		} finally {
			setLoading(false);
		}
	};

	const handleApplyFilters = () => {
		if (result && onApplyFilterPresets) {
			onApplyFilterPresets(result.filter_presets);
			onClose();
		}
	};

	const handleCreateTable = async () => {
		if (result && onCreateTableFromIcp) {
			const tableName = `Khách ${result.company_name}`;
			await onCreateTableFromIcp(tableName, "target", result.filter_presets);
			onClose();
		}
	};

	const handleOpenChatPrompt = (promptText: string) => {
		router.push(`/dashboard/${workspaceId}/leads?q=${encodeURIComponent(promptText)}`);
		onClose();
	};

	const handleCopyQuery = (text: string) => {
		try {
			navigator.clipboard?.writeText(text).catch(() => {});
		} catch {
			// Fallback silently
		}
		setCopiedQuery(text);
		setTimeout(() => setCopiedQuery(null), 1500);
	};

	const activePersona: BuyerPersona | undefined = result?.target_buyer_personas[selectedPersonaIdx];

	return (
		<div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-150">
			<div className="relative w-full max-w-3xl max-h-[90vh] flex flex-col rounded-2xl bg-zinc-900 border border-zinc-800 shadow-2xl overflow-hidden text-zinc-100">
				{/* Modal Header */}
				<div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800 bg-zinc-950/50">
					<div className="flex items-center gap-2.5">
						<div className="p-2 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
							<Sparkles className="w-5 h-5" />
						</div>
						<div>
							<h2 className="text-base font-bold text-zinc-100 flex items-center gap-2">
								<span>1-Click Reverse-ICP</span>
								<span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">
									Story 21.10
								</span>
							</h2>
							<p className="text-xs text-zinc-400">
								Dán link website hoặc dự án BĐS để tự động sinh chân dung khách hàng & bộ lọc săn
								lead
							</p>
						</div>
					</div>
					<button
						type="button"
						onClick={onClose}
						className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
					>
						<X className="w-5 h-5" />
					</button>
				</div>

				{/* Modal Body */}
				<div className="flex-1 overflow-y-auto p-6 space-y-6">
					{/* Input Form */}
					<form onSubmit={handleAnalyze} className="space-y-3">
						<div className="space-y-1.5">
							<label
								htmlFor="target-url-input"
								className="text-xs font-semibold text-zinc-300 flex items-center gap-1.5"
							>
								<Globe className="w-3.5 h-3.5 text-emerald-400" />
								<span>URL Website / Landing Page Dự án</span>
							</label>
							<div className="flex gap-2">
								<div className="relative flex-1">
									<Search className="w-4 h-4 text-zinc-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
									<input
										id="target-url-input"
										type="text"
										value={url}
										onChange={(e) => setUrl(e.target.value)}
										placeholder="Nhập tên miền hoặc link: vinhomes.vn, topcv.vn, haravan.com..."
										disabled={loading}
										className="w-full pl-10 pr-4 py-2.5 text-xs rounded-xl bg-zinc-950 border border-zinc-800 text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 disabled:opacity-50"
									/>
								</div>
								<button
									type="submit"
									disabled={loading || !url.trim()}
									className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-medium bg-emerald-500 text-black hover:bg-emerald-400 disabled:opacity-50 transition-colors font-semibold shadow-sm shadow-emerald-500/20"
								>
									{loading ? (
										<>
											<Loader2 className="w-4 h-4 animate-spin" />
											<span>Đang phân tích...</span>
										</>
									) : (
										<>
											<Zap className="w-4 h-4" />
											<span>Phân tích ICP</span>
										</>
									)}
								</button>
							</div>
						</div>

						{/* Quick Preset Chips */}
						<div className="flex items-center gap-2 flex-wrap text-[11px] text-zinc-400">
							<span>Thử nhanh:</span>
							{SAMPLE_DOMAINS.map((item) => (
								<button
									key={item.url}
									type="button"
									onClick={() => {
										setUrl(item.url);
									}}
									className="px-2.5 py-1 rounded-lg bg-zinc-800/80 hover:bg-zinc-700/80 text-zinc-300 hover:text-white border border-zinc-700/50 transition-colors"
								>
									{item.label}
								</button>
							))}
						</div>

						{/* Optional Custom Instructions Input */}
						<div className="pt-1">
							<input
								type="text"
								value={customInstructions}
								onChange={(e) => setCustomInstructions(e.target.value)}
								placeholder="Tùy chọn: Nhập yêu cầu tập trung (VD: Chỉ tập trung phân khúc biệt thự cao cấp...)"
								disabled={loading}
								className="w-full px-3.5 py-2 text-[11px] rounded-lg bg-zinc-950/50 border border-zinc-800/80 text-zinc-300 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-emerald-500/50 disabled:opacity-50"
							/>
						</div>
					</form>

					{/* Error Alert */}
					{error && (
						<div className="flex items-center gap-2 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs">
							<AlertCircle className="w-4 h-4 shrink-0" />
							<span>{error}</span>
						</div>
					)}

					{/* Loading State with 3 Progress Steps */}
					{loading && (
						<div className="p-6 rounded-2xl bg-zinc-950/60 border border-zinc-800 text-center space-y-4">
							<Loader2 className="w-8 h-8 animate-spin text-emerald-400 mx-auto" />
							<div className="space-y-1.5 max-w-sm mx-auto">
								<p className="text-xs font-semibold text-zinc-200">
									{progressStep === 1 && "1/3 Đang cào dữ liệu web an toàn (<1s)..."}
									{progressStep === 2 && "2/3 Đang bóc tách OpenGraph & Schema JSON-LD..."}
									{progressStep >= 3 && "3/3 AI đang phân tích chân dung khách hàng..."}
								</p>
								<div className="w-full h-1.5 rounded-full bg-zinc-800 overflow-hidden">
									<div
										className="h-full bg-emerald-500 transition-all duration-500"
										style={{ width: `${progressStep * 33.3}%` }}
									/>
								</div>
							</div>
						</div>
					)}

					{/* Analysis Result View */}
					{result && !loading && (
						<div className="space-y-5 animate-in fade-in duration-200">
							{/* Value Proposition Banner */}
							<div className="p-4 rounded-xl bg-gradient-to-r from-emerald-950/40 via-zinc-900 to-zinc-900 border border-emerald-500/20 space-y-1.5">
								<div className="flex items-center justify-between">
									<div className="flex items-center gap-2">
										<span className="text-sm font-bold text-emerald-400">
											{result.company_name}
										</span>
										<span className="text-[11px] px-2 py-0.5 rounded-md bg-zinc-800 text-zinc-300 font-mono">
											{result.domain}
										</span>
									</div>
									<span className="text-[11px] px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
										{result.industry}
									</span>
								</div>
								<p className="text-xs text-zinc-300 leading-relaxed font-medium">
									{result.value_proposition}
								</p>
							</div>

							{/* Buyer Personas Tabs */}
							<div className="space-y-3">
								<h3 className="text-xs font-bold text-zinc-300 uppercase tracking-wider flex items-center gap-1.5">
									<Target className="w-3.5 h-3.5 text-emerald-400" />
									<span>3 Chân Dung Khách Hàng Tiềm Năng (Buyer Personas)</span>
								</h3>

								{/* Persona Tabs */}
								<div className="flex gap-2 border-b border-zinc-800 pb-1">
									{result.target_buyer_personas.map((persona, idx) => (
										<button
											key={persona.title}
											type="button"
											onClick={() => setSelectedPersonaIdx(idx)}
											className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
												selectedPersonaIdx === idx
													? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
													: "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"
											}`}
										>
											Persona {idx + 1}: {persona.title.split("/")[0]}
										</button>
									))}
								</div>

								{/* Active Persona Card */}
								{activePersona && (
									<div className="p-4 rounded-xl bg-zinc-950/70 border border-zinc-800 space-y-3">
										<div className="flex items-center justify-between text-xs">
											<div>
												<span className="font-bold text-zinc-100">{activePersona.title}</span>
												<span className="text-zinc-400 ml-2">({activePersona.industry})</span>
											</div>
											<span className="text-[11px] text-zinc-400 px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800">
												Quy mô: {activePersona.company_size}
											</span>
										</div>

										<div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
											<div className="p-3 rounded-lg bg-zinc-900/60 border border-zinc-800/80 space-y-1">
												<span className="text-[11px] font-semibold text-rose-400">
													⚡ Nỗi đau / Thách thức cốt lõi:
												</span>
												<ul className="list-disc list-inside text-zinc-300 space-y-0.5 text-[11px]">
													{activePersona.pain_points.map((p) => (
														<li key={p}>{p}</li>
													))}
												</ul>
											</div>

											<div className="p-3 rounded-lg bg-zinc-900/60 border border-zinc-800/80 space-y-1">
												<span className="text-[11px] font-semibold text-emerald-400">
													🎯 Tín hiệu kích hoạt mua hàng:
												</span>
												<ul className="list-disc list-inside text-zinc-300 space-y-0.5 text-[11px]">
													{activePersona.buying_triggers.map((t) => (
														<li key={t}>{t}</li>
													))}
												</ul>
											</div>
										</div>
									</div>
								)}
							</div>

							{/* Suggested Search Queries */}
							<div className="space-y-2">
								<h3 className="text-xs font-bold text-zinc-300 uppercase tracking-wider flex items-center gap-1.5">
									<Search className="w-3.5 h-3.5 text-emerald-400" />
									<span>Truy Vấn Tìm Kiếm & Quét Lead Khuyến Nghị</span>
								</h3>
								<div className="flex flex-wrap gap-2">
									{result.suggested_search_queries.map((q) => (
										<button
											key={q}
											type="button"
											onClick={() => handleCopyQuery(q)}
											className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700/60 transition-colors"
										>
											{copiedQuery === q ? (
												<Check className="w-3 h-3 text-emerald-400" />
											) : (
												<Copy className="w-3 h-3 text-zinc-400" />
											)}
											<span>{q}</span>
										</button>
									))}
								</div>
							</div>

							{/* Chat Starter Prompts */}
							<div className="space-y-2">
								<h3 className="text-xs font-bold text-zinc-300 uppercase tracking-wider flex items-center gap-1.5">
									<Bot className="w-3.5 h-3.5 text-emerald-400" />
									<span>Kích Hoạt Nhanh AI Co-pilot Săn Lead</span>
								</h3>
								<div className="space-y-1.5">
									{result.chat_starter_prompts.map((promptText) => (
										<div
											key={promptText}
											className="flex items-center justify-between p-2.5 rounded-xl bg-zinc-950 border border-zinc-800/80 text-xs hover:border-emerald-500/40 transition-colors"
										>
											<span className="text-zinc-300">{promptText}</span>
											<button
												type="button"
												onClick={() => handleOpenChatPrompt(promptText)}
												className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500 hover:text-black font-semibold transition-all shrink-0 ml-3"
											>
												<span>Mở Chat</span>
												<ArrowRight className="w-3 h-3" />
											</button>
										</div>
									))}
								</div>
							</div>
						</div>
					)}
				</div>

				{/* Modal Footer */}
				{result && !loading && (
					<div className="flex flex-wrap items-center justify-between gap-3 px-6 py-4 border-t border-zinc-800 bg-zinc-950/80">
						<div className="text-[11px] text-zinc-400">
							<span>Đã cấu hình bộ lọc: </span>
							<span className="text-emerald-400 font-semibold">
								{result.filter_presets.platforms.join(", ")} • Ý định:{" "}
								{result.filter_presets.intent}
							</span>
						</div>

						<div className="flex items-center gap-2">
							{onCreateTableFromIcp && (
								<button
									type="button"
									onClick={handleCreateTable}
									className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 transition-colors"
								>
									<Plus className="w-3.5 h-3.5 text-zinc-400" />
									<span>Tạo Tab Bảng Mới</span>
								</button>
							)}

							{onApplyFilterPresets && (
								<button
									type="button"
									onClick={handleApplyFilters}
									className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-emerald-500 hover:bg-emerald-400 text-black shadow-sm transition-colors"
								>
									<Filter className="w-3.5 h-3.5" />
									<span>Áp dụng vào Bộ lọc</span>
								</button>
							)}
						</div>
					</div>
				)}
			</div>
		</div>
	);
};

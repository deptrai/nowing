"use client";

import {
	AlertTriangle,
	Check,
	Copy,
	Edit3,
	Eye,
	Flame,
	Layers,
	ShieldCheck,
	Sparkles,
} from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import type {
	DraftVariation,
	OutlierPostItem,
	VoiceProfile,
} from "@/lib/apis/social-copilot-api.service";

interface ViralDraftReviewPanelProps {
	originalPost?: OutlierPostItem | null;
	drafts: DraftVariation[];
	activeVoiceProfile?: VoiceProfile | null;
	targetPlatform: "facebook" | "twitter" | "linkedin" | "threads";
	isGenerating?: boolean;
	onGenerateNewDrafts?: () => void;
}

export function ViralDraftReviewPanel({
	originalPost,
	drafts,
	activeVoiceProfile,
	targetPlatform,
	isGenerating = false,
	onGenerateNewDrafts,
}: ViralDraftReviewPanelProps) {
	const [activeTabIndex, setActiveTabIndex] = useState(0);
	const [isPreviewMode, setIsPreviewMode] = useState(false);
	const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
	const [localContents, setLocalContents] = useState<Record<number, string>>({});

	// Synchronize incoming drafts to local state
	useEffect(() => {
		if (drafts && drafts.length > 0) {
			const initial: Record<number, string> = {};
			drafts.forEach((d, idx) => {
				initial[idx] = d.content;
			});
			setLocalContents(initial);
		}
	}, [drafts]);

	const activeDraft = drafts[activeTabIndex] || drafts[0];
	const currentContent =
		localContents[activeTabIndex] !== undefined
			? localContents[activeTabIndex]
			: activeDraft?.content || "";

	const handleContentChange = (val: string) => {
		setLocalContents((prev) => ({
			...prev,
			[activeTabIndex]: val,
		}));
	};

	const handleCopy = async (content: string, index: number) => {
		try {
			await navigator.clipboard.writeText(content);
			setCopiedIndex(index);
			toast.success("Đã sao chép vào clipboard / Copied to clipboard!");
			setTimeout(() => setCopiedIndex(null), 2000);
		} catch (_err) {
			toast.error("Không thể sao chép vào clipboard");
		}
	};

	if (!drafts || drafts.length === 0) {
		return (
			<div className="rounded-xl border border-dashed border-border p-12 text-center text-muted-foreground">
				<Sparkles className="h-8 w-8 mx-auto mb-3 text-primary/60" />
				<h4 className="font-semibold text-foreground text-base mb-1">Chưa có bản thảo nào</h4>
				<p className="text-sm max-w-md mx-auto mb-4">
					Chọn một bài viết viral từ mục "Bài viết Viral" hoặc dán nội dung thủ công để AI viết lại
					theo giọng văn của bạn.
				</p>
				{onGenerateNewDrafts && (
					<button
						type="button"
						onClick={onGenerateNewDrafts}
						disabled={isGenerating}
						className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
					>
						<Sparkles className="h-4 w-4" />
						{isGenerating ? "Đang tạo..." : "Tạo bản thảo / Generate Draft"}
					</button>
				)}
			</div>
		);
	}

	const charCount = currentContent.length;
	const wordCount = currentContent.trim().split(/\s+/).filter(Boolean).length;
	const isTwitterOverlimit =
		targetPlatform === "twitter" && !activeDraft?.is_thread && charCount > 280;

	return (
		<div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
			{/* Left Column: Original Viral Reference */}
			<div className="lg:col-span-5 space-y-4">
				<div className="rounded-xl border border-border bg-card p-5 shadow-sm space-y-4">
					<div className="flex items-center justify-between border-b border-border/50 pb-3">
						<div className="flex items-center gap-2">
							<Layers className="h-4 w-4 text-primary" />
							<h4 className="font-semibold text-foreground text-sm">Bài Viral Tham Chiếu</h4>
						</div>
						{originalPost?.baseline_ratio && (
							<span className="flex items-center gap-1 text-xs font-bold text-orange-600 bg-orange-500/10 border border-orange-500/20 px-2 py-0.5 rounded-full">
								<Flame className="h-3 w-3" />
								{originalPost.baseline_ratio}x Baseline
							</span>
						)}
					</div>

					{originalPost ? (
						<div className="space-y-3">
							<div className="rounded-lg bg-muted/40 p-3.5 border border-border/50">
								<p className="text-xs text-foreground/90 font-sans leading-relaxed whitespace-pre-line">
									{originalPost.content}
								</p>
							</div>

							{originalPost.why_it_worked && (
								<div className="rounded-lg bg-primary/5 p-3 border border-primary/20 text-xs">
									<span className="font-semibold text-primary">💡 Phân tích cấu trúc:</span>{" "}
									<span className="text-foreground/80">{originalPost.why_it_worked}</span>
								</div>
							)}
						</div>
					) : (
						<div className="text-xs text-muted-foreground italic p-4 text-center">
							Bản thảo được tạo theo chủ đề tự do (không đính kèm bài mẫu cụ thể).
						</div>
					)}

					{/* Active Voice Persona info */}
					{activeVoiceProfile && (
						<div className="rounded-lg bg-muted/60 p-3 border border-border/50 text-xs space-y-1">
							<div className="flex items-center justify-between">
								<span className="font-semibold text-foreground">Giọng văn áp dụng:</span>
								<span className="text-primary font-medium">{activeVoiceProfile.profile_name}</span>
							</div>
							<p className="text-muted-foreground">Tone: {activeVoiceProfile.tone}</p>
						</div>
					)}

					{/* Guardrail Reminder */}
					<div className="flex items-start gap-2 rounded-lg bg-emerald-500/10 p-3 border border-emerald-500/20 text-xs text-emerald-700">
						<ShieldCheck className="h-4 w-4 flex-shrink-0 mt-0.5" />
						<span>
							<strong>Human-in-the-Loop:</strong> AI chỉ hỗ trợ soạn thảo và tinh chỉnh. Bạn luôn có
							toàn quyền kiểm duyệt trước khi sao chép và tự đăng.
						</span>
					</div>
				</div>
			</div>

			{/* Right Column: Interactive Tabbed Draft Editor */}
			<div className="lg:col-span-7 space-y-4">
				<div className="rounded-xl border border-border bg-card p-5 shadow-sm space-y-4">
					{/* Variation Tabs & Tools */}
					<div className="flex items-center justify-between gap-2 border-b border-border/50 pb-3 flex-wrap">
						<div className="flex items-center gap-1.5" role="tablist">
							{drafts.map((d, index) => {
								const isCurrent = activeTabIndex === index;
								const tabLabels = [
									"Bản thảo A / Variation A",
									"Bản thảo B / Variation B",
									"Bản thảo C / Variation C",
								];
								return (
									<button
										key={d.variation_letter}
										type="button"
										role="tab"
										aria-selected={isCurrent}
										onClick={() => setActiveTabIndex(index)}
										className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
											isCurrent
												? "bg-primary text-primary-foreground shadow-sm"
												: "text-muted-foreground hover:text-foreground hover:bg-muted"
										}`}
									>
										<span>{tabLabels[index] || `Bản thảo ${d.variation_letter}`}</span>
									</button>
								);
							})}
						</div>

						<div className="flex items-center gap-2">
							<button
								type="button"
								onClick={() => setIsPreviewMode(!isPreviewMode)}
								className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground px-2 py-1 rounded-md hover:bg-muted transition-colors border border-border"
							>
								{isPreviewMode ? (
									<Edit3 className="h-3.5 w-3.5" />
								) : (
									<Eye className="h-3.5 w-3.5" />
								)}
								{isPreviewMode ? "Chỉnh sửa" : "Xem trước"}
							</button>

							<button
								type="button"
								onClick={() => handleCopy(currentContent, activeTabIndex)}
								className="flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition-colors shadow-sm"
							>
								{copiedIndex === activeTabIndex ? (
									<Check className="h-3.5 w-3.5" />
								) : (
									<Copy className="h-3.5 w-3.5" />
								)}
								Sao chép / Copy
							</button>
						</div>
					</div>

					{/* Angle metadata badge */}
					<div className="flex items-center justify-between text-xs text-muted-foreground">
						<span className="flex items-center gap-1.5">
							<span className="font-semibold text-foreground">Góc tiếp cận:</span>
							<span className="rounded-md bg-primary/10 text-primary px-2 py-0.5 font-medium uppercase text-[10px]">
								{activeDraft?.angle || "contrarian"}
							</span>
						</span>
						<span>Đọc ước tính: ~{activeDraft?.estimated_reading_time_sec || 30}s</span>
					</div>

					{/* Draft Content Area */}
					{isPreviewMode ? (
						<div className="min-h-[240px] rounded-lg bg-background p-4 border border-input text-sm text-foreground whitespace-pre-line leading-relaxed font-sans">
							{currentContent}
						</div>
					) : (
						<textarea
							rows={10}
							value={currentContent}
							onChange={(e) => handleContentChange(e.target.value)}
							className="w-full min-h-[240px] rounded-lg bg-background p-4 border border-input text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary whitespace-pre-line leading-relaxed font-sans resize-y"
						/>
					)}

					{/* Footer: Counters & Warning */}
					<div className="flex items-center justify-between pt-2 border-t border-border/50 text-xs text-muted-foreground">
						<div className="flex items-center gap-3 font-mono">
							<span>{wordCount} từ</span>
							<span className={isTwitterOverlimit ? "text-rose-600 font-bold" : ""}>
								{charCount} ký tự{" "}
								{targetPlatform === "twitter" && !activeDraft?.is_thread && "/ 280"}
								{targetPlatform === "twitter" && activeDraft?.is_thread && " (Thread 3 tweets)"}
							</span>
						</div>

						{isTwitterOverlimit && (
							<span className="flex items-center gap-1 text-rose-600 font-medium">
								<AlertTriangle className="h-3.5 w-3.5" /> Quá giới hạn 280 ký tự của tweet đơn
							</span>
						)}
					</div>
				</div>
			</div>
		</div>
	);
}

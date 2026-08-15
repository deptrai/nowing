"use client";

import { ExternalLink, Flame, MessageSquare, Repeat2, Sparkles, ThumbsUp } from "lucide-react";
import type { OutlierPostItem } from "@/lib/apis/social-copilot-api.service";

interface OutlierPostCardProps {
	post: OutlierPostItem;
	isSelected?: boolean;
	onSelect: (post: OutlierPostItem) => void;
	onGenerateDraft?: (post: OutlierPostItem) => void;
}

export function OutlierPostCard({
	post,
	isSelected = false,
	onSelect,
	onGenerateDraft,
}: OutlierPostCardProps) {
	const taxonomyColors: Record<string, string> = {
		contrarian_hook: "bg-rose-500/10 text-rose-600 border-rose-500/20",
		story_shift: "bg-purple-500/10 text-purple-600 border-purple-500/20",
		value_list: "bg-blue-500/10 text-blue-600 border-blue-500/20",
		data_reveal: "bg-amber-500/10 text-amber-600 border-amber-500/20",
	};

	const taxonomyLabels: Record<string, string> = {
		contrarian_hook: "Tranh biện / Contrarian Hook",
		story_shift: "Chuyển hóa / Story Shift",
		value_list: "Checklist giá trị / Value List",
		data_reveal: "Bật mí dữ liệu / Data Reveal",
	};

	const taxonomyKey = post.hook_taxonomy || "contrarian_hook";
	const badgeColor = taxonomyColors[taxonomyKey] || "bg-primary/10 text-primary border-primary/20";
	const badgeLabel = taxonomyLabels[taxonomyKey] || "Viral Hook";

	return (
		<div
			data-testid="outlier-card"
			className={`group relative rounded-xl border p-5 transition-all ${
				isSelected
					? "border-primary bg-primary/[0.03] shadow-md ring-2 ring-primary/30"
					: "border-border bg-card hover:border-primary/40 hover:shadow-sm"
			}`}
		>
			{/* Top Bar: Platform, Multiplier Badge, Taxonomy */}
			<div className="flex items-center justify-between gap-2 mb-3">
				<div className="flex items-center gap-2 flex-wrap">
					<span className="rounded-md bg-muted px-2 py-0.5 text-xs font-semibold text-foreground uppercase">
						{post.platform}
					</span>

					{/* Multiplier Badge */}
					<span
						data-testid="outlier-multiplier"
						className="flex items-center gap-1 rounded-full bg-orange-500/10 border border-orange-500/20 px-2 py-0.5 text-xs font-bold text-orange-600"
					>
						<Flame className="h-3 w-3" />
						{post.baseline_ratio >= 1 ? `${post.baseline_ratio}x` : "3.0x"} baseline
					</span>

					{/* Taxonomy Badge */}
					<span
						data-testid="hook-taxonomy-badge"
						className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${badgeColor}`}
					>
						{badgeLabel}
					</span>
				</div>

				{post.post_url && (
					<a
						href={post.post_url}
						target="_blank"
						rel="noopener noreferrer"
						className="text-muted-foreground hover:text-foreground transition-colors p-1"
						title="Xem bài gốc"
					>
						<ExternalLink className="h-4 w-4" />
					</a>
				)}
			</div>

			{/* Post Content Preview */}
			<div className="mb-4">
				<p className="text-sm text-foreground/90 font-sans leading-relaxed line-clamp-4 whitespace-pre-line">
					{post.content}
				</p>
			</div>

			{/* Why it worked highlight */}
			{post.why_it_worked && (
				<div className="mb-4 rounded-lg bg-muted/60 p-2.5 text-xs text-muted-foreground border border-border/50">
					<span className="font-semibold text-foreground">💡 Tại sao viral:</span>{" "}
					{post.why_it_worked}
				</div>
			)}

			{/* Footer: Engagement Stats & Action */}
			<div className="flex items-center justify-between pt-3 border-t border-border/50 text-xs text-muted-foreground">
				<div className="flex items-center gap-3 font-mono">
					<span className="flex items-center gap-1">
						<ThumbsUp className="h-3.5 w-3.5" /> {post.reactions_count}
					</span>
					<span className="flex items-center gap-1">
						<MessageSquare className="h-3.5 w-3.5" /> {post.comments_count}
					</span>
					<span className="flex items-center gap-1">
						<Repeat2 className="h-3.5 w-3.5" /> {post.shares_count}
					</span>
				</div>

				<div className="flex items-center gap-2">
					<button
						type="button"
						onClick={() => onSelect(post)}
						className="rounded-lg border border-input px-2.5 py-1 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
					>
						Chọn
					</button>

					{onGenerateDraft && (
						<button
							type="button"
							onClick={() => onGenerateDraft(post)}
							className="flex items-center gap-1 rounded-lg bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary hover:bg-primary hover:text-primary-foreground transition-colors"
						>
							<Sparkles className="h-3 w-3" /> Tạo bản thảo
						</button>
					)}
				</div>
			</div>
		</div>
	);
}

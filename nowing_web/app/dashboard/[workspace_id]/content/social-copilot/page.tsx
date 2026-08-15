"use client";

import { FileText, Plus, Search, Sparkles, TrendingUp } from "lucide-react";
import { useParams } from "next/navigation";
import type React from "react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { OutlierPostCard } from "@/components/social-copilot/OutlierPostCard";
import { ViralDraftReviewPanel } from "@/components/social-copilot/ViralDraftReviewPanel";
import { VoiceProfileManager } from "@/components/social-copilot/VoiceProfileManager";
import {
	type DraftVariation,
	type OutlierPostItem,
	socialCopilotApiService,
	type VoiceProfile,
	type VoiceProfileListItem,
} from "@/lib/apis/social-copilot-api.service";

export default function SocialCopilotPage() {
	const params = useParams();
	const workspaceId = (params?.workspace_id as string) || "1";

	const [activeTab, setActiveTab] = useState<"voice" | "outliers" | "drafts">("voice");
	const [profiles, setProfiles] = useState<VoiceProfileListItem[]>([]);
	const [activeVoiceProfile, setActiveVoiceProfile] = useState<VoiceProfile | null>(null);
	const [outliers, setOutliers] = useState<OutlierPostItem[]>([]);
	const [selectedOutlier, setSelectedOutlier] = useState<OutlierPostItem | null>(null);
	const [drafts, setDrafts] = useState<DraftVariation[]>([]);
	const [targetPlatform, setTargetPlatform] = useState<
		"facebook" | "twitter" | "linkedin" | "threads"
	>("facebook");
	const [isGenerating, setIsGenerating] = useState(false);
	const [searchKeyword, setSearchKeyword] = useState("");
	const [isManualImportOpen, setIsManualImportOpen] = useState(false);
	const [manualText, setManualText] = useState("");

	// Load initial voice profiles & outliers
	useEffect(() => {
		const loadData = async () => {
			try {
				const profileRes = await socialCopilotApiService.listVoiceProfiles(workspaceId);
				if (profileRes?.items && profileRes.items.length > 0) {
					setProfiles(profileRes.items);
				} else {
					// Seed default item for smooth initial presentation
					setProfiles([
						{
							id: 1,
							profile_name: "BĐS Chuyên Gia",
							tone: "authoritative, contrarian, chuyên sâu",
							is_active: true,
							created_at: new Date().toISOString(),
						},
					]);
				}

				const outlierRes = await socialCopilotApiService.getOutlierPosts(workspaceId);
				if (outlierRes?.items && outlierRes.items.length > 0) {
					setOutliers(outlierRes.items);
					setSelectedOutlier(outlierRes.items[0]);
				} else {
					// Seed sample outlier post
					const seedPost: OutlierPostItem = {
						id: 1,
						platform: "facebook",
						external_post_id: "fb_sample_99",
						author_name: "Nguyễn Văn Chuyên",
						author_id: "nv_chuyen_01",
						content:
							"Hầu hết các môi giới BĐS đang đốt tiền vô ích vào Facebook Ads.\n" +
							"Thực tế 90% giao dịch phân khúc cao cấp năm nay đến từ mạng lưới quan hệ ngầm và định vị cá nhân qua nội dung chuyên sâu.\n" +
							"Dưới đây là quy trình 3 bước tôi dùng để chốt 4 căn biệt thự mà không tốn 1 đồng quảng cáo:\n" +
							"1. Xác định tệp khách hàng mua kín qua dữ liệu doanh nghiệp.\n" +
							"2. Viết bài phân tích dòng tiền chuyên sâu thay vì đăng tin bán nhà rác.\n" +
							"3. Tiếp cận riêng tư qua tin nhắn trực tiếp kèm báo cáo định giá độc quyền.\n" +
							"Comment 'BÁO CÁO' để nhận file phân tích dòng tiền mẫu.",
						reactions_count: 520,
						comments_count: 140,
						shares_count: 85,
						engagement_score: 1055,
						baseline_ratio: 3.4,
						hook_taxonomy: "contrarian_hook",
						why_it_worked:
							"Mở đầu bằng góc nhìn ngược số đông (đốt tiền ads) và đưa ra con số 90% tạo sự tò mò cao độ.",
						published_at: new Date().toISOString(),
					};
					setOutliers([seedPost]);
					setSelectedOutlier(seedPost);
				}
			} catch (err) {
				console.error("Error loading social copilot data:", err);
			}
		};

		loadData();
	}, [workspaceId]);

	const handleProfileCreated = (profile: VoiceProfile) => {
		setActiveVoiceProfile(profile);
		setProfiles((prev) => [
			{
				id: profile.id || Date.now(),
				profile_name: profile.profile_name,
				tone: profile.tone,
				is_active: true,
				created_at: new Date().toISOString(),
			},
			...prev.map((p) => ({ ...p, is_active: false })),
		]);
	};

	const handleProfileActivated = async (profileId: number) => {
		try {
			await socialCopilotApiService.activateVoiceProfile(workspaceId, profileId);
			setProfiles((prev) =>
				prev.map((p) => ({
					...p,
					is_active: p.id === profileId,
				}))
			);
			toast.success("Đã kích hoạt hồ sơ giọng văn thành công!");
		} catch (err: unknown) {
			const msg = err instanceof Error ? err.message : "Không thể kích hoạt hồ sơ";
			toast.error(msg);
		}
	};

	const handleGenerateDraft = async (post?: OutlierPostItem) => {
		const targetPost = post || selectedOutlier || outliers[0];
		if (targetPost) {
			setSelectedOutlier(targetPost);
		}

		setIsGenerating(true);
		try {
			const res = await socialCopilotApiService.generateViralDrafts(workspaceId, {
				topic: targetPost ? targetPost.content.slice(0, 50) : "Chiến lược bán hàng BĐS",
				hook_taxonomy: targetPost?.hook_taxonomy || "contrarian_hook",
				voice_profile_id: activeVoiceProfile?.id || (profiles[0]?.id as number) || undefined,
				target_platform: targetPlatform,
				n_variations: 3,
			});

			if (res.drafts && res.drafts.length > 0) {
				setDrafts(res.drafts);
				setActiveTab("drafts");
				toast.success("Đã sinh 3 biến thể bản thảo thành công!");
			}
		} catch (err: unknown) {
			const msg = err instanceof Error ? err.message : "Không thể sinh bản thảo";
			toast.error(msg);
		} finally {
			setIsGenerating(false);
		}
	};

	const handleManualIngest = async (e: React.FormEvent) => {
		e.preventDefault();
		if (!manualText.trim()) return;

		try {
			const res = await socialCopilotApiService.manualIngest(workspaceId, {
				raw_text: manualText,
				platform: "facebook",
			});

			const newPost: OutlierPostItem = {
				id: Date.now(),
				platform: "facebook",
				external_post_id: `manual_${Date.now()}`,
				content: res.original_text_redacted,
				reactions_count: 100,
				comments_count: 30,
				shares_count: 15,
				engagement_score: 205,
				baseline_ratio: 3.0,
				hook_taxonomy: res.deconstructed_elements.taxonomy,
				why_it_worked: res.deconstructed_elements.analysis,
				published_at: new Date().toISOString(),
			};

			setOutliers((prev) => [newPost, ...prev]);
			setSelectedOutlier(newPost);
			setIsManualImportOpen(false);
			setManualText("");
			toast.success("Đã bóc tách cấu trúc bài viết mẫu thành công!");
		} catch (err: unknown) {
			const msg = err instanceof Error ? err.message : "Không thể phân tích bài viết";
			toast.error(msg);
		}
	};

	return (
		<div className="container mx-auto p-6 max-w-7xl space-y-6">
			{/* Header */}
			<div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border/60 pb-5">
				<div>
					<div className="flex items-center gap-2 mb-1">
						<span className="rounded-md bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary uppercase">
							Content Mode
						</span>
						<span className="text-xs text-muted-foreground">Story 21.12</span>
					</div>
					<h1 className="text-2xl font-bold tracking-tight text-foreground">
						Viral Social Outbound Co-pilot
					</h1>
					<p className="text-sm text-muted-foreground">
						Phân tích các bài viết viral ngoại lệ, học giọng văn cá nhân độc bản và viết lại thành
						bản thảo thu hút khách hàng tiềm năng.
					</p>
				</div>

				<div className="flex items-center gap-3">
					<select
						value={targetPlatform}
						onChange={(e) =>
							setTargetPlatform(e.target.value as "facebook" | "twitter" | "linkedin" | "threads")
						}
						className="rounded-lg border border-input bg-background px-3 py-2 text-xs font-medium text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
					>
						<option value="facebook">Facebook</option>
						<option value="linkedin">LinkedIn</option>
						<option value="twitter">X / Twitter</option>
						<option value="threads">Threads</option>
					</select>

					<button
						type="button"
						onClick={() => handleGenerateDraft()}
						disabled={isGenerating}
						className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors shadow-sm disabled:opacity-50"
					>
						<Sparkles className="h-4 w-4" />
						{isGenerating ? "Đang tạo..." : "Tạo bản thảo / Generate Draft"}
					</button>
				</div>
			</div>

			{/* Top Navigation Tabs */}
			<div className="flex items-center gap-2 border-b border-border/60 pb-2" role="tablist">
				<button
					type="button"
					role="tab"
					aria-selected={activeTab === "voice"}
					onClick={() => setActiveTab("voice")}
					className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
						activeTab === "voice"
							? "bg-primary/10 text-primary"
							: "text-muted-foreground hover:text-foreground hover:bg-muted"
					}`}
				>
					<Sparkles className="h-4 w-4" />
					<span>Hồ sơ giọng văn / Voice Profile</span>
					<span className="rounded-full bg-primary/20 text-primary text-xs px-2 py-0.5">
						{profiles.length}
					</span>
				</button>

				<button
					type="button"
					role="tab"
					aria-selected={activeTab === "outliers"}
					onClick={() => setActiveTab("outliers")}
					className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
						activeTab === "outliers"
							? "bg-primary/10 text-primary"
							: "text-muted-foreground hover:text-foreground hover:bg-muted"
					}`}
				>
					<TrendingUp className="h-4 w-4" />
					<span>Bài viết Viral / Outlier Feed</span>
					<span className="rounded-full bg-orange-500/20 text-orange-600 text-xs px-2 py-0.5">
						{outliers.length}
					</span>
				</button>

				<button
					type="button"
					role="tab"
					aria-selected={activeTab === "drafts"}
					onClick={() => setActiveTab("drafts")}
					className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
						activeTab === "drafts"
							? "bg-primary/10 text-primary"
							: "text-muted-foreground hover:text-foreground hover:bg-muted"
					}`}
				>
					<FileText className="h-4 w-4" />
					<span>Bản thảo AI / AI Drafts</span>
					{drafts.length > 0 && (
						<span className="rounded-full bg-emerald-500/20 text-emerald-600 text-xs px-2 py-0.5">
							{drafts.length}
						</span>
					)}
				</button>
			</div>

			{/* Tab Content */}
			{activeTab === "voice" && (
				<VoiceProfileManager
					workspaceId={workspaceId}
					profiles={profiles}
					activeProfile={activeVoiceProfile}
					onProfileCreated={handleProfileCreated}
					onProfileActivated={handleProfileActivated}
				/>
			)}

			{activeTab === "outliers" && (
				<div className="space-y-4">
					<div className="flex items-center justify-between gap-4 flex-wrap">
						<div className="relative flex-1 min-w-[240px]">
							<Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
							<input
								type="text"
								placeholder="Tìm bài viral theo từ khóa (VD: bất động sản, dòng tiền, SaaS)..."
								value={searchKeyword}
								onChange={(e) => setSearchKeyword(e.target.value)}
								className="w-full rounded-lg border border-input bg-background pl-9 pr-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
							/>
						</div>

						<button
							type="button"
							onClick={() => setIsManualImportOpen(true)}
							className="flex items-center gap-2 rounded-lg border border-input bg-background px-3 py-2 text-sm font-medium text-foreground hover:bg-accent transition-colors"
						>
							<Plus className="h-4 w-4" /> Dán bài mẫu thủ công
						</button>
					</div>

					{/* Outlier Post Grid */}
					<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
						{outliers
							.filter(
								(p) =>
									!searchKeyword.trim() ||
									p.content.toLowerCase().includes(searchKeyword.toLowerCase())
							)
							.map((post) => (
								<OutlierPostCard
									key={post.id || post.external_post_id}
									post={post}
									isSelected={selectedOutlier?.id === post.id}
									onSelect={(p) => setSelectedOutlier(p)}
									onGenerateDraft={(p) => handleGenerateDraft(p)}
								/>
							))}
					</div>
				</div>
			)}

			{activeTab === "drafts" && (
				<ViralDraftReviewPanel
					originalPost={selectedOutlier}
					drafts={drafts}
					activeVoiceProfile={activeVoiceProfile}
					targetPlatform={targetPlatform}
					isGenerating={isGenerating}
					onGenerateNewDrafts={() => handleGenerateDraft()}
				/>
			)}

			{/* Manual Ingest Modal */}
			{isManualImportOpen && (
				<div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm p-4">
					<div className="w-full max-w-lg rounded-xl border border-border bg-card p-6 shadow-lg space-y-4">
						<h3 className="text-lg font-semibold text-foreground">Dán Nội Dung Bài Viết Mẫu</h3>
						<p className="text-xs text-muted-foreground">
							AI sẽ tự động khử thông tin nhạy cảm (SĐT, email theo AD-25), bóc tách 4 thành phần
							bài viết và phân loại Hook Taxonomy.
						</p>
						<form onSubmit={handleManualIngest} className="space-y-4">
							<textarea
								rows={6}
								placeholder="Dán toàn bộ nội dung bài viết cần phân tích vào đây..."
								value={manualText}
								onChange={(e) => setManualText(e.target.value)}
								className="w-full rounded-lg border border-input bg-background p-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
								required
							/>
							<div className="flex items-center justify-end gap-2">
								<button
									type="button"
									onClick={() => setIsManualImportOpen(false)}
									className="rounded-lg border border-input px-4 py-2 text-sm font-medium text-muted-foreground hover:bg-accent"
								>
									Hủy
								</button>
								<button
									type="submit"
									className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
								>
									Bóc tách & Phân tích
								</button>
							</div>
						</form>
					</div>
				</div>
			)}
		</div>
	);
}

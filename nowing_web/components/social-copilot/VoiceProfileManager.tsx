"use client";

import { AlertCircle, CheckCircle2, Sparkles } from "lucide-react";
import type React from "react";
import { useState } from "react";
import { toast } from "sonner";
import {
	socialCopilotApiService,
	type VoiceProfile,
	type VoiceProfileListItem,
} from "@/lib/apis/social-copilot-api.service";

interface VoiceProfileManagerProps {
	workspaceId: string | number;
	profiles: VoiceProfileListItem[];
	activeProfile?: VoiceProfile | null;
	onProfileCreated: (profile: VoiceProfile) => void;
	onProfileActivated: (profileId: number) => void;
}

export function VoiceProfileManager({
	workspaceId,
	profiles,
	activeProfile,
	onProfileCreated,
	onProfileActivated,
}: VoiceProfileManagerProps) {
	const [profileName, setProfileName] = useState("");
	const [sampleText, setSampleText] = useState("");
	const [platform, setPlatform] = useState<"facebook" | "twitter" | "linkedin">("facebook");
	const [isLoading, setIsLoading] = useState(false);

	const wordCount = sampleText.trim().split(/\s+/).filter(Boolean).length;
	const isWordCountValid = wordCount >= 100;

	const handleLearnVoice = async (e: React.FormEvent) => {
		e.preventDefault();
		if (!profileName.trim()) {
			toast.error("Vui lòng nhập tên hồ sơ giọng văn");
			return;
		}
		if (!isWordCountValid) {
			toast.error(`Mẫu bài viết cần ít nhất 100 từ (hiện tại: ${wordCount} từ)`);
			return;
		}

		setIsLoading(true);
		try {
			const newProfile = await socialCopilotApiService.createVoiceProfile(workspaceId, {
				profile_name: profileName,
				sample_text: sampleText,
				platform,
			});
			toast.success("Đã phân tích và lưu hồ sơ giọng văn thành công!");
			onProfileCreated(newProfile);
			setProfileName("");
			setSampleText("");
		} catch (error: unknown) {
			const msg = error instanceof Error ? error.message : "Không thể phân tích giọng văn";
			toast.error(msg);
		} finally {
			setIsLoading(false);
		}
	};

	return (
		<div className="space-y-6">
			{/* Form to create / learn voice profile */}
			<div className="rounded-xl border border-border bg-card p-6 shadow-sm">
				<div className="flex items-center gap-2 mb-4">
					<div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
						<Sparkles className="h-5 w-5" aria-hidden="true" />
					</div>
					<div>
						<h3 className="font-semibold text-foreground text-base">
							Học Giọng Văn Mới (Voice Learner)
						</h3>
						<p className="text-muted-foreground text-xs">
							AI sẽ phân tích văn phong, nhịp điệu câu, từ vựng và cấu trúc hook từ mẫu bài viết của
							bạn.
						</p>
					</div>
				</div>

				<form onSubmit={handleLearnVoice} className="space-y-4">
					<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
						<div className="space-y-1.5">
							<label htmlFor="profile-name" className="text-sm font-medium text-foreground">
								Tên hồ sơ / Profile Name
							</label>
							<input
								id="profile-name"
								aria-label="Tên hồ sơ / Profile Name"
								type="text"
								placeholder="VD: BĐS Chuyên Gia, Tech Founder..."
								value={profileName}
								onChange={(e) => setProfileName(e.target.value)}
								className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
								required
							/>
						</div>

						<div className="space-y-1.5">
							<label htmlFor="platform-select" className="text-sm font-medium text-foreground">
								Nền tảng mục tiêu
							</label>
							<select
								id="platform-select"
								value={platform}
								onChange={(e) => setPlatform(e.target.value as "facebook" | "twitter" | "linkedin")}
								className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
							>
								<option value="facebook">Facebook (Bài dài, hook mạnh)</option>
								<option value="linkedin">LinkedIn (Chuyên sâu, B2B)</option>
								<option value="twitter">X / Twitter (Ngắn gọn, thread)</option>
							</select>
						</div>
					</div>

					<div className="space-y-1.5">
						<div className="flex items-center justify-between">
							<label htmlFor="sample-text" className="text-sm font-medium text-foreground">
								Mẫu bài viết / Sample Text
							</label>
							<span
								className={`text-xs font-mono px-2 py-0.5 rounded-full ${
									isWordCountValid
										? "bg-emerald-500/10 text-emerald-600 font-semibold"
										: "bg-amber-500/10 text-amber-600"
								}`}
							>
								{wordCount} / 100 từ tối thiểu
							</span>
						</div>
						<textarea
							id="sample-text"
							aria-label="Mẫu bài viết / Sample Text"
							rows={6}
							placeholder="Dán 1-3 bài viết mẫu bạn từng đăng (tối thiểu 100 từ) để AI nhận diện chuẩn xác phong cách của bạn..."
							value={sampleText}
							onChange={(e) => setSampleText(e.target.value)}
							className="w-full rounded-lg border border-input bg-background p-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary font-sans leading-relaxed"
							required
						/>
						{!isWordCountValid && (
							<div className="flex items-center gap-1.5 text-xs text-amber-600">
								<AlertCircle className="h-3.5 w-3.5 flex-shrink-0" aria-hidden="true" />
								<span>
									Cần thêm ít nhất {Math.max(0, 100 - wordCount)} từ để kích hoạt thuật toán học
									giọng văn.
								</span>
							</div>
						)}
					</div>

					<div className="flex justify-end">
						<button
							type="submit"
							disabled={isLoading || !isWordCountValid || !profileName.trim()}
							className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
						>
							<Sparkles className="h-4 w-4" aria-hidden="true" />
							{isLoading ? "Đang phân tích..." : "Phân tích giọng văn / Learn Voice"}
						</button>
					</div>
				</form>
			</div>

			{/* List of Personas */}
			<div className="space-y-3">
				<h4 className="text-sm font-semibold text-foreground uppercase tracking-wider">
					Hồ Sơ Đã Lưu ({profiles.length})
				</h4>

				{profiles.length === 0 ? (
					<div className="rounded-xl border border-dashed border-border p-8 text-center text-muted-foreground text-sm">
						Chưa có hồ sơ giọng văn nào. Hãy nhập mẫu bài viết ở trên để tạo hồ sơ đầu tiên!
					</div>
				) : (
					<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
						{profiles.map((p) => {
							const isActive = activeProfile?.id === p.id || p.is_active;
							return (
								<div
									key={p.id}
									className={`rounded-xl border p-4 transition-all ${
										isActive
											? "border-primary/50 bg-primary/5 shadow-sm ring-1 ring-primary/30"
											: "border-border bg-card hover:border-border/80"
									}`}
								>
									<div className="flex items-start justify-between gap-2 mb-2">
										<div className="flex items-center gap-2">
											<div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-primary font-bold text-xs">
												{p.profile_name.charAt(0).toUpperCase()}
											</div>
											<div>
												<h5 className="font-semibold text-sm text-foreground">{p.profile_name}</h5>
												<span className="text-xs text-muted-foreground">ID: #{p.id}</span>
											</div>
										</div>
										{isActive ? (
											<span className="flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-600">
												<CheckCircle2 className="h-3 w-3" aria-hidden="true" /> Đang dùng
											</span>
										) : (
											<button
												type="button"
												onClick={() => onProfileActivated(p.id)}
												className="rounded-lg border border-input px-2.5 py-1 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
											>
												Chọn
											</button>
										)}
									</div>

									<div className="mt-3 space-y-1 text-xs text-muted-foreground">
										<p>
											<span className="font-medium text-foreground">Giọng điệu:</span> {p.tone}
										</p>
									</div>
								</div>
							);
						})}
					</div>
				)}
			</div>
		</div>
	);
}

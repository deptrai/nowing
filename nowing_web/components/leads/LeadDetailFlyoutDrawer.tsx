"use client";

import {
	AlertTriangle,
	Building2,
	Calendar,
	CheckCircle2,
	Clock,
	ExternalLink,
	History,
	MapPin,
	MessageSquare,
	Network,
	Phone,
	Send,
	Sparkles,
	Tag,
	UserCheck,
	X,
} from "lucide-react";
import type React from "react";
import { useEffect, useState } from "react";
import type { LeadActivityLog } from "@/contracts/types/lead-pipeline.types";
import type { Lead } from "@/contracts/types/leads.types";
import { leadPipelineApiService } from "@/lib/apis/lead-pipeline-api.service";
import { isAllowedUrl } from "@/lib/utils";
import { PhoneUnlockPill } from "./PhoneUnlockPill";
import { ZaloOutreachButton } from "./zalo-outreach-button";

export interface LeadDetailFlyoutDrawerProps {
	lead: Lead | null;
	isOpen: boolean;
	onClose: () => void;
	workspaceId?: string | number;
	onOpenCompanyGraph?: (companyName: string) => void;
	onReportInvalidPhone?: (lead: Lead) => void;
	unlockedPhone?: string | null;
	onPhoneChange?: (leadId: string, phone: string | null, unlocked: boolean) => void;
}

export const LeadDetailFlyoutDrawer: React.FC<LeadDetailFlyoutDrawerProps> = ({
	lead,
	isOpen,
	onClose,
	workspaceId = "1",
	onOpenCompanyGraph,
	onReportInvalidPhone,
	unlockedPhone: externalUnlockedPhone,
	onPhoneChange,
}) => {
	const [activities, setActivities] = useState<LeadActivityLog[]>([]);
	const [newNote, setNewNote] = useState("");
	const [isSubmittingNote, setIsSubmittingNote] = useState(false);
	const [leadUnlocked, setLeadUnlocked] = useState(lead?.is_unlocked ?? false);
	const [localUnlockedPhone, setLocalUnlockedPhone] = useState<string | null>(
		externalUnlockedPhone ?? lead?.phone ?? null
	);

	const displayPhone = localUnlockedPhone ?? lead?.phone ?? null;
	const isContactUnlocked = leadUnlocked;

	useEffect(() => {
		const handleKeyDown = (e: KeyboardEvent) => {
			if (e.key === "Escape" && isOpen) {
				onClose();
			}
		};
		window.addEventListener("keydown", handleKeyDown);
		return () => window.removeEventListener("keydown", handleKeyDown);
	}, [isOpen, onClose]);

	useEffect(() => {
		setLeadUnlocked(lead?.is_unlocked ?? false);
		setLocalUnlockedPhone(externalUnlockedPhone ?? lead?.phone ?? null);
	}, [lead?.is_unlocked, lead?.phone, externalUnlockedPhone]);

	useEffect(() => {
		if (isOpen && lead?.id) {
			leadPipelineApiService
				.listActivities(workspaceId, lead.id)
				.then((data) => setActivities(data || []))
				.catch(() => setActivities([]));
		}
	}, [isOpen, lead?.id, workspaceId]);

	if (!isOpen || !lead) {
		return null;
	}

	const fitScore = lead.fit_score ?? 0;
	const intentScore = lead.intent_score ?? 0;
	const compositeScore = lead.composite_score ?? 0;

	const handleAddNote = async (e: React.FormEvent) => {
		e.preventDefault();
		if (!newNote.trim() || !lead?.id || isSubmittingNote) return;

		try {
			setIsSubmittingNote(true);
			const created = await leadPipelineApiService.addActivity(workspaceId, lead.id, {
				activity_type: "internal_note",
				title: newNote.trim(),
			});
			setActivities((prev) => [created, ...prev]);
			setNewNote("");
		} catch (err) {
			console.error("Failed to add note", err);
		} finally {
			setIsSubmittingNote(false);
		}
	};

	return (
		<div className="fixed inset-0 z-50 overflow-hidden">
			{/* Backdrop */}
			<button
				type="button"
				aria-label="Đóng chi tiết lead"
				className="absolute inset-0 bg-black/60 backdrop-blur-xs transition-opacity cursor-pointer w-full h-full border-0 p-0"
				onClick={onClose}
			/>

			<div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
				<aside
					role="dialog"
					aria-modal="true"
					aria-label="Chi tiết khách hàng tiềm năng"
					data-testid="lead-detail-flyout-drawer"
					className="w-screen max-w-[480px] bg-card border-l border-border shadow-2xl flex flex-col text-foreground z-10 animate-in slide-in-from-right duration-200"
				>
					{/* Header */}
					<div className="px-6 py-5 border-b border-border bg-muted/30 soc-caro-grid flex items-start justify-between">
						<div className="space-y-1 pr-4">
							<div className="flex items-center gap-2">
								<span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
									{lead.source}
								</span>
								{lead.status && (
									<span className="text-[10px] font-medium px-2 py-0.5 rounded bg-muted text-muted-foreground border border-border">
										{lead.status}
									</span>
								)}
							</div>
							<h3 className="text-base font-bold text-foreground line-clamp-2">
								{lead.company_name}
							</h3>
						</div>
						<button
							type="button"
							onClick={onClose}
							className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
						>
							<X className="w-5 h-5" />
						</button>
					</div>

					{/* Body Content */}
					<div className="flex-1 overflow-y-auto p-6 space-y-6 scrollbar-thin">
						{/* Score Matrix */}
						<div className="p-4 rounded-xl bg-muted/40 border border-border space-y-3">
							<div className="flex items-center justify-between">
								<span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
									<Sparkles className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
									Đánh giá Điểm Tiềm Năng (Fit Score)
								</span>
								<span className="font-mono text-sm font-bold text-emerald-600 dark:text-emerald-400">
									{fitScore} / 100
								</span>
							</div>

							<div className="space-y-2 text-xs">
								<div>
									<div className="flex justify-between text-[11px] text-muted-foreground mb-1">
										<span>Khớp Chân Dung (Fit Score)</span>
										<span className="font-mono font-medium text-foreground">{fitScore}%</span>
									</div>
									<div className="w-full h-1.5 rounded-full bg-muted overflow-hidden">
										<div
											className="h-full bg-emerald-500 rounded-full transition-all duration-300"
											style={{ width: `${Math.min(100, Math.max(0, fitScore))}%` }}
										/>
									</div>
								</div>

								{intentScore > 0 && (
									<div>
										<div className="flex justify-between text-[11px] text-muted-foreground mb-1">
											<span>Ý Định Mua / Nhu Cầu (Intent)</span>
											<span className="font-mono font-medium text-foreground">{intentScore}%</span>
										</div>
										<div className="w-full h-1.5 rounded-full bg-muted overflow-hidden">
											<div
												className="h-full bg-blue-500 rounded-full transition-all duration-300"
												style={{ width: `${Math.min(100, Math.max(0, intentScore))}%` }}
											/>
										</div>
									</div>
								)}

								{compositeScore > 0 && (
									<div>
										<div className="flex justify-between text-[11px] text-muted-foreground mb-1">
											<span>Tổng Hợp (Composite)</span>
											<span className="font-mono font-medium text-foreground">
												{compositeScore}%
											</span>
										</div>
										<div className="w-full h-1.5 rounded-full bg-muted overflow-hidden">
											<div
												className="h-full bg-amber-500 rounded-full transition-all duration-300"
												style={{ width: `${Math.min(100, Math.max(0, compositeScore))}%` }}
											/>
										</div>
									</div>
								)}
							</div>
						</div>

						{/* Contact & Outreach Actions */}
						<div className="p-4 rounded-xl bg-muted/40 border border-border space-y-3">
							<h4 className="text-xs font-semibold text-foreground uppercase tracking-wider">
								Thông Tin Liên Hệ & Tiếp Cận
							</h4>

							<div className="flex items-center justify-between gap-2 p-2.5 rounded-lg bg-card border border-border">
								<div className="flex items-center gap-2">
									<Phone className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
									<PhoneUnlockPill
										lead={lead}
										workspaceId={workspaceId}
										onUnlock={setLeadUnlocked}
										onPhoneChange={(leadId, phone, unlocked) => {
											setLeadUnlocked(unlocked);
											setLocalUnlockedPhone(phone);
											onPhoneChange?.(leadId, phone, unlocked);
										}}
									/>
								</div>
								{(() => {
									const cleanDigits = (displayPhone ?? "").replace(/[^0-9+]/g, "");
									return isContactUnlocked && cleanDigits.length >= 8 ? (
										<a
											href={`tel:${cleanDigits}`}
											data-testid="call-now-link"
											className="px-2.5 py-1 text-xs font-medium rounded-md bg-muted hover:bg-muted/80 text-foreground transition-colors"
										>
											Gọi ngay
										</a>
									) : null;
								})()}
							</div>

							<div className="grid grid-cols-2 gap-2 pt-1">
								<ZaloOutreachButton
									leadId={lead.id}
									workspaceId={workspaceId}
									phone={displayPhone}
									companyName={lead.company_name}
									intent={lead.intent}
									source={lead.source}
									contentSnippet={lead.content_snippet}
									className="w-full justify-center"
									disabled={!isContactUnlocked}
								/>

								{onOpenCompanyGraph && (
									<button
										type="button"
										onClick={() => onOpenCompanyGraph(lead.company_name)}
										className="inline-flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium rounded-lg bg-muted hover:bg-muted/80 text-foreground border border-border transition-colors cursor-pointer"
									>
										<Network className="w-3.5 h-3.5 text-blue-500" />
										Company Graph
									</button>
								)}
							</div>
						</div>

						{/* Entity Metadata */}
						<div className="space-y-2 text-xs text-foreground">
							{lead.location && (
								<div className="flex items-start gap-2">
									<MapPin className="w-3.5 h-3.5 text-muted-foreground shrink-0 mt-0.5" />
									<span>{lead.location}</span>
								</div>
							)}
							{lead.price_estimate && (
								<div className="flex items-start gap-2">
									<Tag className="w-3.5 h-3.5 text-emerald-500 shrink-0 mt-0.5" />
									<span className="font-mono font-bold text-emerald-600 dark:text-emerald-400">
										{lead.price_estimate}
									</span>
								</div>
							)}
							{lead.industry && (
								<div className="flex items-start gap-2">
									<Building2 className="w-3.5 h-3.5 text-muted-foreground shrink-0 mt-0.5" />
									<span>Ngành: {lead.industry}</span>
								</div>
							)}
							{lead.created_at && (
								<div className="flex items-start gap-2">
									<Calendar className="w-3.5 h-3.5 text-muted-foreground shrink-0 mt-0.5" />
									<span className="text-muted-foreground font-mono text-[11px]">
										{!Number.isNaN(new Date(lead.created_at).getTime())
											? new Date(lead.created_at).toLocaleString("vi-VN")
											: "Vừa xong"}
									</span>
								</div>
							)}
						</div>

						{/* Full Content Snippet */}
						{lead.content_snippet && (
							<div className="space-y-2">
								<h4 className="text-xs font-semibold text-foreground uppercase tracking-wider">
									Nội dung bài đăng gốc
								</h4>
								<div className="p-3.5 rounded-xl bg-muted/30 border border-border text-xs text-foreground leading-relaxed whitespace-pre-wrap font-sans">
									{lead.content_snippet}
								</div>
							</div>
						)}

						{/* Interaction Timeline & Audit Logs (Story 24.3 / AC-3) */}
						<div className="p-4 rounded-xl bg-muted/40 border border-border space-y-4">
							<div className="flex items-center justify-between">
								<h4 className="text-xs font-semibold text-foreground uppercase tracking-wider flex items-center gap-1.5">
									<History className="w-3.5 h-3.5 text-blue-500" />
									Lịch Sử Tương Tác & Phân Bổ
								</h4>
								<span className="text-[10px] text-muted-foreground font-mono">
									{activities.length} sự kiện
								</span>
							</div>

							{/* Add Internal Note */}
							<form onSubmit={handleAddNote} className="flex gap-2">
								<input
									type="text"
									value={newNote}
									onChange={(e) => setNewNote(e.target.value)}
									placeholder="Thêm ghi chú nội bộ..."
									className="flex-1 px-3 py-1.5 text-xs rounded-lg bg-card border border-border text-foreground placeholder:text-muted-foreground focus:outline-hidden focus:ring-1 focus:ring-primary"
								/>
								<button
									type="submit"
									disabled={!newNote.trim() || isSubmittingNote}
									className="px-3 py-1.5 text-xs font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors flex items-center gap-1 cursor-pointer"
								>
									<Send className="w-3 h-3" />
									Lưu
								</button>
							</form>

							{/* Activity Timeline List */}
							<div className="space-y-3 relative before:absolute before:inset-0 before:left-2.5 before:w-0.5 before:bg-border/60">
								{activities.length === 0 ? (
									<div className="text-xs text-muted-foreground pl-6 py-2">
										Chưa có tương tác ghi nhận.
									</div>
								) : (
									activities.map((act) => {
										let icon = <Clock className="w-3 h-3 text-muted-foreground" />;
										let badgeBg = "bg-muted";

										if (act.activity_type.includes("zalo") || act.activity_type.includes("zns")) {
											icon = <MessageSquare className="w-3 h-3 text-emerald-500" />;
											badgeBg =
												"bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30";
										} else if (act.activity_type.includes("stage")) {
											icon = <CheckCircle2 className="w-3 h-3 text-blue-500" />;
											badgeBg =
												"bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/30";
										} else if (act.activity_type.includes("assign")) {
											icon = <UserCheck className="w-3 h-3 text-purple-500" />;
											badgeBg =
												"bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/30";
										}

										return (
											<div key={act.id} className="relative flex items-start gap-3 pl-1">
												<div className="relative z-10 flex items-center justify-center w-5 h-5 rounded-full bg-card border border-border shadow-xs mt-0.5">
													{icon}
												</div>
												<div className="flex-1 min-w-0 p-2 rounded-lg bg-card border border-border text-xs space-y-1">
													<div className="flex items-center justify-between gap-2">
														<span
															className={`text-[9px] uppercase font-bold px-1.5 py-0.5 rounded ${badgeBg}`}
														>
															{act.activity_type}
														</span>
														<span className="text-[10px] text-muted-foreground font-mono">
															{new Date(act.created_at).toLocaleTimeString("vi-VN", {
																hour: "2-digit",
																minute: "2-digit",
															})}
														</span>
													</div>
													<div className="font-medium text-foreground text-[11px] leading-snug">
														{act.title}
													</div>
												</div>
											</div>
										);
									})
								)}
							</div>
						</div>

						{/* Source Link & Invalid Phone Report */}
						<div className="pt-2 flex items-center justify-between text-xs text-muted-foreground border-t border-border">
							{lead.source_url && isAllowedUrl(lead.source_url) ? (
								<a
									href={lead.source_url}
									target="_blank"
									rel="noopener noreferrer"
									className="inline-flex items-center gap-1 text-muted-foreground hover:text-emerald-600 dark:hover:text-emerald-400 transition-colors"
								>
									<ExternalLink className="w-3.5 h-3.5" />
									Mở bài gốc
								</a>
							) : (
								<span />
							)}

							{lead.phone && onReportInvalidPhone && (
								<button
									type="button"
									onClick={() => onReportInvalidPhone(lead)}
									className="inline-flex items-center gap-1 text-rose-500/80 hover:text-rose-500 transition-colors cursor-pointer"
								>
									<AlertTriangle className="w-3.5 h-3.5" />
									Báo SĐT sai (Hoàn tiền 100%)
								</button>
							)}
						</div>
					</div>
				</aside>
			</div>
		</div>
	);
};

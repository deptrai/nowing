"use client";

import {
	AlertTriangle,
	Edit2,
	Info,
	Megaphone,
	Plus,
	RefreshCw,
	Sparkles,
	Trash2,
	Wrench,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import type {
	BannerType,
	BroadcastCreate,
	BroadcastRead,
	BroadcastUpdate,
} from "@/contracts/types/broadcasts.types";
import { broadcastsApiService } from "@/lib/apis/broadcasts-api.service";

function getBannerIcon(type: BannerType) {
	switch (type) {
		case "warning":
			return <AlertTriangle className="h-4 w-4 text-amber-500" />;
		case "maintenance":
			return <Wrench className="h-4 w-4 text-rose-500" />;
		case "promo":
			return <Sparkles className="h-4 w-4 text-purple-500" />;
		default:
			return <Info className="h-4 w-4 text-blue-500" />;
	}
}

function getStatusBadge(status: string, t: (k: string) => string) {
	switch (status) {
		case "active":
			return (
				<span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs font-semibold text-emerald-500 border border-emerald-500/20">
					Active
				</span>
			);
		case "scheduled":
			return (
				<span className="rounded-full bg-blue-500/10 px-2 py-0.5 text-xs font-semibold text-blue-500 border border-blue-500/20">
					{t("broadcasts_status_scheduled")}
				</span>
			);
		case "expired":
			return (
				<span className="rounded-full bg-zinc-500/10 px-2 py-0.5 text-xs font-semibold text-zinc-500 border border-zinc-500/20">
					{t("broadcasts_status_expired")}
				</span>
			);
		default:
			return (
				<span className="rounded-full bg-rose-500/10 px-2 py-0.5 text-xs font-semibold text-rose-500 border border-rose-500/20">
					{t("broadcasts_status_inactive")}
				</span>
			);
	}
}

export default function AdminBroadcastsPage() {
	const t = useTranslations("admin");
	const [items, setItems] = useState<BroadcastRead[]>([]);
	const [isLoading, setIsLoading] = useState(false);

	// Create / Edit modal state
	const [isModalOpen, setIsModalOpen] = useState(false);
	const [editingItem, setEditingItem] = useState<BroadcastRead | null>(null);

	const [title, setTitle] = useState("");
	const [message, setMessage] = useState("");
	const [bannerType, setBannerType] = useState<BannerType>("info");
	const [targetAll, setTargetAll] = useState(true);
	const [targetWorkspacesStr, setTargetWorkspacesStr] = useState("");
	const [startsAt, setStartsAt] = useState("");
	const [expiresAt, setExpiresAt] = useState("");
	const [dismissible, setDismissible] = useState(true);
	const [isActive, setIsActive] = useState(true);

	const [isSubmitting, setIsSubmitting] = useState(false);
	const [formError, setFormError] = useState("");

	const loadBroadcasts = useCallback(async () => {
		setIsLoading(true);
		try {
			const res = await broadcastsApiService.listAdmin();
			setItems(res.items);
		} catch (err) {
			console.error(t("broadcasts_load_failed"), err);
		} finally {
			setIsLoading(false);
		}
	}, []);

	useEffect(() => {
		loadBroadcasts();
	}, [loadBroadcasts]);

	const openCreateModal = () => {
		setEditingItem(null);
		setTitle("");
		setMessage("");
		setBannerType("info");
		setTargetAll(true);
		setTargetWorkspacesStr("");
		setStartsAt(new Date().toISOString().slice(0, 16));
		setExpiresAt("");
		setDismissible(true);
		setIsActive(true);
		setFormError("");
		setIsModalOpen(true);
	};

	const openEditModal = (item: BroadcastRead) => {
		setEditingItem(item);
		setTitle(item.title);
		setMessage(item.message);
		setBannerType(item.banner_type as BannerType);
		setTargetAll(item.target_all);
		setTargetWorkspacesStr((item.target_workspace_ids || []).join(", "));
		setStartsAt(new Date(item.starts_at).toISOString().slice(0, 16));
		setExpiresAt(item.expires_at ? new Date(item.expires_at).toISOString().slice(0, 16) : "");
		setDismissible(item.dismissible);
		setIsActive(item.is_active);
		setFormError("");
		setIsModalOpen(true);
	};

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		setFormError("");
		setIsSubmitting(true);

		const parsedWsIds = targetAll
			? []
			: targetWorkspacesStr
					.split(",")
					.map((s) => parseInt(s.trim(), 10))
					.filter((n) => !Number.isNaN(n));

		try {
			if (editingItem) {
				const updatePayload: BroadcastUpdate = {
					title,
					message,
					banner_type: bannerType,
					target_all: targetAll,
					target_workspace_ids: parsedWsIds,
					starts_at: startsAt ? new Date(startsAt).toISOString() : undefined,
					expires_at: expiresAt ? new Date(expiresAt).toISOString() : null,
					dismissible,
					is_active: isActive,
				};
				await broadcastsApiService.update(editingItem.id, updatePayload);
			} else {
				const createPayload: BroadcastCreate = {
					title,
					message,
					banner_type: bannerType,
					target_all: targetAll,
					target_workspace_ids: parsedWsIds,
					starts_at: startsAt ? new Date(startsAt).toISOString() : undefined,
					expires_at: expiresAt ? new Date(expiresAt).toISOString() : null,
					dismissible,
					is_active: isActive,
				};
				await broadcastsApiService.create(createPayload);
			}
			setIsModalOpen(false);
			await loadBroadcasts();
		} catch (err: unknown) {
			const errorMsg = err instanceof Error ? err.message : t("broadcasts_save_failed");
			setFormError(errorMsg);
		} finally {
			setIsSubmitting(false);
		}
	};

	const handleDelete = async (id: string) => {
		if (!confirm(t("broadcasts_confirm_delete"))) return;
		try {
			await broadcastsApiService.delete(id);
			await loadBroadcasts();
		} catch (err: unknown) {
			const errorMsg = err instanceof Error ? err.message : t("broadcasts_unknown_error");
			alert(t("broadcasts_delete_failed", {errorMsg}));
		}
	};

	return (
		<div className="space-y-6 p-6">
			{/* Header */}
			<div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
				<div>
					<div className="flex items-center gap-2">
						<Megaphone className="h-6 w-6 text-primary" />
						<h1 className="text-2xl font-bold tracking-tight">{t("broadcasts_title")}</h1>
					</div>
					<p className="text-sm text-muted-foreground">
						{t("broadcasts_subtitle")}
					</p>
				</div>
				<div className="flex items-center gap-2">
					<button
						type="button"
						onClick={loadBroadcasts}
						disabled={isLoading}
						className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-3 py-2 text-sm font-medium text-foreground hover:bg-muted"
					>
						<RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
						{t("broadcasts_refresh")}
					</button>
					<button
						type="button"
						onClick={openCreateModal}
						className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
					>
						<Plus className="h-4 w-4" />
						{t("broadcasts_new")}
					</button>
				</div>
			</div>

			{/* Table */}
			<div className="rounded-xl border border-border bg-card overflow-hidden">
				<div className="overflow-x-auto">
					<table className="w-full text-left text-sm">
						<thead className="border-b border-border bg-muted/40 text-xs font-medium text-muted-foreground uppercase">
							<tr>
								<th className="px-4 py-3">{t("broadcasts_col_type")}</th>
								<th className="px-4 py-3">{t("broadcasts_col_title_msg")}</th>
								<th className="px-4 py-3">{t("broadcasts_col_targeting")}</th>
								<th className="px-4 py-3">{t("broadcasts_col_schedule")}</th>
								<th className="px-4 py-3">{t("broadcasts_col_status")}</th>
								<th className="px-4 py-3 text-right">{t("broadcasts_col_actions")}</th>
							</tr>
						</thead>
						<tbody className="divide-y divide-border">
							{isLoading ? (
								<tr>
									<td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
										{t("broadcasts_loading")}
									</td>
								</tr>
							) : items.length === 0 ? (
								<tr>
									<td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
										{t("broadcasts_empty")}
									</td>
								</tr>
							) : (
								items.map((b) => (
									<tr key={b.id} className="hover:bg-muted/30 transition">
										<td className="px-4 py-3 whitespace-nowrap">
											<div className="flex items-center gap-1.5">
												{getBannerIcon(b.banner_type as BannerType)}
												<span className="text-xs font-semibold capitalize">{b.banner_type}</span>
											</div>
										</td>
										<td className="px-4 py-3">
											<div className="font-semibold text-foreground">{b.title}</div>
											<div className="text-xs text-muted-foreground line-clamp-2 max-w-md">
												{b.message}
											</div>
										</td>
										<td className="px-4 py-3 text-xs">
											{b.target_all ? (
												<span className="rounded bg-muted px-1.5 py-0.5 font-medium text-foreground">
													{t("broadcasts_all_workspaces")}
												</span>
											) : (
												<span className="rounded bg-primary/10 px-1.5 py-0.5 font-mono text-primary">
													{t("broadcasts_workspaces_label")}: {b.target_workspace_ids.join(", ")}
												</span>
											)}
										</td>
										<td className="px-4 py-3 text-xs text-muted-foreground whitespace-nowrap">
											<div>{t("broadcasts_start")}: {new Date(b.starts_at).toLocaleString()}</div>
											{b.expires_at && <div>{t("broadcasts_exp")}: {new Date(b.expires_at).toLocaleString()}</div>}
										</td>
										<td className="px-4 py-3 whitespace-nowrap">{getStatusBadge(b.status, t)}</td>
										<td className="px-4 py-3 text-right whitespace-nowrap">
											<div className="flex justify-end gap-1">
												<button
													type="button"
													onClick={() => openEditModal(b)}
													className="rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
													title={t("broadcasts_edit")}
												>
													<Edit2 className="h-4 w-4" />
												</button>
												<button
													type="button"
													onClick={() => handleDelete(b.id)}
													className="rounded p-1.5 text-rose-500 hover:bg-rose-500/10"
													title={t("broadcasts_delete")}
												>
													<Trash2 className="h-4 w-4" />
												</button>
											</div>
										</td>
									</tr>
								))
							)}
						</tbody>
					</table>
				</div>
			</div>

			{/* Create / Edit Modal */}
			{isModalOpen && (
				<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
					<div className="w-full max-w-lg rounded-xl border border-border bg-card p-6 shadow-2xl space-y-4">
						<div className="flex items-center justify-between">
							<h3 className="text-lg font-bold">
								{editingItem ? t("broadcasts_edit_title") : t("broadcasts_create_title")}
							</h3>
							<button
								type="button"
								onClick={() => setIsModalOpen(false)}
								className="rounded-lg p-1 text-muted-foreground hover:bg-muted"
							>
								✕
							</button>
						</div>

						{formError && (
							<div className="rounded-lg bg-rose-500/10 p-3 text-xs text-rose-500">{formError}</div>
						)}

						<form onSubmit={handleSubmit} className="space-y-4">
							<div>
								<label
									htmlFor="broadcast-title"
									className="text-xs font-medium text-muted-foreground"
								>
									{t("broadcasts_field_title")}
								</label>
								<input
									id="broadcast-title"
									type="text"
									required
									placeholder={t("broadcasts_title_placeholder")}
									value={title}
									onChange={(e) => setTitle(e.target.value)}
									className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
								/>
							</div>

							<div>
								<label
									htmlFor="broadcast-message"
									className="text-xs font-medium text-muted-foreground"
								>
									{t("broadcasts_field_message")}
								</label>
								<textarea
									id="broadcast-message"
									rows={3}
									required
									placeholder={t("broadcasts_message_placeholder")}
									value={message}
									onChange={(e) => setMessage(e.target.value)}
									className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
								/>
							</div>

							<div className="grid grid-cols-2 gap-3">
								<div>
									<label
										htmlFor="broadcast-banner-type"
										className="text-xs font-medium text-muted-foreground"
									>
										{t("broadcasts_banner_type")}
									</label>
									<select
										id="broadcast-banner-type"
										value={bannerType}
										onChange={(e) => setBannerType(e.target.value as BannerType)}
										className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
									>
										<option value="info">{t("broadcasts_type_info")}</option>
										<option value="warning">{t("broadcasts_type_warning")}</option>
										<option value="maintenance">{t("broadcasts_type_maintenance")}</option>
										<option value="promo">{t("broadcasts_type_promo")}</option>
									</select>
								</div>

								<div className="flex items-center pt-5 gap-4">
									<label className="flex items-center gap-2 text-xs font-medium cursor-pointer">
										<input
											type="checkbox"
											checked={dismissible}
											onChange={(e) => setDismissible(e.target.checked)}
											className="rounded"
										/>
										{t("broadcasts_dismissible")}
									</label>
									<label className="flex items-center gap-2 text-xs font-medium cursor-pointer">
										<input
											type="checkbox"
											checked={isActive}
											onChange={(e) => setIsActive(e.target.checked)}
											className="rounded"
										/>
										{t("broadcasts_active")}
									</label>
								</div>
							</div>

							<div>
								<label className="flex items-center gap-2 text-xs font-medium cursor-pointer">
									<input
										type="checkbox"
										checked={targetAll}
										onChange={(e) => setTargetAll(e.target.checked)}
										className="rounded"
									/>
									{t("broadcasts_target_all")}
								</label>

								{!targetAll && (
									<div className="mt-2">
										<label
											htmlFor="broadcast-target-workspaces"
											className="text-xs text-muted-foreground"
										>
											{t("broadcasts_target_ids")}
										</label>
										<input
											id="broadcast-target-workspaces"
											type="text"
											placeholder="1, 2, 3"
											value={targetWorkspacesStr}
											onChange={(e) => setTargetWorkspacesStr(e.target.value)}
											className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
										/>
									</div>
								)}
							</div>

							<div className="grid grid-cols-2 gap-3">
								<div>
									<label
										htmlFor="broadcast-starts-at"
										className="text-xs font-medium text-muted-foreground"
									>
										{t("broadcasts_starts_at")}
									</label>
									<input
										id="broadcast-starts-at"
										type="datetime-local"
										value={startsAt}
										onChange={(e) => setStartsAt(e.target.value)}
										className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
									/>
								</div>
								<div>
									<label
										htmlFor="broadcast-expires-at"
										className="text-xs font-medium text-muted-foreground"
									>
										{t("broadcasts_expires_at")}
									</label>
									<input
										id="broadcast-expires-at"
										type="datetime-local"
										value={expiresAt}
										onChange={(e) => setExpiresAt(e.target.value)}
										className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
									/>
								</div>
							</div>

							<div className="flex justify-end gap-2 pt-2">
								<button
									type="button"
									onClick={() => setIsModalOpen(false)}
									className="rounded-lg border border-border px-4 py-2 text-sm font-medium hover:bg-muted"
								>
									{t("broadcasts_cancel")}
								</button>
								<button
									type="submit"
									disabled={isSubmitting || !title.trim() || !message.trim()}
									className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
								>
									{isSubmitting ? t("broadcasts_saving") : t("broadcasts_save")}
								</button>
							</div>
						</form>
					</div>
				</div>
			)}
		</div>
	);
}

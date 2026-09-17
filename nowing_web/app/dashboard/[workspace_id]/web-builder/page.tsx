"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
	AlertCircle,
	CheckCircle2,
	ChevronDown,
	ChevronUp,
	Code,
	ExternalLink,
	Eye,
	FileCode,
	Globe,
	Loader2,
	Monitor,
	MousePointerClick,
	Play,
	RefreshCw,
	Rocket,
	Settings,
	Smartphone,
	Sparkles,
	Square,
	Tablet,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { MarkToolOverlay } from "@/components/web-builder/mark-tool-overlay";
import { PreviewIframe } from "@/components/web-builder/preview-iframe";
import type { MarkToolRect, WorkspaceApp } from "@/contracts/types/web-builder.types";
import { webBuilderApiService } from "@/lib/apis/web-builder-api.service";

export default function WebBuilderPage() {
	const params = useParams();
	const t = useTranslations("webBuilder");
	const workspaceId = Number(params.workspace_id);
	const queryClient = useQueryClient();

	const [prompt, setPrompt] = useState("");
	const [selectedApp, setSelectedApp] = useState<WorkspaceApp | null>(null);
	const [isMarkToolActive, setIsMarkToolActive] = useState(false);
	const [selectedSelector, setSelectedSelector] = useState("");
	const [patchText, setPatchText] = useState("");
	const [patchType, setPatchType] = useState<
		"text" | "className" | "style" | "attribute" | "replace"
	>("text");
	const [attributeName, setAttributeName] = useState("");
	const [selectedRect, setSelectedRect] = useState<MarkToolRect | undefined>(undefined);
	const [componentHint, setComponentHint] = useState<string | undefined>(undefined);
	const [customDomainInput, setCustomDomainInput] = useState("");
	const [isDomainModalOpen, setIsDomainModalOpen] = useState(false);
	const [isLogsOpen, setIsLogsOpen] = useState(false);

	// Enhanced UI States: View Tabs, Device Switcher, Streaming Logs & Code Viewer
	const [activeTab, setActiveTab] = useState<"preview" | "code">("preview");
	const [deviceMode, setDeviceMode] = useState<"desktop" | "tablet" | "mobile">("desktop");
	const [isStreaming, setIsStreaming] = useState(false);
	const [streamPhase, setStreamPhase] = useState<string>("");
	const [streamMessage, setStreamMessage] = useState<string>("");
	const [streamTokens, setStreamTokens] = useState<string>("");
	const [streamFiles, setStreamFiles] = useState<string[]>([]);
	const [iframeKey, setIframeKey] = useState(0);
	const [appFiles, setAppFiles] = useState<Record<string, string>>({});
	const [selectedFile, setSelectedFile] = useState<string>("app/page.tsx");
	const abortControllerRef = useRef<AbortController | null>(null);

	const backendBaseUrl = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || "http://localhost:8000";

	// 1. Fetch apps list
	const { data: apps = [], error: appsError } = useQuery({
		queryKey: ["web-builder-apps", workspaceId],
		queryFn: () => webBuilderApiService.listApps(workspaceId),
		enabled: !!workspaceId,
	});

	// Check if workspace is feature-gated (403)
	const isFeatureDisabled =
		(appsError as { status?: number; response?: { status?: number } })?.status === 403 ||
		(appsError as { status?: number; response?: { status?: number } })?.response?.status === 403;

	// Auto-select latest app if none selected
	useEffect(() => {
		if (apps.length > 0 && !selectedApp) {
			setSelectedApp(apps[0]);
		}
	}, [apps, selectedApp]);

	// 2. Poll app status when building or generated
	const isBuilding = selectedApp?.status === "building" || selectedApp?.status === "generated";

	const { data: polledApp } = useQuery({
		queryKey: ["web-builder-app-detail", selectedApp?.id, workspaceId],
		queryFn: () => (selectedApp ? webBuilderApiService.getApp(selectedApp.id, workspaceId) : null),
		enabled: !!selectedApp && isBuilding,
		refetchInterval: isBuilding ? 2000 : false,
	});

	useEffect(() => {
		if (
			polledApp &&
			selectedApp &&
			polledApp.id === selectedApp.id &&
			polledApp.status !== selectedApp.status
		) {
			setSelectedApp(polledApp);
			queryClient.invalidateQueries({ queryKey: ["web-builder-apps", workspaceId] });
			if (polledApp.status === "preview_ready") {
				toast.success(t("build_ready"));
				setIframeKey((prev) => prev + 1);
			} else if (polledApp.status === "build_failed") {
				toast.error(t("build_failed_toast"));
				setIsLogsOpen(true);
			}
		}
	}, [polledApp, selectedApp, queryClient, workspaceId]);

	// 2b. Story 31.2b: fetch app detail when the domain modal opens so the modal
	// can render the required TXT verification record (token lives on detail,
	// not the list response).
	const { data: domainDetailApp } = useQuery({
		queryKey: ["web-builder-app-domain-detail", selectedApp?.id, workspaceId],
		queryFn: () => (selectedApp ? webBuilderApiService.getApp(selectedApp.id, workspaceId) : null),
		enabled: !!selectedApp && isDomainModalOpen,
	});
	const domainVerifyToken =
		domainDetailApp?.custom_domain_verify_token ?? selectedApp?.custom_domain_verify_token ?? null;

	// 3. Fetch build logs
	const { data: buildLogs } = useQuery({
		queryKey: ["web-builder-build-logs", selectedApp?.id, workspaceId],
		queryFn: () =>
			selectedApp ? webBuilderApiService.getBuildLogs(selectedApp.id, workspaceId) : null,
		enabled: !!selectedApp && (isLogsOpen || selectedApp?.status === "build_failed"),
		refetchInterval: isBuilding ? 2500 : false,
	});

	// Fetch files when selected app changes or switches to code tab
	useEffect(() => {
		if (selectedApp) {
			webBuilderApiService
				.getAppFiles(selectedApp.id, workspaceId)
				.then((files) => {
					if (files && Object.keys(files).length > 0) {
						setAppFiles(files);
						const keys = Object.keys(files);
						if (!files[selectedFile]) {
							setSelectedFile(keys[0]);
						}
					}
				})
				.catch(() => {});
		}
	}, [selectedApp, workspaceId, selectedFile]);

	// Handle element selected from the preview iframe.
	const handleMarkElementSelected = useCallback(
		(data: {
			selector: string;
			tag: string;
			text: string;
			rect?: MarkToolRect;
			component_hint?: string;
		}) => {
			setSelectedSelector(data.selector);
			setPatchText(data.text || "");
			setSelectedRect(data.rect);
			setComponentHint(data.component_hint);
			toast.info(t("selected_element", { selector: data.selector }));
		},
		[]
	);

	// 4. Real-time Streaming Generation
	const handleStartStreamingGeneration = async () => {
		if (!prompt.trim() || isStreaming) return;

		setIsStreaming(true);
		setStreamTokens("");
		setStreamFiles([]);
		setStreamPhase("planning");
		setStreamMessage(t("init_engine"));

		const controller = new AbortController();
		abortControllerRef.current = controller;

		try {
			await webBuilderApiService.generateWebAppStream(
				{
					workspace_id: workspaceId,
					prompt: prompt.trim(),
					language: "en",
				},
				(event) => {
					if (event.type === "phase") {
						setStreamPhase(event.phase);
						setStreamMessage(event.message);
					} else if (event.type === "token") {
						setStreamTokens((prev) => prev + event.token);
					} else if (event.type === "file_written") {
						setStreamFiles((prev) => (prev.includes(event.path) ? prev : [...prev, event.path]));
					} else if (event.type === "complete") {
						const newApp = event.app;
						toast.success(t("generated_ok", { name: newApp.name }));
						queryClient.invalidateQueries({ queryKey: ["web-builder-apps", workspaceId] });
						setSelectedApp({
							id: newApp.id,
							workspace_id: newApp.workspace_id,
							name: newApp.name,
							slug: newApp.slug,
							status: newApp.status,
							preview_url: newApp.preview_url,
							public_url: newApp.public_url,
							language: "en",
							created_at: new Date().toISOString(),
							updated_at: new Date().toISOString(),
						});
						setIframeKey((prev) => prev + 1);
						setActiveTab("preview");
					}
				},
				controller.signal
			);
		} catch (err: unknown) {
			const error = err as Error;
			if (error.name !== "AbortError") {
				toast.error(error.message || t("stream_error"));
			}
		} finally {
			setIsStreaming(false);
			abortControllerRef.current = null;
		}
	};

	const handleCancelStreaming = () => {
		if (abortControllerRef.current) {
			abortControllerRef.current.abort();
			setIsStreaming(false);
			toast.info(t("generation_cancelled"));
		}
	};

	// 5. Rebuild mutation
	const rebuildMutation = useMutation({
		mutationFn: (appId: string) => webBuilderApiService.triggerBuild(appId, workspaceId),
		onSuccess: () => {
			toast.info(t("build_started"));
			if (selectedApp) {
				setSelectedApp({
					...selectedApp,
					status: "building",
				});
			}
			queryClient.invalidateQueries({ queryKey: ["web-builder-apps", workspaceId] });
			queryClient.invalidateQueries({ queryKey: ["web-builder-app-detail", selectedApp?.id] });
		},
		onError: (err: Error) => {
			toast.error(err?.message || t("rebuild_failed"));
		},
	});

	// 6. Publish mutation
	const publishMutation = useMutation({
		mutationFn: (appId: string) =>
			webBuilderApiService.publishWebApp(appId, {
				workspace_id: workspaceId,
			}),
		onSuccess: (result) => {
			toast.success(t("published_live", { url: result.public_url ?? "" }));
			queryClient.invalidateQueries({ queryKey: ["web-builder-apps", workspaceId] });
			if (selectedApp) {
				setSelectedApp({
					...selectedApp,
					status: "published",
					public_url: result.public_url,
				});
			}
		},
		onError: (err: Error) => {
			toast.error(err?.message || t("deploy_failed_toast"));
		},
	});

	// 7. Mark Tool patch mutation
	const markToolMutation = useMutation({
		mutationFn: () => {
			if (!selectedApp) throw new Error("No app selected");
			return webBuilderApiService.applyMarkToolPatch(selectedApp.id, {
				workspace_id: workspaceId,
				selector: selectedSelector,
				file_path: selectedFile,
				patch: {
					type: patchType,
					value: patchText,
					attribute: patchType === "attribute" ? attributeName : undefined,
				},
				rect: selectedRect,
				component_hint: componentHint,
			});
		},
		onSuccess: (res) => {
			if (res.status === "patched") {
				toast.success(t("patch_applied"));
				setPatchText("");
				setSelectedSelector("");
				setSelectedRect(undefined);
				setComponentHint(undefined);
				setIsMarkToolActive(false);
				if (selectedApp) {
					setSelectedApp({ ...selectedApp, status: "building" });
				}
				queryClient.invalidateQueries({
					queryKey: ["web-builder-apps", workspaceId],
				});
				queryClient.invalidateQueries({
					queryKey: ["web-builder-app-detail", selectedApp?.id, workspaceId],
				});
			} else {
				toast.warning(res.message || t("selector_map_fail"));
			}
		},
		onError: (err: Error) => {
			toast.error(err?.message || t("marktool_failed"));
		},
	});

	// 8. Custom domain mutation
	const customDomainMutation = useMutation({
		mutationFn: () => {
			if (!selectedApp) throw new Error("No app selected");
			return webBuilderApiService.configureCustomDomain(selectedApp.id, {
				workspace_id: workspaceId,
				custom_domain: customDomainInput,
			});
		},
		onSuccess: (res) => {
			toast.success(t("domain_configured", { domain: res.custom_domain ?? "", cname: res.cname_target ?? "" }));
			setIsDomainModalOpen(false);
			queryClient.invalidateQueries({ queryKey: ["web-builder-apps", workspaceId] });
		},
		onError: (err: Error) => {
			toast.error(err?.message || t("domain_config_failed"));
		},
	});

	const rotateTokenMutation = useMutation({
		mutationFn: () => {
			if (!selectedApp) throw new Error("No app selected");
			return webBuilderApiService.rotateCustomDomainToken(selectedApp.id, workspaceId);
		},
		onSuccess: (_res) => {
			toast.success(t("token_rotated"));
			queryClient.invalidateQueries({ queryKey: ["web-builder-apps", workspaceId] });
			queryClient.invalidateQueries({
				queryKey: ["web-builder-app", selectedApp?.id, workspaceId],
			});
		},
		onError: (err: Error) => {
			toast.error(err?.message || t("rotate_failed"));
		},
	});

	const unbindDomainMutation = useMutation({
		mutationFn: () => {
			if (!selectedApp) throw new Error("No app selected");
			return webBuilderApiService.unbindCustomDomain(selectedApp.id, workspaceId);
		},
		onSuccess: () => {
			toast.success(t("domain_removed"));
			setCustomDomainInput("");
			setIsDomainModalOpen(false);
			queryClient.invalidateQueries({ queryKey: ["web-builder-apps", workspaceId] });
		},
		onError: (err: Error) => {
			toast.error(err?.message || t("remove_domain_failed"));
		},
	});

	const localPreviewUrl = selectedApp
		? `${backendBaseUrl}/api/v1/web-builder/apps/${selectedApp.id}/preview?workspace_id=${workspaceId}`
		: "";

	const previewOrigin = useMemo(() => {
		try {
			return localPreviewUrl ? new URL(localPreviewUrl).origin : "";
		} catch {
			return "";
		}
	}, [localPreviewUrl]);

	const currentDisplayUrl =
		selectedApp?.status === "published" && selectedApp.public_url
			? selectedApp.public_url
			: localPreviewUrl;

	if (isFeatureDisabled) {
		return (
			<div
				data-testid="web-builder-disabled-gate"
				className="flex flex-col items-center justify-center h-[calc(100vh-8rem)] p-8 text-center space-y-4 max-w-lg mx-auto"
			>
				<div className="w-12 h-12 rounded-full bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-500">
					<Sparkles className="w-6 h-6" aria-hidden="true" />
				</div>
				<h2 className="text-xl font-bold text-foreground">{t("disabled_title")}</h2>
				<p className="text-sm text-muted-foreground">
					{t("disabled_desc")}
				</p>
			</div>
		);
	}

	return (
		<div className="flex flex-col h-[calc(100vh-4rem)] p-6 space-y-6 max-w-7xl mx-auto">
			{/* Header */}
			<div className="flex items-center justify-between">
				<div>
					<h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
						<Sparkles className="w-6 h-6 text-indigo-500" aria-hidden="true" />
						{t("page_title")}
					</h1>
					<p className="text-sm text-muted-foreground">
						{t("page_sub")}
					</p>
				</div>

				{selectedApp && (
					<div className="flex items-center gap-3">
						<button
							type="button"
							onClick={() => rebuildMutation.mutate(selectedApp.id)}
							disabled={rebuildMutation.isPending || isBuilding}
							className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-border bg-background hover:bg-muted text-foreground transition-colors disabled:opacity-50"
							title={t("rebuild_title")}
						>
							<RefreshCw
								className={`w-3.5 h-3.5 ${rebuildMutation.isPending || isBuilding ? "animate-spin" : ""}`}
							/>
							{t("rebuild")}
						</button>

						<button
							type="button"
							onClick={() => setIsMarkToolActive(!isMarkToolActive)}
							className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
								isMarkToolActive
									? "bg-indigo-600 text-white border-indigo-600 shadow-sm"
									: "bg-background text-foreground border-border hover:bg-muted"
							}`}
						>
							<MousePointerClick className="w-4 h-4" aria-hidden="true" />
							{isMarkToolActive ? t("marktool_active") : t("marktool")}
						</button>

						<button
							type="button"
							onClick={() => setIsDomainModalOpen(true)}
							className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-border bg-background hover:bg-muted text-foreground transition-colors"
						>
							<Settings className="w-4 h-4 text-muted-foreground" aria-hidden="true" />
							{t("custom_domain")}
						</button>

						<button
							type="button"
							onClick={() => publishMutation.mutate(selectedApp.id)}
							disabled={publishMutation.isPending || selectedApp.status === "published"}
							className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-medium rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm transition-colors disabled:opacity-50"
						>
							{publishMutation.isPending ? (
								<>
									<Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
									{t("publishing")}
								</>
							) : selectedApp.status === "published" ? (
								<>
									<CheckCircle2 className="w-4 h-4" aria-hidden="true" />
									{t("published")}
								</>
							) : (
								<>
									<Rocket className="w-4 h-4" aria-hidden="true" />
									{t("publish")}
								</>
							)}
						</button>
					</div>
				)}
			</div>

			{/* Main Content Grid */}
			<div className="grid grid-cols-1 lg:grid-cols-12 gap-6 flex-1 min-h-0">
				{/* Left Column: Prompt Input & Projects List */}
				<div className="lg:col-span-4 flex flex-col space-y-4">
					{/* Prompt Box */}
					<div className="p-4 rounded-xl border border-border bg-card shadow-sm space-y-3">
						<label
							htmlFor="web-app-prompt-input"
							className="text-xs font-semibold text-muted-foreground uppercase tracking-wider block"
						>
							{t("describe_title")}
						</label>
						<textarea
							id="web-app-prompt-input"
							rows={4}
							value={prompt}
							onChange={(e) => setPrompt(e.target.value)}
							placeholder={t("prompt_placeholder")}
							disabled={isStreaming}
							className="w-full text-sm p-3 rounded-lg border border-border bg-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
						/>
						{isStreaming ? (
							<button
								type="button"
								onClick={handleCancelStreaming}
								className="w-full py-2.5 px-4 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-sm font-medium flex items-center justify-center gap-2 shadow-sm transition-colors"
							>
								<Square className="w-4 h-4 fill-current" aria-hidden="true" />
								{t("cancel_generation")}
							</button>
						) : (
							<button
								type="button"
								onClick={handleStartStreamingGeneration}
								disabled={!prompt.trim()}
								className="w-full py-2.5 px-4 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium flex items-center justify-center gap-2 shadow-sm transition-colors disabled:opacity-50"
							>
								<Play className="w-4 h-4 fill-current" aria-hidden="true" />
								{t("generate_app")}
							</button>
						)}
					</div>

					{/* Generated Projects List */}
					<div className="flex-1 flex flex-col p-4 rounded-xl border border-border bg-card shadow-sm overflow-hidden">
						<h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
							{t("generated_projects", { count: apps.length })}
						</h2>
						<div className="flex-1 overflow-y-auto space-y-2 pr-1">
							{apps.length === 0 && !isStreaming && (
								<div className="text-xs text-muted-foreground text-center py-8">
									{t("no_apps")}
								</div>
							)}

							{apps.map((app) => (
								<button
									type="button"
									key={app.id}
									onClick={() => {
										setSelectedApp(app);
										setIsMarkToolActive(false);
										setIsLogsOpen(false);
										setIframeKey((prev) => prev + 1);
									}}
									className={`w-full text-left p-3 rounded-lg border transition-all ${
										selectedApp?.id === app.id
											? "border-indigo-500 bg-indigo-50/5 dark:bg-indigo-950/20 shadow-sm"
											: "border-border hover:border-muted-foreground/40 bg-background"
									}`}
								>
									<div className="flex items-center justify-between mb-1">
										<span className="font-semibold text-foreground truncate">{app.name}</span>
										<span
											className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
												app.status === "published"
													? "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20"
													: app.status === "building"
														? "bg-amber-500/10 text-amber-500 border border-amber-500/20 animate-pulse"
														: app.status === "build_failed" ||
																app.status === "validation_failed" ||
																app.status === "deploy_failed" ||
																app.status === "error"
															? "bg-rose-500/10 text-rose-500 border border-rose-500/20"
															: "bg-indigo-500/10 text-indigo-400 border border-indigo-500/20"
											}`}
										>
											{app.status === "published"
												? t("status_live")
												: app.status === "building"
													? t("status_building")
													: app.status === "build_failed"
														? t("status_build_failed")
														: app.status === "validation_failed"
															? t("status_validation_failed")
															: app.status === "deploy_failed"
																? t("status_deploy_failed")
																: app.status === "preview_ready"
																	? t("status_preview_ready")
																	: t("status_generated")}
										</span>
									</div>
									<p className="text-xs text-muted-foreground truncate">
										{app.status === "published" && app.public_url
											? app.public_url
											: `${app.slug}.apps.nowing.net`}
									</p>
								</button>
							))}
						</div>
					</div>
				</div>

				{/* Right Column: Live Streaming Terminal / Canvas Preview / Code Viewer */}
				<div className="lg:col-span-8 flex flex-col rounded-xl border border-border bg-card shadow-sm overflow-hidden min-h-[600px]">
					{isStreaming ? (
						/* Live SSE Streaming Terminal & File Progress */
						<div className="flex flex-col h-full bg-slate-950 text-slate-100 p-5 space-y-4 font-mono text-xs overflow-hidden">
							{/* Live Banner */}
							<div className="flex items-center justify-between border-b border-slate-800 pb-3">
								<div className="flex items-center gap-2 text-indigo-400">
									<Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
									<span className="font-semibold uppercase tracking-wider">
										{t("stream_title")} — {streamPhase || t("streaming")}
									</span>
								</div>
								<span className="text-slate-400">{streamMessage}</span>
							</div>

							{/* Written Files Progress Checklist */}
							{streamFiles.length > 0 && (
								<div className="flex flex-wrap gap-2 py-1">
									{streamFiles.map((file) => (
										<span
											key={file}
											className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-indigo-950/80 text-indigo-300 border border-indigo-800/60 text-[11px]"
										>
											<FileCode className="w-3 h-3 text-indigo-400" aria-hidden="true" />
											{file}
										</span>
									))}
								</div>
							)}

							{/* Live Code Stream Output */}
							<div className="flex-1 overflow-y-auto rounded-lg bg-slate-900/90 border border-slate-800/80 p-4 leading-relaxed whitespace-pre-wrap select-text">
								{streamTokens || t("connecting_stream")}
							</div>
						</div>
					) : selectedApp ? (
						<div className="flex flex-col h-full">
							{/* Preview & View Controls Bar */}
							<div className="flex items-center justify-between px-4 py-2 border-b border-border bg-muted/40 gap-4">
								{/* URL Display with Status Badge */}
								<div className="flex items-center gap-2 flex-1 min-w-0">
									<Globe className="w-4 h-4 text-muted-foreground shrink-0" aria-hidden="true" />
									<span
										className={`text-[10px] px-1.5 py-0.5 rounded font-mono font-medium shrink-0 ${
											selectedApp.status === "published"
												? "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20"
												: selectedApp.status === "building"
													? "bg-amber-500/10 text-amber-500 border border-amber-500/20"
													: selectedApp.status === "build_failed"
														? "bg-rose-500/10 text-rose-500 border border-rose-500/20"
														: "bg-blue-500/10 text-blue-400 border border-blue-500/20"
										}`}
									>
										{selectedApp.status === "published"
											? t("status_live_upper")
											: selectedApp.status === "building"
												? t("status_building_upper")
												: selectedApp.status === "build_failed"
													? t("status_build_failed_upper")
													: t("status_local_preview")}
									</span>
									<span className="text-xs font-mono text-foreground font-medium truncate">
										{currentDisplayUrl}
									</span>
								</div>

								{/* Controls: Tab Switcher, Device Switcher, Refresh, External */}
								<div className="flex items-center gap-2 shrink-0">
									{/* Device Mode Switcher */}
									<div className="flex items-center bg-background border border-border rounded-lg p-0.5">
										<button
											type="button"
											onClick={() => setDeviceMode("desktop")}
											className={`p-1 rounded ${
												deviceMode === "desktop"
													? "bg-muted text-foreground"
													: "text-muted-foreground hover:text-foreground"
											}`}
											title={t("desktop_view")}
										>
											<Monitor className="w-3.5 h-3.5" aria-hidden="true" />
										</button>
										<button
											type="button"
											onClick={() => setDeviceMode("tablet")}
											className={`p-1 rounded ${
												deviceMode === "tablet"
													? "bg-muted text-foreground"
													: "text-muted-foreground hover:text-foreground"
											}`}
											title={t("tablet_view")}
										>
											<Tablet className="w-3.5 h-3.5" aria-hidden="true" />
										</button>
										<button
											type="button"
											onClick={() => setDeviceMode("mobile")}
											className={`p-1 rounded ${
												deviceMode === "mobile"
													? "bg-muted text-foreground"
													: "text-muted-foreground hover:text-foreground"
											}`}
											title={t("mobile_view")}
										>
											<Smartphone className="w-3.5 h-3.5" aria-hidden="true" />
										</button>
									</div>

									{/* Tab Switcher: Preview vs Code */}
									<div className="flex items-center bg-background border border-border rounded-lg p-0.5">
										<button
											type="button"
											onClick={() => setActiveTab("preview")}
											className={`flex items-center gap-1 px-2 py-1 text-xs rounded font-medium ${
												activeTab === "preview"
													? "bg-indigo-600 text-white"
													: "text-muted-foreground hover:text-foreground"
											}`}
										>
											<Eye className="w-3.5 h-3.5" aria-hidden="true" />
											{t("tab_preview")}
										</button>
										<button
											type="button"
											onClick={() => setActiveTab("code")}
											className={`flex items-center gap-1 px-2 py-1 text-xs rounded font-medium ${
												activeTab === "code"
													? "bg-indigo-600 text-white"
													: "text-muted-foreground hover:text-foreground"
											}`}
										>
											<Code className="w-3.5 h-3.5" aria-hidden="true" />
											{t("tab_code")}
										</button>
									</div>

									{/* Refresh Iframe */}
									<button
										type="button"
										onClick={() => setIframeKey((prev) => prev + 1)}
										className="p-1.5 rounded-lg border border-border bg-background hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
										title={t("reload_preview")}
									>
										<RefreshCw className="w-3.5 h-3.5" aria-hidden="true" />
									</button>

									{/* External Link */}
									<a
										href={localPreviewUrl}
										target="_blank"
										rel="noreferrer"
										className="p-1.5 rounded-lg border border-border bg-background hover:bg-muted text-indigo-500 hover:text-indigo-600 transition-colors"
										title={t("open_new_window")}
									>
										<ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />
									</a>
								</div>
							</div>

							{/* Mark Tool Quick Inspector Bar */}
							{isMarkToolActive && (
								<MarkToolOverlay
									selectedSelector={selectedSelector}
									patchText={patchText}
									patchType={patchType}
									attributeName={attributeName}
									componentHint={componentHint}
									rect={selectedRect}
									isPending={markToolMutation.isPending}
									onSelectorChange={setSelectedSelector}
									onPatchTextChange={setPatchText}
									onPatchTypeChange={setPatchType}
									onAttributeNameChange={setAttributeName}
									onApply={() => markToolMutation.mutate()}
								/>
							)}

							{/* Build Failure Banner & Collapsible Logs */}
							{selectedApp.status === "build_failed" && (
								<div
									data-testid="web-builder-error-banner"
									className="p-4 bg-rose-950/40 border-b border-rose-800/60 space-y-3"
								>
									<div className="flex items-center justify-between">
										<div className="flex items-center gap-2 text-rose-400">
											<AlertCircle className="w-4 h-4 shrink-0" aria-hidden="true" />
											<span className="font-semibold text-xs uppercase tracking-wide">
												{t("build_failed_title")}
											</span>
										</div>
										<div className="flex items-center gap-2">
											<button
												type="button"
												onClick={() => setIsLogsOpen(!isLogsOpen)}
												className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded border border-rose-800/60 bg-rose-900/30 hover:bg-rose-900/50 text-rose-200 transition-colors"
											>
												{isLogsOpen ? (
													<ChevronUp className="w-3.5 h-3.5" aria-hidden="true" />
												) : (
													<ChevronDown className="w-3.5 h-3.5" aria-hidden="true" />
												)}
												{isLogsOpen ? t("hide_logs") : t("view_logs")}
											</button>
											<button
												type="button"
												onClick={() => rebuildMutation.mutate(selectedApp.id)}
												disabled={rebuildMutation.isPending}
												className="flex items-center gap-1 px-3 py-1 text-xs font-medium rounded bg-rose-600 hover:bg-rose-700 text-white transition-colors"
											>
												<RefreshCw
													className={`w-3.5 h-3.5 ${rebuildMutation.isPending ? "animate-spin" : ""}`}
												/>
												{t("rebuild_retry")}
											</button>
										</div>
									</div>
									<p className="text-xs text-rose-300 font-mono line-clamp-2">
										{selectedApp.description ||
											t("build_failed_desc")}
									</p>
									{isLogsOpen && (
										<div
											data-testid="web-builder-logs-panel"
											className="p-3 bg-black/80 border border-rose-900/60 rounded-lg max-h-56 overflow-y-auto font-mono text-xs text-rose-200 whitespace-pre-wrap leading-relaxed select-text"
										>
											{buildLogs?.logs || t("loading_logs")}
										</div>
									)}
								</div>
							)}

							{/* Canvas Frame or Code Viewer */}
							{activeTab === "preview" ? (
								<div className="flex-1 bg-neutral-900/90 flex items-center justify-center p-3 overflow-hidden">
									{isBuilding ? (
										<div
											data-testid="web-builder-building-indicator"
											className="flex flex-col items-center justify-center p-8 space-y-4 text-center max-w-sm"
										>
											<Loader2
												className="w-8 h-8 text-indigo-500 animate-spin"
												aria-hidden="true"
											/>
											<div className="space-y-1">
												<h3 className="text-sm font-semibold text-slate-100">
													{t("building_app")}
												</h3>
												<p className="text-xs text-slate-400">
													{t("building_desc")}
												</p>
											</div>
										</div>
									) : (
										<div
											className={`h-full bg-slate-950 rounded-lg shadow-2xl border border-border/40 overflow-hidden transition-all duration-300 ${
												deviceMode === "desktop"
													? "w-full"
													: deviceMode === "tablet"
														? "w-[768px]"
														: "w-[375px]"
											}`}
										>
											<PreviewIframe
												src={localPreviewUrl}
												appId={selectedApp.id}
												title={selectedApp.name}
												isMarkToolActive={isMarkToolActive}
												previewOrigin={previewOrigin}
												onMarkElementSelected={handleMarkElementSelected}
												iframeKey={iframeKey}
											/>
										</div>
									)}
								</div>
							) : (
								/* Code Viewer Tab */
								<div className="flex-1 flex flex-col bg-slate-950 text-slate-100 overflow-hidden">
									{/* File Tabs */}
									<div className="flex items-center gap-1 px-4 py-2 border-b border-slate-800 bg-slate-900/80 overflow-x-auto">
										{Object.keys(appFiles).map((path) => (
											<button
												type="button"
												key={path}
												onClick={() => setSelectedFile(path)}
												className={`flex items-center gap-1.5 px-3 py-1 text-xs rounded-md transition-colors ${
													selectedFile === path
														? "bg-indigo-600 text-white font-medium shadow-sm"
														: "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
												}`}
											>
												<FileCode className="w-3.5 h-3.5" aria-hidden="true" />
												{path}
											</button>
										))}
									</div>

									{/* Code Content */}
									<div className="flex-1 p-4 overflow-y-auto font-mono text-xs leading-relaxed selection:bg-indigo-500 selection:text-white">
										<pre className="text-slate-200">
											{appFiles[selectedFile] || t("file_empty")}
										</pre>
									</div>
								</div>
							)}
						</div>
					) : (
						<div className="flex-1 flex flex-col items-center justify-center text-center p-8 space-y-3 text-muted-foreground">
							<Sparkles
								className="w-10 h-10 text-muted-foreground/40 stroke-1"
								aria-hidden="true"
							/>
							<p className="text-sm">
								{t("empty_state")}
							</p>
						</div>
					)}
				</div>
			</div>

			{/* Custom Domain Modal */}
			{isDomainModalOpen && selectedApp && (
				<div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
					<div className="bg-card border border-border rounded-xl p-6 max-w-md w-full shadow-2xl space-y-4">
						<h3 className="text-lg font-bold text-foreground">{t("domain_title")}</h3>
						<p className="text-xs text-muted-foreground">
							{t("domain_desc_1")}{" "}
							<code className="text-indigo-400 font-mono">cname-ingress.apps.nowing.net</code> to
							{t("domain_desc_2")}
						</p>
						{domainVerifyToken && (
							<div className="rounded-lg border border-border bg-muted/40 p-3 space-y-1.5">
								<div className="flex items-center justify-between">
									<p className="text-[11px] font-medium text-foreground">
										{t("verify_ownership")}
									</p>
									<button
										type="button"
										onClick={() => {
											navigator.clipboard.writeText(`nowing-verify=${domainVerifyToken}`);
											toast.success(t("txt_copied"));
										}}
										className="text-[10px] text-indigo-400 hover:text-indigo-300 font-medium underline"
									>
										{t("copy_value")}
									</button>
								</div>
								<div className="text-[11px] font-mono text-muted-foreground space-y-0.5">
									<div>
										<span className="text-foreground">{t("name_host")} </span>
										<code className="text-indigo-400">
											_nowing-verify.
											{customDomainInput.trim() || "<your-domain>"}
										</code>
									</div>
									<div className="break-all flex items-center justify-between gap-1">
										<span>
											<span className="text-foreground">{t("value_label")} </span>
											<code className="text-indigo-400">nowing-verify={domainVerifyToken}</code>
										</span>
									</div>
								</div>
								<div className="flex items-center justify-between text-[10px] text-muted-foreground pt-1">
									<span>{t("dns_propagate")}</span>
									<button
										type="button"
										onClick={() => rotateTokenMutation.mutate()}
										disabled={rotateTokenMutation.isPending}
										className="text-amber-400 hover:text-amber-300 underline disabled:opacity-50"
									>
										{rotateTokenMutation.isPending ? t("rotating") : t("rotate_token")}
									</button>
								</div>
							</div>
						)}
						<input
							type="text"
							placeholder={t("domain_placeholder")}
							value={customDomainInput}
							onChange={(e) => setCustomDomainInput(e.target.value)}
							className="w-full text-sm p-2.5 rounded-lg border border-border bg-background focus:outline-none focus:ring-2 focus:ring-indigo-500"
						/>
						<div className="flex items-center justify-between">
							{selectedApp.custom_domain ? (
								<button
									type="button"
									onClick={() => unbindDomainMutation.mutate()}
									disabled={unbindDomainMutation.isPending}
									className="px-3 py-1.5 text-xs rounded-lg border border-destructive/40 text-destructive hover:bg-destructive/10 disabled:opacity-50"
								>
									{unbindDomainMutation.isPending ? t("removing") : t("remove_domain")}
								</button>
							) : (
								<span />
							)}
							<div className="flex justify-end gap-2">
								<button
									type="button"
									onClick={() => setIsDomainModalOpen(false)}
									className="px-3 py-1.5 text-xs rounded-lg border border-border hover:bg-muted text-foreground"
								>
									{t("cancel")}
								</button>
								<button
									type="button"
									onClick={() => customDomainMutation.mutate()}
									disabled={customDomainMutation.isPending || !customDomainInput.trim()}
									className="px-4 py-1.5 text-xs rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-medium disabled:opacity-50"
								>
									{customDomainMutation.isPending ? t("verifying_dns") : t("save_domain")}
								</button>
							</div>
						</div>
					</div>
				</div>
			)}
		</div>
	);
}

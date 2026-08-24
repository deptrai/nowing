"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
	CheckCircle2,
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
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import type { WorkspaceApp } from "@/contracts/types/web-builder.types";
import { webBuilderApiService } from "@/lib/apis/web-builder-api.service";

export default function WebBuilderPage() {
	const params = useParams();
	const workspaceId = Number(params.workspace_id);
	const queryClient = useQueryClient();

	const [prompt, setPrompt] = useState("");
	const [selectedApp, setSelectedApp] = useState<WorkspaceApp | null>(null);
	const [isMarkToolActive, setIsMarkToolActive] = useState(false);
	const [selectedSelector, setSelectedSelector] = useState("");
	const [patchText, setPatchText] = useState("");
	const [customDomainInput, setCustomDomainInput] = useState("");
	const [isDomainModalOpen, setIsDomainModalOpen] = useState(false);

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
	const { data: apps = [] } = useQuery({
		queryKey: ["web-builder-apps", workspaceId],
		queryFn: () => webBuilderApiService.listApps(workspaceId),
		enabled: !!workspaceId,
	});

	// Auto-select latest app if none selected
	useEffect(() => {
		if (apps.length > 0 && !selectedApp) {
			setSelectedApp(apps[0]);
		}
	}, [apps, selectedApp]);

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

	// Listen to messages from Preview iframe (Mark Tool Click-To-Inspect)
	useEffect(() => {
		const handleIframeMessage = (event: MessageEvent) => {
			if (event.data?.type === "MARK_ELEMENT_SELECTED") {
				setSelectedSelector(event.data.selector || "");
				setPatchText(event.data.text || "");
				toast.info(`Selected element: ${event.data.selector}`);
			}
		};

		window.addEventListener("message", handleIframeMessage);
		return () => window.removeEventListener("message", handleIframeMessage);
	}, []);

	// Send toggle message to iframe when Mark Tool toggles
	useEffect(() => {
		const iframe = document.getElementById(
			"web-builder-preview-iframe"
		) as HTMLIFrameElement | null;
		if (iframe?.contentWindow) {
			iframe.contentWindow.postMessage({ type: "TOGGLE_MARK_TOOL", active: isMarkToolActive }, "*");
		}
	}, [isMarkToolActive]);

	// 2. Real-time Streaming Generation
	const handleStartStreamingGeneration = async () => {
		if (!prompt.trim() || isStreaming) return;

		setIsStreaming(true);
		setStreamTokens("");
		setStreamFiles([]);
		setStreamPhase("planning");
		setStreamMessage("Initializing generation engine...");

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
						toast.success(`Generated "${newApp.name}" successfully!`);
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
				toast.error(error.message || "Streaming generation encountered an error");
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
			toast.info("Generation cancelled");
		}
	};

	// 3. Publish mutation
	const publishMutation = useMutation({
		mutationFn: (appId: string) =>
			webBuilderApiService.publishWebApp(appId, {
				workspace_id: workspaceId,
			}),
		onSuccess: (result) => {
			toast.success(`Published live to ${result.public_url}`);
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
			toast.error(err?.message || "Deployment failed");
		},
	});

	// 4. Mark Tool patch mutation
	const markToolMutation = useMutation({
		mutationFn: () => {
			if (!selectedApp) throw new Error("No app selected");
			return webBuilderApiService.applyMarkToolPatch(selectedApp.id, {
				workspace_id: workspaceId,
				selector: selectedSelector,
				patch: {
					type: "text",
					value: patchText,
				},
			});
		},
		onSuccess: (res) => {
			if (res.status === "patched") {
				toast.success("Visual modification applied to JSX!");
				setPatchText("");
				setSelectedSelector("");
				setIsMarkToolActive(false);
				setIframeKey((prev) => prev + 1);
			} else {
				toast.warning(res.message || "Could not map selector to JSX element");
			}
		},
		onError: (err: Error) => {
			toast.error(err?.message || "Mark tool mutation failed");
		},
	});

	// 5. Custom domain mutation
	const customDomainMutation = useMutation({
		mutationFn: () => {
			if (!selectedApp) throw new Error("No app selected");
			return webBuilderApiService.configureCustomDomain(selectedApp.id, {
				workspace_id: workspaceId,
				custom_domain: customDomainInput,
			});
		},
		onSuccess: (res) => {
			toast.success(`Domain ${res.custom_domain} configured! Point CNAME to ${res.cname_target}`);
			setIsDomainModalOpen(false);
			queryClient.invalidateQueries({ queryKey: ["web-builder-apps", workspaceId] });
		},
		onError: (err: Error) => {
			toast.error(err?.message || "Failed to configure custom domain");
		},
	});

	const localPreviewUrl = selectedApp
		? `${backendBaseUrl}/api/v1/web-builder/apps/${selectedApp.id}/preview`
		: "";

	const currentDisplayUrl =
		selectedApp?.status === "published" && selectedApp.public_url
			? selectedApp.public_url
			: localPreviewUrl;

	return (
		<div className="flex flex-col h-[calc(100vh-4rem)] p-6 space-y-6 max-w-7xl mx-auto">
			{/* Header */}
			<div className="flex items-center justify-between">
				<div>
					<h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
						<Sparkles className="w-6 h-6 text-indigo-500" />
						Full-Stack Web App Builder
					</h1>
					<p className="text-sm text-muted-foreground">
						Generate full-stack Next.js & Tailwind apps with live streaming, interactive preview,
						Design Mark Tool, and 1-Click hosting.
					</p>
				</div>

				{selectedApp && (
					<div className="flex items-center gap-3">
						<button
							type="button"
							onClick={() => setIsMarkToolActive(!isMarkToolActive)}
							className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
								isMarkToolActive
									? "bg-indigo-600 text-white border-indigo-600 shadow-sm"
									: "bg-background text-foreground border-border hover:bg-muted"
							}`}
						>
							<MousePointerClick className="w-4 h-4" />
							{isMarkToolActive ? "Mark Tool: Active" : "Design View Mark Tool"}
						</button>

						<button
							type="button"
							onClick={() => setIsDomainModalOpen(true)}
							className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-border bg-background hover:bg-muted text-foreground transition-colors"
						>
							<Settings className="w-4 h-4 text-muted-foreground" />
							Custom Domain
						</button>

						<button
							type="button"
							onClick={() => publishMutation.mutate(selectedApp.id)}
							disabled={publishMutation.isPending || selectedApp.status === "published"}
							className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-medium rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm transition-colors disabled:opacity-50"
						>
							{publishMutation.isPending ? (
								<>
									<Loader2 className="w-4 h-4 animate-spin" />
									Publishing...
								</>
							) : selectedApp.status === "published" ? (
								<>
									<CheckCircle2 className="w-4 h-4" />
									Published
								</>
							) : (
								<>
									<Rocket className="w-4 h-4" />
									1-Click Publish
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
							Describe Your Web Application
						</label>
						<textarea
							id="web-app-prompt-input"
							rows={4}
							value={prompt}
							onChange={(e) => setPrompt(e.target.value)}
							placeholder="E.g. A modern SaaS landing page for an AI accounting tool with dark mode, interactive pricing tiers, and contact form..."
							disabled={isStreaming}
							className="w-full text-sm p-3 rounded-lg border border-border bg-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
						/>
						{isStreaming ? (
							<button
								type="button"
								onClick={handleCancelStreaming}
								className="w-full py-2.5 px-4 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-sm font-medium flex items-center justify-center gap-2 shadow-sm transition-colors"
							>
								<Square className="w-4 h-4 fill-current" />
								Cancel Generation
							</button>
						) : (
							<button
								type="button"
								onClick={handleStartStreamingGeneration}
								disabled={!prompt.trim()}
								className="w-full py-2.5 px-4 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium flex items-center justify-center gap-2 shadow-sm transition-colors disabled:opacity-50"
							>
								<Play className="w-4 h-4 fill-current" />
								Generate App (Live Stream)
							</button>
						)}
					</div>

					{/* Generated Projects List */}
					<div className="flex-1 flex flex-col p-4 rounded-xl border border-border bg-card shadow-sm overflow-hidden">
						<h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
							Generated Projects ({apps.length})
						</h2>
						<div className="flex-1 overflow-y-auto space-y-2 pr-1">
							{apps.length === 0 && !isStreaming && (
								<div className="text-xs text-muted-foreground text-center py-8">
									No web applications generated yet.
								</div>
							)}

							{apps.map((app) => (
								<button
									type="button"
									key={app.id}
									onClick={() => {
										setSelectedApp(app);
										setIsMarkToolActive(false);
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
													: "bg-indigo-500/10 text-indigo-400 border border-indigo-500/20"
											}`}
										>
											{app.status === "published" ? "Live HTTPS" : "Local Ready"}
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
				<div className="lg:col-span-8 flex flex-col rounded-xl border border-border bg-card shadow-sm overflow-hidden">
					{isStreaming ? (
						/* Live SSE Streaming Terminal & File Progress */
						<div className="flex flex-col h-full bg-slate-950 text-slate-100 p-5 space-y-4 font-mono text-xs overflow-hidden">
							{/* Live Banner */}
							<div className="flex items-center justify-between border-b border-slate-800 pb-3">
								<div className="flex items-center gap-2 text-indigo-400">
									<Loader2 className="w-4 h-4 animate-spin" />
									<span className="font-semibold uppercase tracking-wider">
										AI Web Builder — {streamPhase || "Streaming"}
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
											<FileCode className="w-3 h-3 text-indigo-400" />
											{file}
										</span>
									))}
								</div>
							)}

							{/* Live Code Stream Output */}
							<div className="flex-1 overflow-y-auto rounded-lg bg-slate-900/90 border border-slate-800/80 p-4 leading-relaxed whitespace-pre-wrap select-text">
								{streamTokens || "Connecting to model stream..."}
							</div>
						</div>
					) : selectedApp ? (
						<div className="flex flex-col h-full">
							{/* Preview & View Controls Bar */}
							<div className="flex items-center justify-between px-4 py-2 border-b border-border bg-muted/40 gap-4">
								{/* URL Display with Status Badge */}
								<div className="flex items-center gap-2 flex-1 min-w-0">
									<Globe className="w-4 h-4 text-muted-foreground shrink-0" />
									<span
										className={`text-[10px] px-1.5 py-0.5 rounded font-mono font-medium shrink-0 ${
											selectedApp.status === "published"
												? "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20"
												: "bg-blue-500/10 text-blue-400 border border-blue-500/20"
										}`}
									>
										{selectedApp.status === "published" ? "LIVE HTTPS" : "LOCAL PREVIEW"}
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
											title="Desktop View (100%)"
										>
											<Monitor className="w-3.5 h-3.5" />
										</button>
										<button
											type="button"
											onClick={() => setDeviceMode("tablet")}
											className={`p-1 rounded ${
												deviceMode === "tablet"
													? "bg-muted text-foreground"
													: "text-muted-foreground hover:text-foreground"
											}`}
											title="Tablet View (768px)"
										>
											<Tablet className="w-3.5 h-3.5" />
										</button>
										<button
											type="button"
											onClick={() => setDeviceMode("mobile")}
											className={`p-1 rounded ${
												deviceMode === "mobile"
													? "bg-muted text-foreground"
													: "text-muted-foreground hover:text-foreground"
											}`}
											title="Mobile View (375px)"
										>
											<Smartphone className="w-3.5 h-3.5" />
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
											<Eye className="w-3.5 h-3.5" />
											Preview
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
											<Code className="w-3.5 h-3.5" />
											Code
										</button>
									</div>

									{/* Refresh Iframe */}
									<button
										type="button"
										onClick={() => setIframeKey((prev) => prev + 1)}
										className="p-1.5 rounded-lg border border-border bg-background hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
										title="Reload Preview"
									>
										<RefreshCw className="w-3.5 h-3.5" />
									</button>

									{/* External Link */}
									<a
										href={localPreviewUrl}
										target="_blank"
										rel="noreferrer"
										className="p-1.5 rounded-lg border border-border bg-background hover:bg-muted text-indigo-500 hover:text-indigo-600 transition-colors"
										title="Open In New Window"
									>
										<ExternalLink className="w-3.5 h-3.5" />
									</a>
								</div>
							</div>

							{/* Mark Tool Quick Inspector Bar */}
							{isMarkToolActive && (
								<div className="p-3 bg-indigo-50/20 dark:bg-indigo-950/30 border-b border-indigo-500/30 flex items-center gap-3">
									<input
										type="text"
										placeholder="DOM Selector (e.g. #hero-title or h1) — Click element in preview to select"
										value={selectedSelector}
										onChange={(e) => setSelectedSelector(e.target.value)}
										className="text-xs px-2.5 py-1.5 rounded border border-border bg-background flex-1 focus:ring-1 focus:ring-indigo-500"
									/>
									<input
										type="text"
										placeholder="New Text Content..."
										value={patchText}
										onChange={(e) => setPatchText(e.target.value)}
										className="text-xs px-2.5 py-1.5 rounded border border-border bg-background flex-1 focus:ring-1 focus:ring-indigo-500"
									/>
									<button
										type="button"
										onClick={() => markToolMutation.mutate()}
										disabled={markToolMutation.isPending || !selectedSelector}
										className="px-3 py-1.5 text-xs font-medium bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50 transition-colors"
									>
										{markToolMutation.isPending ? "Patching..." : "Apply Patch"}
									</button>
								</div>
							)}

							{/* Canvas Frame or Code Viewer */}
							{activeTab === "preview" ? (
								<div className="flex-1 bg-neutral-900/90 flex items-center justify-center p-3 overflow-hidden">
									<div
										className={`h-full bg-slate-950 rounded-lg shadow-2xl border border-border/40 overflow-hidden transition-all duration-300 ${
											deviceMode === "desktop"
												? "w-full"
												: deviceMode === "tablet"
													? "w-[768px]"
													: "w-[375px]"
										}`}
									>
										<iframe
											key={`${selectedApp.id}-${iframeKey}`}
											id="web-builder-preview-iframe"
											src={localPreviewUrl}
											title={selectedApp.name}
											sandbox="allow-scripts allow-forms allow-same-origin"
											className="w-full h-full border-0 bg-slate-950"
										/>
									</div>
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
												<FileCode className="w-3.5 h-3.5" />
												{path}
											</button>
										))}
									</div>

									{/* Code Content */}
									<div className="flex-1 p-4 overflow-y-auto font-mono text-xs leading-relaxed selection:bg-indigo-500 selection:text-white">
										<pre className="text-slate-200">
											{appFiles[selectedFile] || "// File empty or loading..."}
										</pre>
									</div>
								</div>
							)}
						</div>
					) : (
						<div className="flex-1 flex flex-col items-center justify-center text-center p-8 space-y-3 text-muted-foreground">
							<Sparkles className="w-10 h-10 text-muted-foreground/40 stroke-1" />
							<p className="text-sm">
								Enter a prompt on the left and click Generate App to start live building.
							</p>
						</div>
					)}
				</div>
			</div>

			{/* Custom Domain Modal */}
			{isDomainModalOpen && selectedApp && (
				<div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
					<div className="bg-card border border-border rounded-xl p-6 max-w-md w-full shadow-2xl space-y-4">
						<h3 className="text-lg font-bold text-foreground">Connect Custom Domain</h3>
						<p className="text-xs text-muted-foreground">
							Point your DNS CNAME record to{" "}
							<code className="text-indigo-400 font-mono">cname-ingress.apps.nowing.net</code> to
							bind your custom domain.
						</p>
						<input
							type="text"
							placeholder="e.g. app.mycompany.com"
							value={customDomainInput}
							onChange={(e) => setCustomDomainInput(e.target.value)}
							className="w-full text-sm p-2.5 rounded-lg border border-border bg-background focus:outline-none focus:ring-2 focus:ring-indigo-500"
						/>
						<div className="flex justify-end gap-2">
							<button
								type="button"
								onClick={() => setIsDomainModalOpen(false)}
								className="px-3 py-1.5 text-xs rounded-lg border border-border hover:bg-muted text-foreground"
							>
								Cancel
							</button>
							<button
								type="button"
								onClick={() => customDomainMutation.mutate()}
								disabled={customDomainMutation.isPending || !customDomainInput.trim()}
								className="px-4 py-1.5 text-xs rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-medium disabled:opacity-50"
							>
								{customDomainMutation.isPending ? "Verifying DNS..." : "Save Domain"}
							</button>
						</div>
					</div>
				</div>
			)}
		</div>
	);
}

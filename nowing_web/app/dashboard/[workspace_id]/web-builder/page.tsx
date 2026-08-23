"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
	Code,
	Copy,
	ExternalLink,
	Globe,
	Loader2,
	MousePointerClick,
	Play,
	Rocket,
	Settings,
	Sparkles,
} from "lucide-react";
import { useParams } from "next/navigation";
import { useState } from "react";
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

	// 1. Fetch apps list
	const { data: apps = [] } = useQuery({
		queryKey: ["web-builder-apps", workspaceId],
		queryFn: () => webBuilderApiService.listApps(workspaceId),
		enabled: !!workspaceId,
	});

	// 2. Generate app mutation
	const generateMutation = useMutation({
		mutationFn: (userPrompt: string) =>
			webBuilderApiService.generateWebApp({
				workspace_id: workspaceId,
				prompt: userPrompt,
				language: "en",
			}),
		onSuccess: (result) => {
			toast.success("Web application generated successfully!");
			queryClient.invalidateQueries({ queryKey: ["web-builder-apps", workspaceId] });
			setPrompt("");
			setSelectedApp({
				id: result.app_id,
				workspace_id: result.workspace_id,
				name: result.name,
				slug: result.slug,
				status: result.status,
				preview_url: result.preview_url,
				public_url: result.public_url,
				language: "en",
				created_at: new Date().toISOString(),
				updated_at: new Date().toISOString(),
			});
		},
		onError: (err: Error) => {
			toast.error(err?.message || "Failed to generate application");
		},
	});

	// 3. Publish mutation
	const publishMutation = useMutation({
		mutationFn: (appId: string) =>
			webBuilderApiService.publishWebApp(appId, {
				workspace_id: workspaceId,
			}),
		onSuccess: (result) => {
			toast.success(`Published to ${result.public_url}`);
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
						Generate full-stack Next.js & Tailwind apps from prompt, edit visually with Design Mark
						Tool, and host with 1-click on *.apps.nowing.net.
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
							className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-border bg-background hover:bg-muted text-foreground"
						>
							<Settings className="w-4 h-4" />
							Custom Domain
						</button>

						<button
							type="button"
							onClick={() => publishMutation.mutate(selectedApp.id)}
							disabled={publishMutation.isPending}
							className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-semibold rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm transition-colors disabled:opacity-50"
						>
							{publishMutation.isPending ? (
								<Loader2 className="w-4 h-4 animate-spin" />
							) : (
								<Rocket className="w-4 h-4" />
							)}
							1-Click Publish
						</button>
					</div>
				)}
			</div>

			{/* Main Grid */}
			<div className="grid grid-cols-1 lg:grid-cols-12 gap-6 flex-1 min-h-0">
				{/* Left Column: Prompt Input & Apps History */}
				<div className="lg:col-span-4 flex flex-col space-y-4">
					<div className="p-4 rounded-xl border border-border bg-card shadow-sm space-y-3">
						<label
							htmlFor="web-app-prompt-input"
							className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
						>
							Describe your Web Application
						</label>
						<textarea
							id="web-app-prompt-input"
							rows={4}
							value={prompt}
							onChange={(e) => setPrompt(e.target.value)}
							placeholder="E.g. A modern SaaS landing page for an AI accounting tool with dark mode, interactive pricing tiers, and contact form..."
							className="w-full text-sm p-3 rounded-lg border border-border bg-background focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
						/>
						<button
							type="button"
							onClick={() => generateMutation.mutate(prompt)}
							disabled={generateMutation.isPending || !prompt.trim()}
							className="w-full py-2.5 px-4 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium flex items-center justify-center gap-2 shadow-sm transition-colors disabled:opacity-50"
						>
							{generateMutation.isPending ? (
								<>
									<Loader2 className="w-4 h-4 animate-spin" />
									Generating Next.js App...
								</>
							) : (
								<>
									<Play className="w-4 h-4 fill-white" />
									Generate App
								</>
							)}
						</button>
					</div>

					{/* Generated Apps List */}
					<div className="p-4 rounded-xl border border-border bg-card shadow-sm flex-1 flex flex-col min-h-0">
						<h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
							Generated Projects ({apps.length})
						</h3>
						<div className="space-y-2 overflow-y-auto flex-1 pr-1">
							{apps.map((app) => (
								<button
									type="button"
									key={app.id}
									onClick={() => setSelectedApp(app)}
									className={`w-full text-left p-3 rounded-lg border text-sm cursor-pointer transition-all ${
										selectedApp?.id === app.id
											? "border-indigo-500 bg-indigo-50/10 dark:bg-indigo-950/20"
											: "border-border hover:border-muted-foreground/40 bg-background"
									}`}
								>
									<div className="flex items-center justify-between mb-1">
										<span className="font-semibold text-foreground truncate">{app.name}</span>
										<span
											className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
												app.status === "published"
													? "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20"
													: "bg-muted text-muted-foreground"
											}`}
										>
											{app.status}
										</span>
									</div>
									<p className="text-xs text-muted-foreground truncate">
										{app.slug}.apps.nowing.net
									</p>
								</button>
							))}
						</div>
					</div>
				</div>

				{/* Right Column: Live Canvas Preview / Mark Tool */}
				<div className="lg:col-span-8 flex flex-col rounded-xl border border-border bg-card shadow-sm overflow-hidden">
					{selectedApp ? (
						<div className="flex flex-col h-full">
							{/* Preview Bar */}
							<div className="flex items-center justify-between px-4 py-2.5 border-b border-border bg-muted/30">
								<div className="flex items-center gap-2">
									<Globe className="w-4 h-4 text-muted-foreground" />
									<span className="text-xs font-mono text-foreground font-medium">
										{selectedApp.public_url || `https://${selectedApp.slug}.apps.nowing.net`}
									</span>
								</div>
								{selectedApp.public_url && (
									<a
										href={selectedApp.public_url}
										target="_blank"
										rel="noreferrer"
										className="text-xs text-indigo-500 hover:text-indigo-600 flex items-center gap-1 font-medium"
									>
										Open Live
										<ExternalLink className="w-3 h-3" />
									</a>
								)}
							</div>

							{/* Mark Tool Quick Inspector Box */}
							{isMarkToolActive && (
								<div className="p-3 bg-indigo-50/20 dark:bg-indigo-950/30 border-b border-indigo-500/30 flex items-center gap-3">
									<input
										type="text"
										placeholder="DOM Selector (e.g. #hero-title or h1)"
										value={selectedSelector}
										onChange={(e) => setSelectedSelector(e.target.value)}
										className="text-xs px-2.5 py-1.5 rounded border border-border bg-background flex-1"
									/>
									<input
										type="text"
										placeholder="New Text Content..."
										value={patchText}
										onChange={(e) => setPatchText(e.target.value)}
										className="text-xs px-2.5 py-1.5 rounded border border-border bg-background flex-1"
									/>
									<button
										type="button"
										onClick={() => markToolMutation.mutate()}
										disabled={markToolMutation.isPending || !selectedSelector}
										className="px-3 py-1.5 text-xs font-medium bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50"
									>
										{markToolMutation.isPending ? "Patching..." : "Apply Patch"}
									</button>
								</div>
							)}

							{/* Canvas Frame */}
							<div className="flex-1 bg-neutral-900 flex items-center justify-center p-4">
								<div className="w-full h-full bg-white dark:bg-neutral-950 rounded-lg shadow-lg border border-border/40 flex flex-col items-center justify-center text-center p-8">
									<div className="max-w-md space-y-4">
										<div className="w-12 h-12 rounded-full bg-indigo-500/10 text-indigo-500 flex items-center justify-center mx-auto">
											<Code className="w-6 h-6" />
										</div>
										<h2 className="text-lg font-bold text-foreground">{selectedApp.name}</h2>
										<p className="text-xs text-muted-foreground">
											Preview Canvas is ready. The standalone Next.js container has been compiled
											and routed for workspace {selectedApp.workspace_id}.
										</p>
										{selectedApp.public_url && (
											<div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-between text-xs text-emerald-600 font-mono">
												<span className="truncate">{selectedApp.public_url}</span>
												<button
													type="button"
													onClick={() => {
														if (selectedApp.public_url) {
															navigator.clipboard.writeText(selectedApp.public_url);
															toast.success("Copied to clipboard!");
														}
													}}
													className="p-1 hover:bg-emerald-500/20 rounded"
												>
													<Copy className="w-3.5 h-3.5" />
												</button>
											</div>
										)}
									</div>
								</div>
							</div>
						</div>
					) : (
						<div className="flex-1 flex flex-col items-center justify-center text-center p-8 space-y-3 text-muted-foreground">
							<Sparkles className="w-10 h-10 text-muted-foreground/40 stroke-1" />
							<p className="text-sm">
								Select or generate a project on the left to start editing and previewing.
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

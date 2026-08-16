import { useSetAtom } from "jotai";
import {
	Boxes,
	FileText,
	Image,
	Mic,
	Presentation,
	RefreshCw,
	Search,
	TriangleAlert,
} from "lucide-react";
import { useMemo, useState } from "react";
import { openReportPanelAtom } from "@/atoms/chat/report-panel.atom";
import { MobileReportPanel } from "@/components/report-panel/report-panel";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { useLibraryArtifacts } from "../hooks/use-library-artifacts";
import type { LibraryArtifact, LibraryArtifactKind } from "../model/artifact";
import { ArtifactCard } from "./artifact-card";
import { KIND_META, KIND_ORDER } from "./kind-meta";
import { MediaViewerDialog } from "./media-viewer-dialog";

const SKELETON_KEYS = ["s1", "s2", "s3", "s4", "s5", "s6"];

function LoadingState() {
	return (
		<div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
			{SKELETON_KEYS.map((key) => (
				<div key={key} className="h-[68px] animate-pulse rounded-xl border bg-muted/40" />
			))}
		</div>
	);
}

function ErrorState({ onRetry }: { onRetry: () => void }) {
	return (
		<div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed py-16 text-center">
			<span className="flex size-10 items-center justify-center rounded-full bg-destructive/10 text-destructive">
				<TriangleAlert className="size-5" />
			</span>
			<div>
				<p className="text-sm font-semibold text-foreground">Couldn't load artifacts</p>
				<p className="mt-1 text-xs text-muted-foreground">
					Something went wrong fetching this workspace's deliverables.
				</p>
			</div>
			<Button variant="outline" size="sm" onClick={onRetry} className="h-8 text-xs">
				<RefreshCw className="size-3.5 mr-1.5" />
				Retry
			</Button>
		</div>
	);
}

function EmptyState() {
	return (
		<div className="rounded-xl border border-dashed border-border/70 bg-card p-8 sm:p-12 text-center">
			<div className="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-400">
				<Boxes className="h-5 w-5" aria-hidden />
			</div>
			<h3 className="mt-3 font-serif text-lg sm:text-xl font-normal text-foreground">
				No artifacts yet
			</h3>
			<p className="mt-1.5 text-xs text-muted-foreground max-w-md mx-auto leading-relaxed">
				Artifacts collect the reports, resumes, podcasts, presentations, and images Nowing creates
				for this workspace. Generated deliverables from your chats will appear here automatically.
			</p>
		</div>
	);
}

export function ArtifactsLibrary({ workspaceId }: { workspaceId: number }) {
	const { artifacts, loading, error, refresh } = useLibraryArtifacts(workspaceId);
	const openReportPanel = useSetAtom(openReportPanelAtom);
	const [selectedMedia, setSelectedMedia] = useState<LibraryArtifact | null>(null);
	const [activeTab, setActiveTab] = useState<string>("all");
	const [searchQuery, setSearchQuery] = useState<string>("");

	const filteredArtifacts = useMemo(() => {
		return artifacts.filter((item) => {
			if (activeTab !== "all" && item.kind !== activeTab) return false;
			if (searchQuery.trim()) {
				const query = searchQuery.toLowerCase();
				return item.title.toLowerCase().includes(query) || item.kind.toLowerCase().includes(query);
			}
			return true;
		});
	}, [artifacts, activeTab, searchQuery]);

	const countsByKind = useMemo(() => {
		const counts: Record<string, number> = { all: artifacts.length };
		for (const a of artifacts) {
			counts[a.kind] = (counts[a.kind] || 0) + 1;
		}
		return counts;
	}, [artifacts]);

	const grouped = useMemo(() => {
		const map = new Map<LibraryArtifactKind, LibraryArtifact[]>();
		for (const artifact of filteredArtifacts) {
			const bucket = map.get(artifact.kind);
			if (bucket) bucket.push(artifact);
			else map.set(artifact.kind, [artifact]);
		}
		return map;
	}, [filteredArtifacts]);

	const handleOpen = (artifact: LibraryArtifact) => {
		if (artifact.kind === "report" || artifact.kind === "resume") {
			openReportPanel({
				reportId: artifact.entityId,
				title: artifact.title,
				contentType: artifact.contentType,
			});
			return;
		}
		setSelectedMedia(artifact);
	};

	const filterTabs = [
		{ id: "all", label: "Tất cả", icon: Boxes },
		{ id: "report", label: "Reports", icon: FileText },
		{ id: "podcast", label: "Podcasts", icon: Mic },
		{ id: "video", label: "Presentations", icon: Presentation },
		{ id: "image", label: "Images", icon: Image },
	];

	return (
		<div className="w-full space-y-5">
			<header className="flex items-center justify-between gap-4 flex-wrap pb-1 border-b border-border/40">
				<div className="flex items-baseline gap-2.5">
					<h1 className="font-serif text-2xl sm:text-3xl font-normal text-foreground tracking-tight">
						Artifacts
					</h1>
					{!loading && artifacts.length > 0 ? (
						<span className="text-[11.5px] text-muted-foreground font-mono bg-muted/60 px-2 py-0.5 rounded-md">
							{artifacts.length} deliverables
						</span>
					) : null}
				</div>

				<div className="flex items-center gap-2 w-full sm:w-auto">
					<div className="relative flex-1 sm:w-64">
						<Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
						<Input
							placeholder="Tìm kiếm artifacts..."
							value={searchQuery}
							onChange={(e) => setSearchQuery(e.target.value)}
							className="h-8 pl-8 text-xs rounded-lg bg-background"
						/>
					</div>
					<Button
						variant="outline"
						size="sm"
						onClick={() => refresh()}
						className="h-8 px-2.5 text-xs shrink-0"
						title="Làm mới danh sách"
					>
						<RefreshCw className="size-3.5" />
					</Button>
				</div>
			</header>

			{/* Filter Tabs */}
			{!loading && artifacts.length > 0 ? (
				<div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none">
					{filterTabs.map((tab) => {
						const count = countsByKind[tab.id] || 0;
						if (tab.id !== "all" && count === 0) return null;
						const Icon = tab.icon;
						const isActive = activeTab === tab.id;
						return (
							<button
								key={tab.id}
								type="button"
								onClick={() => setActiveTab(tab.id)}
								className={cn(
									"flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all shrink-0",
									isActive
										? "bg-primary/10 text-primary border border-primary/30"
										: "text-muted-foreground hover:bg-muted/60 hover:text-foreground border border-transparent"
								)}
							>
								<Icon className="size-3.5" />
								<span>{tab.label}</span>
								<span
									className={cn(
										"text-[10px] font-mono px-1.5 py-0.2 rounded-full",
										isActive ? "bg-primary/20 text-primary" : "bg-muted text-muted-foreground"
									)}
								>
									{count}
								</span>
							</button>
						);
					})}
				</div>
			) : null}

			{loading ? (
				<LoadingState />
			) : error ? (
				<ErrorState onRetry={() => refresh()} />
			) : artifacts.length === 0 ? (
				<EmptyState />
			) : filteredArtifacts.length === 0 ? (
				<div className="rounded-xl border border-dashed border-border/70 p-8 text-center">
					<p className="text-xs text-muted-foreground">
						Không tìm thấy artifact nào phù hợp với bộ lọc.
					</p>
					<Button
						variant="ghost"
						size="sm"
						onClick={() => {
							setActiveTab("all");
							setSearchQuery("");
						}}
						className="mt-2 h-7 text-xs text-primary"
					>
						Đặt lại bộ lọc
					</Button>
				</div>
			) : (
				<div className="space-y-6">
					{KIND_ORDER.map((kind) => {
						const items = grouped.get(kind);
						if (!items || items.length === 0) return null;
						return (
							<section key={kind}>
								<div className="flex items-center justify-between mb-2.5">
									<h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
										<span>{KIND_META[kind].group}</span>
										<span className="text-[10.5px] font-mono text-muted-foreground/60 font-normal">
											({items.length})
										</span>
									</h2>
								</div>
								<div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
									{items.map((artifact) => (
										<ArtifactCard
											key={artifact.key}
											artifact={artifact}
											workspaceId={workspaceId}
											onOpen={handleOpen}
										/>
									))}
								</div>
							</section>
						);
					})}
				</div>
			)}

			<MediaViewerDialog artifact={selectedMedia} onClose={() => setSelectedMedia(null)} />
			<MobileReportPanel />
		</div>
	);
}

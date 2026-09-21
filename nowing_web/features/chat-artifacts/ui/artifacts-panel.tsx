"use client";

import { useAtomValue, useSetAtom } from "jotai";
import { Boxes, XIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerHandle, DrawerTitle } from "@/components/ui/drawer";
import { useMediaQuery } from "@/hooks/use-media-query";
import type { ArtifactKind, ChatArtifact } from "../model/artifact";
import {
	artifactsPanelOpenAtom,
	chatArtifactsAtom,
	closeArtifactsPanelAtom,
} from "../state/artifacts-panel.atom";
import { ArtifactRow } from "./artifact-row";

const getGroupOrder = (t: (k: string) => string): { kind: ArtifactKind; label: string }[] => [
	{ kind: "web_app", label: t("x_web_apps") },
	{ kind: "presentation", label: t("x_slide_decks") },
	{ kind: "meeting_minutes", label: t("x_meeting_minutes") },
	{ kind: "report", label: t("x_reports") },
	{ kind: "resume", label: t("x_resumes") },
	{ kind: "podcast", label: t("x_podcasts") },
	{ kind: "video", label: t("x_video_presentations") },
	{ kind: "image", label: t("x_images") },
];

function groupByKind(artifacts: ChatArtifact[]): { label: string; items: ChatArtifact[] }[] {
	const t = useTranslations("layout");
	return getGroupOrder(t)
		.map(({ kind, label }) => ({
			label,
			items: artifacts.filter((a) => a.kind === kind),
		}))
		.filter((group) => group.items.length > 0);
}

function EmptyState() {
	const t = useTranslations("layout");
	return (
		<div className="flex flex-1 flex-col items-center justify-center gap-2 p-6 text-center select-none">
			<Boxes className="size-6 text-muted-foreground/60" aria-hidden="true" />
			<p className="text-sm font-medium text-foreground">{t("no_artifacts_yet")}</p>
			<p className="text-xs text-muted-foreground">
				Web apps, slide decks, meeting minutes, reports, podcasts, video presentations, and images
				you generate will appear here.
			</p>
		</div>
	);
}

function ArtifactGroups({ artifacts }: { artifacts: ChatArtifact[] }) {
	const groups = useMemo(() => groupByKind(artifacts), [artifacts]);

	if (groups.length === 0) return <EmptyState />;

	return (
		<div className="flex-1 overflow-y-auto px-2 py-2">
			{groups.map((group) => (
				<div key={group.label} className="mb-3 last:mb-0">
					<p className="px-3 pb-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground/80 select-none">
						{group.label}
					</p>
					<div className="flex flex-col gap-0.5">
						{group.items.map((artifact) => (
							<ArtifactRow key={artifact.key} artifact={artifact} />
						))}
					</div>
				</div>
			))}
		</div>
	);
}

/** Inner content shared by the desktop right-panel tab and the mobile drawer. */
export function ArtifactsPanelContent({ onClose }: { onClose?: () => void }) {
	const t = useTranslations("layout");
	const artifacts = useAtomValue(chatArtifactsAtom);

	return (
		<>
			<div className="flex h-10 shrink-0 items-center justify-between border-b px-3">
				<h2 className="select-none font-serif text-base font-normal text-foreground">
					{t("x_artifacts")}
				</h2>
				{onClose && (
					<Button
						variant="ghost"
						size="icon"
						onClick={onClose}
						className="size-6 shrink-0 rounded-full text-muted-foreground hover:text-accent-foreground"
					>
						<XIcon className="size-3.5" aria-hidden="true" />
						<span className="sr-only">{t("close_artifacts_panel")}</span>
					</Button>
				)}
			</div>
			<ArtifactGroups artifacts={artifacts} />
		</>
	);
}

/**
 * Mobile artifacts drawer. Desktop renders inside the layout-level RightPanel
 * tab instead, so this no-ops on large screens.
 */
export function MobileArtifactsPanel() {
	const t = useTranslations("layout");
	const isOpen = useAtomValue(artifactsPanelOpenAtom);
	const close = useSetAtom(closeArtifactsPanelAtom);
	const isDesktop = useMediaQuery("(min-width: 1024px)");

	if (isDesktop || !isOpen) return null;

	return (
		<Drawer
			open={isOpen}
			onOpenChange={(open) => {
				if (!open) close();
			}}
			shouldScaleBackground={false}
		>
			<DrawerContent
				className="h-[85vh] max-h-[85vh] z-80 overflow-hidden bg-sidebar"
				overlayClassName="z-80"
			>
				<DrawerHandle />
				<DrawerTitle className="sr-only">{t("x_artifacts")}</DrawerTitle>
				<div className="flex min-h-0 flex-1 flex-col overflow-hidden">
					<ArtifactsPanelContent onClose={close} />
				</div>
			</DrawerContent>
		</Drawer>
	);
}

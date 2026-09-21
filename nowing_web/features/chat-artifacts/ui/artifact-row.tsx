import { useSetAtom } from "jotai";
import { AudioLines, Contact, FileText, Globe, ImageIcon, Presentation, Users } from "lucide-react";
import { useTranslations } from "next-intl";
import type { ComponentType } from "react";
import { openReportPanelAtom } from "@/atoms/chat/report-panel.atom";
import { Button } from "@/components/ui/button";
import { useMediaQuery } from "@/hooks/use-media-query";
import { scrollToArtifact } from "../lib/scroll-to-artifact";
import type { ArtifactKind, ChatArtifact } from "../model/artifact";
import { closeArtifactsPanelAtom } from "../state/artifacts-panel.atom";

const getKindMeta = (
	t: (k: string) => string
): Record<ArtifactKind, { icon: ComponentType<{ className?: string }>; label: string }> => ({
	web_app: { icon: Globe, label: t("x_web_app") },
	report: { icon: FileText, label: t("x_report") },
	resume: { icon: Contact, label: t("x_resume") },
	podcast: { icon: AudioLines, label: t("x_podcast") },
	video: { icon: Presentation, label: t("x_video_presentation") },
	presentation: { icon: Presentation, label: t("x_slide_deck") },
	meeting_minutes: { icon: Users, label: t("x_meeting_minutes") },
	image: { icon: ImageIcon, label: "Image" },
});

export function ArtifactRow({ artifact }: { artifact: ChatArtifact }) {
	const t = useTranslations("artifacts");
	const openReportPanel = useSetAtom(openReportPanelAtom);
	const closeArtifactsPanel = useSetAtom(closeArtifactsPanelAtom);
	const isDesktop = useMediaQuery("(min-width: 1024px)");
	const meta = getKindMeta(t)[artifact.kind];
	const Icon = meta.icon;
	const isReportLike = artifact.kind === "report" || artifact.kind === "resume";

	const handleOpen = () => {
		// Reports/resumes open in the report viewer, which claims the tab itself.
		if (isReportLike && artifact.entityId != null) {
			openReportPanel({
				reportId: artifact.entityId,
				title: artifact.title,
				contentType: artifact.contentType,
			});
			scrollToArtifact(artifact.toolCallId);
			return;
		}

		// Inline media has no viewer — just jump to the card. Mobile dismisses the
		// drawer first since it covers the chat; desktop leaves the panel open.
		if (!isDesktop) closeArtifactsPanel();
		scrollToArtifact(artifact.toolCallId);
	};

	return (
		<Button
			type="button"
			variant="ghost"
			onClick={handleOpen}
			className="h-auto w-full justify-start gap-3 rounded-lg px-3 py-2.5 text-left font-normal hover:bg-accent hover:text-accent-foreground"
		>
			<span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-muted/60 text-muted-foreground">
				<Icon className="size-4" aria-hidden="true" />
			</span>
			<span className="min-w-0 flex-1">
				<span className="block truncate text-sm font-medium text-foreground">{artifact.title}</span>
				<span className="block truncate text-xs text-muted-foreground">
					{artifact.status === "running" ? "Generating…" : meta.label}
				</span>
			</span>
		</Button>
	);
}

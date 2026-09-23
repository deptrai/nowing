import { AudioLines, Contact, FileText, ImageIcon, Presentation } from "lucide-react";
import type { ComponentType } from "react";
import type { LibraryArtifactKind } from "../model/artifact";

export interface KindMetaEntry {
	icon: ComponentType<{ className?: string }>;
	/** i18n key for the singular label, resolved from the "artifacts" namespace */
	labelKey: string;
	/** i18n key for the group heading, resolved from the "artifacts" namespace */
	groupKey: string;
}

export const KIND_META: Record<LibraryArtifactKind, KindMetaEntry> = {
	report: { icon: FileText, labelKey: "lib_report_label", groupKey: "lib_report_group" },
	resume: { icon: Contact, labelKey: "lib_resume_label", groupKey: "lib_resume_group" },
	podcast: { icon: AudioLines, labelKey: "lib_podcast_label", groupKey: "lib_podcast_group" },
	video: { icon: Presentation, labelKey: "lib_video_label", groupKey: "lib_video_group" },
	image: { icon: ImageIcon, labelKey: "lib_image_label", groupKey: "lib_image_group" },
};

export const KIND_ORDER: LibraryArtifactKind[] = ["report", "resume", "podcast", "video", "image"];

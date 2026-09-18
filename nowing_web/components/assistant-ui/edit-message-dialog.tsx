"use client";

/**
 * Confirmation dialog shown when the user edits a message that has
 * reversible downstream actions. Three buttons:
 *
 *   • "Revert all & resubmit"  — POST regenerate with revert_actions=true
 *   • "Continue without revert" — POST regenerate with revert_actions=false
 *   • "Cancel"                  — abort the edit entirely
 *
 * The dialog is auto-skipped when zero reversible downstream actions
 * exist (the caller checks first via ``downstreamReversibleCount``).
 */

import { useEffect, useRef, useState } from "react";
import {
	AlertDialog,
	AlertDialogCancel,
	AlertDialogContent,
	AlertDialogDescription,
	AlertDialogFooter,
	AlertDialogHeader,
	AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";

export type EditMessageDialogChoice = "revert" | "continue" | "cancel";

export interface EditMessageDialogProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	downstreamReversibleCount: number;
	downstreamTotalCount: number;
	onChoose: (choice: EditMessageDialogChoice) => void | Promise<void>;
}

export function EditMessageDialog({
	open,
	onOpenChange,
	downstreamReversibleCount,
	downstreamTotalCount,
	onChoose,
}: EditMessageDialogProps) {
	const t = useTranslations("assistantUi");
	const tCommon = useTranslations("common");
	const [busy, setBusy] = useState<EditMessageDialogChoice | null>(null);

	// The parent's ``handleEditDialogChoice`` calls
	// ``setEditDialogState(null)`` BEFORE awaiting ``handleRegenerate``.
	// That collapses the dialog (Radix unmounts it) while ``onChoose``
	// is still awaiting the long-running stream. Without this guard,
	// the ``finally { setBusy(null) }`` below ran after unmount and
	// produced a "state update on unmounted component" dev warning.
	const mountedRef = useRef(true);
	useEffect(() => {
		mountedRef.current = true;
		return () => {
			mountedRef.current = false;
		};
	}, []);

	const handle = async (choice: EditMessageDialogChoice) => {
		setBusy(choice);
		try {
			await onChoose(choice);
		} finally {
			if (mountedRef.current) {
				setBusy(null);
			}
		}
	};

	return (
		<AlertDialog open={open} onOpenChange={onOpenChange}>
			<AlertDialogContent>
				<AlertDialogHeader>
					<AlertDialogTitle>{t("edit_message_title")}</AlertDialogTitle>
					<AlertDialogDescription>
						{t("edit_message_description", {
							dropCount: downstreamTotalCount,
							revertCount: downstreamReversibleCount,
						})}
					</AlertDialogDescription>
				</AlertDialogHeader>

				<div className="grid gap-2">
					<Button variant="default" disabled={busy !== null} onClick={() => handle("revert")}>
						{busy === "revert"
							? t("reverting_and_resubmitting")
							: t("revert_and_resubmit", { count: downstreamReversibleCount })}
					</Button>
					<Button variant="outline" disabled={busy !== null} onClick={() => handle("continue")}>
						{busy === "continue" ? t("resubmitting") : t("continue_without_revert")}
					</Button>
				</div>

				<AlertDialogFooter className="sm:justify-start">
					<AlertDialogCancel disabled={busy !== null} onClick={() => handle("cancel")}>
						{tCommon("cancel")}
					</AlertDialogCancel>
				</AlertDialogFooter>
			</AlertDialogContent>
		</AlertDialog>
	);
}

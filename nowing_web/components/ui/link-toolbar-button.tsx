import { useTranslations } from "next-intl";
"use client";

import { useLinkToolbarButton, useLinkToolbarButtonState } from "@platejs/link/react";
import { Link } from "lucide-react";
import type * as React from "react";

import { ToolbarButton } from "./toolbar";

export function LinkToolbarButton(props: React.ComponentProps<typeof ToolbarButton>) {
	const t = useTranslations("ui");
	const state = useLinkToolbarButtonState();
	const { props: buttonProps } = useLinkToolbarButton(state);

	return (
		<ToolbarButton tooltip={t("ui_link")} {...props} {...buttonProps} data-plate-focus>
			<Link />
		</ToolbarButton>
	);
}

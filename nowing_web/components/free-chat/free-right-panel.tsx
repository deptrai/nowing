"use client";

import { Lock } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import type { FC } from "react";
import { Button } from "@/components/ui/button";
import {
	Empty,
	EmptyContent,
	EmptyDescription,
	EmptyHeader,
	EmptyMedia,
	EmptyTitle,
} from "@/components/ui/empty";

interface GatedTabProps {
	title: string;
	description: string;
}

const GatedTab: FC<GatedTabProps> = ({ title, description }) => {
	const t = useTranslations("free");
	return (
	<Empty>
		<EmptyHeader>
			<EmptyMedia variant="icon">
				<Lock />
			</EmptyMedia>
			<EmptyTitle>{title}</EmptyTitle>
			<EmptyDescription>{description}</EmptyDescription>
		</EmptyHeader>
		<EmptyContent>
			<Button size="sm" asChild>
				<Link href="/register">{t("create_account")}</Link>
			</Button>
		</EmptyContent>
	</Empty>
	);
};

export const ReportsGatedPlaceholder: FC = () => {
	const t = useTranslations("free");
	return <GatedTab title={t("reports_title")} description={t("reports_desc")} />;
};

export const EditorGatedPlaceholder: FC = () => {
	const t = useTranslations("free");
	return <GatedTab title={t("editor_title")} description={t("editor_desc")} />;
};

export const HitlGatedPlaceholder: FC = () => {
	const t = useTranslations("free");
	return <GatedTab title={t("hitl_title")} description={t("hitl_desc")} />;
};

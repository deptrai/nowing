"use client";

import { CircleSlash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardFooter,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";

export default function PurchaseCancelPage() {
	const params = useParams();
	const t = useTranslations("purchase");
	const workspaceId = String(params.workspace_id ?? "");

	return (
		<div className="flex min-h-[calc(100vh-64px)] items-center justify-center px-4 py-8">
			<Card className="w-full max-w-lg">
				<CardHeader className="text-center">
					<CircleSlash2 className="mx-auto h-10 w-10 text-muted-foreground" aria-hidden="true" />
					<CardTitle className="text-2xl">{t("cancel_title")}</CardTitle>
					<CardDescription>{t("cancel_desc")}</CardDescription>
				</CardHeader>
				<CardContent className="text-center text-sm text-muted-foreground">
					{t("cancel_body")}
				</CardContent>
				<CardFooter className="flex flex-col gap-2 sm:flex-row">
					<Button asChild className="w-full">
						<Link href={`/dashboard/${workspaceId}/buy-more`}>{t("back_to_pricing")}</Link>
					</Button>
					<Button asChild variant="outline" className="w-full">
						<Link href={`/dashboard/${workspaceId}/new-chat`}>{t("back_to_dashboard")}</Link>
					</Button>
				</CardFooter>
			</Card>
		</div>
	);
}

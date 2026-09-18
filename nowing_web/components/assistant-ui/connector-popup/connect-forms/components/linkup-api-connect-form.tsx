"use client";

import { useTranslations } from "next-intl";
import { zodResolver } from "@hookform/resolvers/zod";
import { Info } from "lucide-react";
import type { FC } from "react";
import { useRef } from "react";
import { useForm } from "react-hook-form";
import * as z from "zod";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
	Form,
	FormControl,
	FormDescription,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { EnumConnectorName } from "@/contracts/enums/connector";
import { getConnectorBenefits } from "../connector-benefits";
import type { ConnectFormProps } from "../index";

const createLinkupApiFormSchema = (t: (k: string, o?: Record<string, string | number | Date>) => string) => z.object({
	name: z.string().min(3, {
		message: t("connector_name_min"),
	}),
	api_key: z.string().min(10, {
		message: t("api_key_required_valid"),
	}),
});

type LinkupApiFormValues = z.infer<typeof linkupApiFormSchema>;

export const LinkupApiConnectForm: FC<ConnectFormProps> = ({ onSubmit, isSubmitting }) => {
	const t = useTranslations("assistant");
	const isSubmittingRef = useRef(false);
	const form = useForm<LinkupApiFormValues>({
		resolver: zodResolver(createLinkupApiFormSchema(t)),
		defaultValues: {
			name: t("linkup_name_default"),
			api_key: "",
		},
	});

	const handleSubmit = async (values: LinkupApiFormValues) => {
		// Prevent multiple submissions
		if (isSubmittingRef.current || isSubmitting) {
			return;
		}

		isSubmittingRef.current = true;
		try {
			await onSubmit({
				name: values.name,
				connector_type: EnumConnectorName.LINKUP_API,
				config: {
					LINKUP_API_KEY: values.api_key,
				},
				is_indexable: false,
				is_active: true,
				last_indexed_at: null,
				periodic_indexing_enabled: false,
				indexing_frequency_minutes: null,
				next_scheduled_at: null,
			});
		} finally {
			isSubmittingRef.current = false;
		}
	};

	return (
		<div className="space-y-6 pb-6">
			<Alert>
				<Info />
				<AlertTitle>{t("api_key_required")}</AlertTitle>
				<AlertDescription>
					<p>
						{t("linkup_get_key_desc")}{" "}
						<a
							href="https://linkup.so"
							target="_blank"
							rel="noopener noreferrer"
							className="font-medium underline underline-offset-4"
						>
							linkup.so
						</a>
					</p>
				</AlertDescription>
			</Alert>

			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<Form {...form}>
					<form
						id="linkup-api-connect-form"
						onSubmit={form.handleSubmit(handleSubmit)}
						className="space-y-4 sm:space-y-6"
					>
						<FormField
							control={form.control}
							name="name"
							render={({ field }) => (
								<FormItem>
									<FormLabel className="text-xs sm:text-sm">{t("connector_name")}</FormLabel>
									<FormControl>
										<Input
											placeholder={t("linkup_name_placeholder")}
											className="border-slate-400/20 focus-visible:border-slate-400/40"
											disabled={isSubmitting}
											{...field}
										/>
									</FormControl>
									<FormDescription className="text-[10px] sm:text-xs">
										{t("connector_name_desc")}
									</FormDescription>
									<FormMessage />
								</FormItem>
							)}
						/>

						<FormField
							control={form.control}
							name="api_key"
							render={({ field }) => (
								<FormItem>
									<FormLabel className="text-xs sm:text-sm">{t("linkup_api_key")}</FormLabel>
									<FormControl>
										<Input
											type="password"
											placeholder={t("linkup_api_key_placeholder")}
											className="border-slate-400/20 focus-visible:border-slate-400/40"
											disabled={isSubmitting}
											{...field}
										/>
									</FormControl>
									<FormDescription className="text-[10px] sm:text-xs">
										{t("api_key_encrypted")}
									</FormDescription>
									<FormMessage />
								</FormItem>
							)}
						/>
					</form>
				</Form>
			</div>

			{/* What you get section */}
			{getConnectorBenefits(EnumConnectorName.LINKUP_API) && (
				<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 px-3 sm:px-6 py-4 space-y-2">
					<h4 className="text-xs sm:text-sm font-medium">{t("linkup_what_you_get")}</h4>
					<ul className="list-disc pl-5 text-[10px] sm:text-xs text-muted-foreground space-y-1">
						{getConnectorBenefits(EnumConnectorName.LINKUP_API)?.map((benefit) => (
							<li key={benefit}>{benefit}</li>
						))}
					</ul>
				</div>
			)}
		</div>
	);
};

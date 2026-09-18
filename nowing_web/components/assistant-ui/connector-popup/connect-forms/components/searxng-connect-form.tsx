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
import { Switch } from "@/components/ui/switch";
import { EnumConnectorName } from "@/contracts/enums/connector";
import { getConnectorBenefits } from "../connector-benefits";
import type { ConnectFormProps } from "../index";

const createSearxngFormSchema = (t: (k: string, o?: Record<string, string | number | Date>) => string) => z.object({
	name: z.string().min(3, {
		message: t("connector_name_min"),
	}),
	host: z
		.string()
		.min(1, { message: t("searxng_host_required") })
		.url({ message: t("searxng_host_invalid") }),
	api_key: z.string().optional(),
	engines: z.string().optional(),
	categories: z.string().optional(),
	language: z.string().optional(),
	safesearch: z
		.string()
		.regex(/^[0-2]?$/, { message: t("searxng_safesearch_invalid") })
		.optional(),
	verify_ssl: z.boolean(),
});

type SearxngFormValues = z.infer<ReturnType<typeof createSearxngFormSchema>>;

const parseCommaSeparated = (value?: string | null) => {
	if (!value) return undefined;
	const items = value
		.split(",")
		.map((item) => item.trim())
		.filter((item) => item.length > 0);
	return items.length > 0 ? items : undefined;
};

export const SearxngConnectForm: FC<ConnectFormProps> = ({ onSubmit, isSubmitting }) => {
	const t = useTranslations("assistant");
	const isSubmittingRef = useRef(false);
	const form = useForm<SearxngFormValues>({
		resolver: zodResolver(createSearxngFormSchema(t)),
		defaultValues: {
			name: t("searxng_name_default"),
			host: "",
			api_key: "",
			engines: "",
			categories: "",
			language: "",
			safesearch: "",
			verify_ssl: true,
		},
	});

	const handleSubmit = async (values: SearxngFormValues) => {
		// Prevent multiple submissions
		if (isSubmittingRef.current || isSubmitting) {
			return;
		}

		isSubmittingRef.current = true;
		try {
			const config: Record<string, unknown> = {
				SEARXNG_HOST: values.host.trim(),
			};

			const apiKey = values.api_key?.trim();
			if (apiKey) config.SEARXNG_API_KEY = apiKey;

			const engines = parseCommaSeparated(values.engines);
			if (engines) config.SEARXNG_ENGINES = engines;

			const categories = parseCommaSeparated(values.categories);
			if (categories) config.SEARXNG_CATEGORIES = categories;

			const language = values.language?.trim();
			if (language) config.SEARXNG_LANGUAGE = language;

			const safesearch = values.safesearch?.trim();
			if (safesearch) {
				const parsed = Number(safesearch);
				if (!Number.isNaN(parsed)) {
					config.SEARXNG_SAFESEARCH = parsed;
				}
			}

			// Include verify flag only when disabled to keep config minimal
			if (values.verify_ssl === false) {
				config.SEARXNG_VERIFY_SSL = false;
			}

			await onSubmit({
				name: values.name,
				connector_type: EnumConnectorName.SEARXNG_API,
				config,
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
				<AlertTitle>{t("searxng_instance_required")}</AlertTitle>
				<AlertDescription>
					<p>
						{t("searxng_desc")}{" "}
						<a
							href="https://docs.searxng.org/admin/installation-docker.html"
							target="_blank"
							rel="noopener noreferrer"
							className="font-medium underline underline-offset-4"
						>
							{t("searxng_install_guide")}
						</a>{" "}
						{t("searxng_desc_2")}
					</p>
				</AlertDescription>
			</Alert>

			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<Form {...form}>
					<form
						id="searxng-connect-form"
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
											placeholder={t("searxng_name_placeholder")}
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
							name="host"
							render={({ field }) => (
								<FormItem>
									<FormLabel className="text-xs sm:text-sm">{t("searxng_host")}</FormLabel>
									<FormControl>
										<Input
											placeholder="https://searxng.example.org"
											className="border-slate-400/20 focus-visible:border-slate-400/40"
											disabled={isSubmitting}
											{...field}
										/>
									</FormControl>
									<FormDescription className="text-[10px] sm:text-xs">
										Provide the full base URL to your SearxNG instance. Include the protocol
										(http/https).
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
									<FormLabel className="text-xs sm:text-sm">{t("searxng_api_key")}</FormLabel>
									<FormControl>
										<Input
											type="password"
											placeholder={t("searxng_api_key_placeholder")}
											className="border-slate-400/20 focus-visible:border-slate-400/40"
											disabled={isSubmitting}
											{...field}
										/>
									</FormControl>
									<FormDescription className="text-[10px] sm:text-xs">
										{t("searxng_api_key_desc")}
									</FormDescription>
									<FormMessage />
								</FormItem>
							)}
						/>

						<div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
							<FormField
								control={form.control}
								name="engines"
								render={({ field }) => (
									<FormItem>
										<FormLabel className="text-xs sm:text-sm">{t("searxng_engines")}</FormLabel>
										<FormControl>
											<Input
												placeholder={t("searxng_engines_placeholder")}
												className="border-slate-400/20 focus-visible:border-slate-400/40"
												disabled={isSubmitting}
												{...field}
											/>
										</FormControl>
										<FormDescription className="text-[10px] sm:text-xs">
											{t("searxng_engines_desc")}
										</FormDescription>
										<FormMessage />
									</FormItem>
								)}
							/>

							<FormField
								control={form.control}
								name="categories"
								render={({ field }) => (
									<FormItem>
										<FormLabel className="text-xs sm:text-sm">{t("searxng_categories")}</FormLabel>
										<FormControl>
											<Input
												placeholder={t("searxng_categories_placeholder")}
												className="border-slate-400/20 focus-visible:border-slate-400/40"
												disabled={isSubmitting}
												{...field}
											/>
										</FormControl>
										<FormDescription className="text-[10px] sm:text-xs">
											{t("searxng_categories_desc")}
										</FormDescription>
										<FormMessage />
									</FormItem>
								)}
							/>
						</div>

						<div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
							<FormField
								control={form.control}
								name="language"
								render={({ field }) => (
									<FormItem>
										<FormLabel className="text-xs sm:text-sm">
											{t("searxng_language")}
										</FormLabel>
										<FormControl>
											<Input
												placeholder={t("searxng_language_placeholder")}
												className="border-slate-400/20 focus-visible:border-slate-400/40"
												disabled={isSubmitting}
												{...field}
											/>
										</FormControl>
										<FormDescription className="text-[10px] sm:text-xs">
											{t("searxng_language_desc")}
										</FormDescription>
										<FormMessage />
									</FormItem>
								)}
							/>

							<FormField
								control={form.control}
								name="safesearch"
								render={({ field }) => (
									<FormItem>
										<FormLabel className="text-xs sm:text-sm">
											{t("searxng_safesearch")}
										</FormLabel>
										<FormControl>
											<Input
												placeholder={t("searxng_safesearch_placeholder")}
												className="border-slate-400/20 focus-visible:border-slate-400/40"
												disabled={isSubmitting}
												{...field}
											/>
										</FormControl>
										<FormDescription className="text-[10px] sm:text-xs">
											Set 0, 1, or 2 to adjust SafeSearch filtering. Leave blank to use the instance
											default.
										</FormDescription>
										<FormMessage />
									</FormItem>
								)}
							/>
						</div>

						<FormField
							control={form.control}
							name="verify_ssl"
							render={({ field }) => (
								<FormItem className="flex items-center justify-between rounded-lg border border-slate-400/20 p-3 sm:p-4">
									<div>
										<FormLabel className="text-xs sm:text-sm">{t("searxng_verify_ssl")}</FormLabel>
										<FormDescription className="text-[10px] sm:text-xs">
											{t("searxng_verify_ssl_desc")}
										</FormDescription>
									</div>
									<FormControl>
										<Switch
											checked={field.value}
											onCheckedChange={field.onChange}
											disabled={isSubmitting}
										/>
									</FormControl>
								</FormItem>
							)}
						/>
					</form>
				</Form>
			</div>

			{/* What you get section */}
			{getConnectorBenefits(EnumConnectorName.SEARXNG_API) && (
				<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 px-3 sm:px-6 py-4 space-y-2">
					<h4 className="text-xs sm:text-sm font-medium">{t("searxng_what_you_get")}</h4>
					<ul className="list-disc pl-5 text-[10px] sm:text-xs text-muted-foreground space-y-1">
						{getConnectorBenefits(EnumConnectorName.SEARXNG_API)?.map((benefit) => (
							<li key={benefit}>{benefit}</li>
						))}
					</ul>
				</div>
			)}
		</div>
	);
};

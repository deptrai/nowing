"use client";

import { useTranslations } from "next-intl";
import { zodResolver } from "@hookform/resolvers/zod";
import { Info } from "lucide-react";
import type { FC } from "react";
import { useRef, useState } from "react";
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
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { EnumConnectorName } from "@/contracts/enums/connector";
import { DateRangeSelector } from "../../components/date-range-selector";
import { getConnectorBenefits } from "../connector-benefits";
import type { ConnectFormProps } from "../index";

const createBookstackConnectorFormSchema = (t: (k: string, o?: Record<string, string | number | Date>) => string) => z.object({
	name: z.string().min(3, {
		message: t("connector_name_min"),
	}),
	base_url: z.string().url({ message: t("bookstack_base_url_invalid") }),
	token_id: z.string().min(1, {
		message: t("bookstack_token_id_required"),
	}),
	token_secret: z.string().min(1, {
		message: t("bookstack_token_secret_required"),
	}),
});

type BookStackConnectorFormValues = z.infer<ReturnType<typeof createBookstackConnectorFormSchema>>;

export const BookStackConnectForm: FC<ConnectFormProps> = ({ onSubmit, isSubmitting }) => {
	const t = useTranslations("assistant");
	const isSubmittingRef = useRef(false);
	const [startDate, setStartDate] = useState<Date | undefined>(undefined);
	const [endDate, setEndDate] = useState<Date | undefined>(undefined);
	const [periodicEnabled, setPeriodicEnabled] = useState(false);
	const [frequencyMinutes, setFrequencyMinutes] = useState("1440");
	const form = useForm<BookStackConnectorFormValues>({
		resolver: zodResolver(createBookstackConnectorFormSchema(t)),
		defaultValues: {
			name: t("bookstack_name_default"),
			base_url: "",
			token_id: "",
			token_secret: "",
		},
	});

	const handleSubmit = async (values: BookStackConnectorFormValues) => {
		// Prevent multiple submissions
		if (isSubmittingRef.current || isSubmitting) {
			return;
		}

		isSubmittingRef.current = true;
		try {
			await onSubmit({
				name: values.name,
				connector_type: EnumConnectorName.BOOKSTACK_CONNECTOR,
				config: {
					BOOKSTACK_BASE_URL: values.base_url,
					BOOKSTACK_TOKEN_ID: values.token_id,
					BOOKSTACK_TOKEN_SECRET: values.token_secret,
				},
				is_indexable: true,
				is_active: true,
				last_indexed_at: null,
				periodic_indexing_enabled: periodicEnabled,
				indexing_frequency_minutes: periodicEnabled ? parseInt(frequencyMinutes, 10) : null,
				next_scheduled_at: null,
				startDate,
				endDate,
				periodicEnabled,
				frequencyMinutes,
			});
		} finally {
			isSubmittingRef.current = false;
		}
	};

	return (
		<div className="space-y-6 pb-6">
			<Alert>
				<Info />
				<AlertTitle>{t("api_token_required")}</AlertTitle>
				<AlertDescription>
					You'll need a BookStack API Token to use this connector. You can create one from your
					BookStack instance settings.
				</AlertDescription>
			</Alert>

			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<Form {...form}>
					<form
						id="bookstack-connect-form"
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
											placeholder={t("bookstack_name_placeholder")}
											className="h-8 sm:h-10 px-2 sm:px-3 text-xs sm:text-sm border-slate-400/20 focus-visible:border-slate-400/40"
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
							name="base_url"
							render={({ field }) => (
								<FormItem>
									<FormLabel className="text-xs sm:text-sm">{t("bookstack_base_url")}</FormLabel>
									<FormControl>
										<Input
											type="url"
											placeholder="https://your-bookstack-instance.com"
											className="h-8 sm:h-10 px-2 sm:px-3 text-xs sm:text-sm border-slate-400/20 focus-visible:border-slate-400/40"
											disabled={isSubmitting}
											{...field}
										/>
									</FormControl>
									<FormDescription className="text-[10px] sm:text-xs">
										The base URL of your BookStack instance (e.g.,
										https://your-bookstack-instance.com).
									</FormDescription>
									<FormMessage />
								</FormItem>
							)}
						/>

						<FormField
							control={form.control}
							name="token_id"
							render={({ field }) => (
								<FormItem>
									<FormLabel className="text-xs sm:text-sm">{t("token_id")}</FormLabel>
									<FormControl>
										<Input
											placeholder={t("bookstack_token_placeholder")}
											className="h-8 sm:h-10 px-2 sm:px-3 text-xs sm:text-sm border-slate-400/20 focus-visible:border-slate-400/40"
											disabled={isSubmitting}
											{...field}
										/>
									</FormControl>
									<FormDescription className="text-[10px] sm:text-xs">
										{t("bookstack_token_id_desc")}
									</FormDescription>
									<FormMessage />
								</FormItem>
							)}
						/>

						<FormField
							control={form.control}
							name="token_secret"
							render={({ field }) => (
								<FormItem>
									<FormLabel className="text-xs sm:text-sm">{t("token_secret")}</FormLabel>
									<FormControl>
										<Input
											type="password"
											placeholder={t("bookstack_secret_placeholder")}
											className="h-8 sm:h-10 px-2 sm:px-3 text-xs sm:text-sm border-slate-400/20 focus-visible:border-slate-400/40"
											disabled={isSubmitting}
											{...field}
										/>
									</FormControl>
									<FormDescription className="text-[10px] sm:text-xs">
										{t("bookstack_token_secret_desc")}
									</FormDescription>
									<FormMessage />
								</FormItem>
							)}
						/>

						{/* Indexing Configuration */}
						<div className="space-y-4 pt-4 border-t border-slate-400/20">
							<h3 className="text-sm sm:text-base font-medium">{t("indexing_config")}</h3>

							{/* Date Range Selector */}
							<DateRangeSelector
								startDate={startDate}
								endDate={endDate}
								onStartDateChange={setStartDate}
								onEndDateChange={setEndDate}
							/>

							{/* Periodic Sync Config */}
							<div className="rounded-xl bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6">
								<div className="flex items-center justify-between">
									<div className="space-y-1">
										<h3 className="font-medium text-sm sm:text-base">{t("enable_periodic_sync")}</h3>
										<p className="text-xs sm:text-sm text-muted-foreground">
											{t("periodic_sync_desc")}
										</p>
									</div>
									<Switch
										checked={periodicEnabled}
										onCheckedChange={setPeriodicEnabled}
										disabled={isSubmitting}
									/>
								</div>

								{periodicEnabled && (
									<div className="mt-4 pt-4 border-t border-slate-400/20 space-y-3">
										<div className="space-y-2">
											<Label htmlFor="frequency" className="text-xs sm:text-sm">
												{t("sync_frequency")}
											</Label>
											<Select
												value={frequencyMinutes}
												onValueChange={setFrequencyMinutes}
												disabled={isSubmitting}
											>
												<SelectTrigger
													id="frequency"
													className="w-full bg-slate-400/5 dark:bg-slate-400/5 border-slate-400/20 text-xs sm:text-sm"
												>
													<SelectValue placeholder={t("select_frequency")} />
												</SelectTrigger>
												<SelectContent className="z-[100]">
													<SelectItem value="5" className="text-xs sm:text-sm">
														{t("every_5_minutes")}
													</SelectItem>
													<SelectItem value="15" className="text-xs sm:text-sm">
														{t("every_15_minutes")}
													</SelectItem>
													<SelectItem value="60" className="text-xs sm:text-sm">
														{t("every_hour")}
													</SelectItem>
													<SelectItem value="360" className="text-xs sm:text-sm">
														{t("every_6_hours")}
													</SelectItem>
													<SelectItem value="720" className="text-xs sm:text-sm">
														{t("every_12_hours")}
													</SelectItem>
													<SelectItem value="1440" className="text-xs sm:text-sm">
														{t("daily")}
													</SelectItem>
													<SelectItem value="10080" className="text-xs sm:text-sm">
														{t("weekly")}
													</SelectItem>
												</SelectContent>
											</Select>
										</div>
									</div>
								)}
							</div>
						</div>
					</form>
				</Form>
			</div>

			{/* What you get section */}
			{getConnectorBenefits(EnumConnectorName.BOOKSTACK_CONNECTOR) && (
				<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 px-3 sm:px-6 py-4 space-y-2">
					<h4 className="text-xs sm:text-sm font-medium">
						{t("bookstack_what_you_get")}
					</h4>
					<ul className="list-disc pl-5 text-[10px] sm:text-xs text-muted-foreground space-y-1">
						{getConnectorBenefits(EnumConnectorName.BOOKSTACK_CONNECTOR)?.map((benefit) => (
							<li key={benefit}>{benefit}</li>
						))}
					</ul>
				</div>
			)}
		</div>
	);
};

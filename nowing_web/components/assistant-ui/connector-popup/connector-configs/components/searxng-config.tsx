"use client";

import { Globe, KeyRound } from "lucide-react";
import type { FC } from "react";
import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import type { ConnectorConfigProps } from "../index";
import { useTranslations } from "next-intl";

export interface SearxngConfigProps extends ConnectorConfigProps {
	onNameChange?: (name: string) => void;
}

const arrayToString = (arr: unknown): string => {
	if (!arr) return "";
	if (Array.isArray(arr)) {
		return arr.join(", ");
	}
	return String(arr);
};

const stringToArray = (value: string): string[] | undefined => {
	if (!value) return undefined;
	const items = value
		.split(",")
		.map((item) => item.trim())
		.filter((item) => item.length > 0);
	return items.length > 0 ? items : undefined;
};

export const SearxngConfig: FC<SearxngConfigProps> = ({
	connector,
	onConfigChange,
	onNameChange,
}) => {
	const t = useTranslations("assistant");
	const [host, setHost] = useState<string>((connector.config?.SEARXNG_HOST as string) || "");
	const [apiKey, setApiKey] = useState<string>((connector.config?.SEARXNG_API_KEY as string) || "");
	const [engines, setEngines] = useState<string>(arrayToString(connector.config?.SEARXNG_ENGINES));
	const [categories, setCategories] = useState<string>(
		arrayToString(connector.config?.SEARXNG_CATEGORIES)
	);
	const [language, setLanguage] = useState<string>(
		(connector.config?.SEARXNG_LANGUAGE as string) || ""
	);
	const [safesearch, setSafesearch] = useState<string>(
		connector.config?.SEARXNG_SAFESEARCH !== undefined
			? String(connector.config.SEARXNG_SAFESEARCH)
			: ""
	);
	const [verifySsl, setVerifySsl] = useState<boolean>(
		connector.config?.SEARXNG_VERIFY_SSL !== undefined
			? (connector.config.SEARXNG_VERIFY_SSL as boolean)
			: true
	);
	const [name, setName] = useState<string>(connector.name || "");

	const updateConfig = (updates: Record<string, unknown>) => {
		if (onConfigChange) {
			onConfigChange({
				...connector.config,
				...updates,
			});
		}
	};

	const handleHostChange = (value: string) => {
		setHost(value);
		updateConfig({ SEARXNG_HOST: value });
	};

	const handleApiKeyChange = (value: string) => {
		setApiKey(value);
		if (value) {
			updateConfig({ SEARXNG_API_KEY: value });
		} else {
			const newConfig = { ...connector.config };
			delete newConfig.SEARXNG_API_KEY;
			if (onConfigChange) {
				onConfigChange(newConfig);
			}
		}
	};

	const handleEnginesChange = (value: string) => {
		setEngines(value);
		const enginesArray = stringToArray(value);
		if (enginesArray) {
			updateConfig({ SEARXNG_ENGINES: enginesArray });
		} else {
			const newConfig = { ...connector.config };
			delete newConfig.SEARXNG_ENGINES;
			if (onConfigChange) {
				onConfigChange(newConfig);
			}
		}
	};

	const handleCategoriesChange = (value: string) => {
		setCategories(value);
		const categoriesArray = stringToArray(value);
		if (categoriesArray) {
			updateConfig({ SEARXNG_CATEGORIES: categoriesArray });
		} else {
			const newConfig = { ...connector.config };
			delete newConfig.SEARXNG_CATEGORIES;
			if (onConfigChange) {
				onConfigChange(newConfig);
			}
		}
	};

	const handleLanguageChange = (value: string) => {
		setLanguage(value);
		if (value) {
			updateConfig({ SEARXNG_LANGUAGE: value });
		} else {
			const newConfig = { ...connector.config };
			delete newConfig.SEARXNG_LANGUAGE;
			if (onConfigChange) {
				onConfigChange(newConfig);
			}
		}
	};

	const handleSafesearchChange = (value: string) => {
		setSafesearch(value);
		if (value) {
			const parsed = Number(value);
			if (!Number.isNaN(parsed)) {
				updateConfig({ SEARXNG_SAFESEARCH: parsed });
			}
		} else {
			const newConfig = { ...connector.config };
			delete newConfig.SEARXNG_SAFESEARCH;
			if (onConfigChange) {
				onConfigChange(newConfig);
			}
		}
	};

	const handleVerifySslChange = (value: boolean) => {
		setVerifySsl(value);
		if (value === false) {
			updateConfig({ SEARXNG_VERIFY_SSL: false });
		} else {
			const newConfig = { ...connector.config };
			delete newConfig.SEARXNG_VERIFY_SSL;
			if (onConfigChange) {
				onConfigChange(newConfig);
			}
		}
	};

	const handleNameChange = (value: string) => {
		setName(value);
		if (onNameChange) {
			onNameChange(value);
		}
	};

	return (
		<div className="space-y-6">
			{/* Connector Name */}
			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<div className="space-y-2">
					<Label className="text-xs sm:text-sm">{t("connector_name")}</Label>
					<Input
						value={name}
						onChange={(e) => handleNameChange(e.target.value)}
						placeholder={t("my_searxng_connector")}
						className="border-slate-400/20 focus-visible:border-slate-400/40"
					/>
					<p className="text-[10px] sm:text-xs text-muted-foreground">
						{t("friendly_name")}
					</p>
				</div>
			</div>

			{/* Configuration */}
			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-3 sm:space-y-4">
				<div className="space-y-1 sm:space-y-2">
					<h3 className="font-medium text-sm sm:text-base">{t("configuration")}</h3>
				</div>

				<div className="space-y-4">
					<div className="space-y-2">
						<Label className="flex items-center gap-2 text-xs sm:text-sm">
							<Globe className="h-4 w-4" aria-hidden="true" />
							{t("searxng_host")}
						</Label>
						<Input
							value={host}
							onChange={(e) => handleHostChange(e.target.value)}
							placeholder="https://searxng.example.org"
							className="border-slate-400/20 focus-visible:border-slate-400/40"
						/>
						<p className="text-[10px] sm:text-xs text-muted-foreground">
							{t("update_searxng_host")}
						</p>
					</div>

					<div className="space-y-2">
						<Label className="flex items-center gap-2 text-xs sm:text-sm">
							<KeyRound className="h-4 w-4" aria-hidden="true" />
							{t("api_key_optional")}
						</Label>
						<Input
							type="password"
							value={apiKey}
							onChange={(e) => handleApiKeyChange(e.target.value)}
							placeholder={t("enter_api_key_instance")}
							className="border-slate-400/20 focus-visible:border-slate-400/40"
						/>
						<p className="text-[10px] sm:text-xs text-muted-foreground">
							{t("leave_empty_no_keys")}
						</p>
					</div>

					<div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
						<div className="space-y-2">
							<Label className="text-xs sm:text-sm">{t("engines_optional")}</Label>
							<Input
								value={engines}
								onChange={(e) => handleEnginesChange(e.target.value)}
								placeholder={t("engines_placeholder")}
								className="border-slate-400/20 focus-visible:border-slate-400/40"
							/>
							<p className="text-[10px] sm:text-xs text-muted-foreground">
								{t("engines_desc")}
							</p>
						</div>

						<div className="space-y-2">
							<Label className="text-xs sm:text-sm">{t("categories_optional")}</Label>
							<Input
								value={categories}
								onChange={(e) => handleCategoriesChange(e.target.value)}
								placeholder={t("categories_placeholder")}
								className="border-slate-400/20 focus-visible:border-slate-400/40"
							/>
							<p className="text-[10px] sm:text-xs text-muted-foreground">
								{t("categories_desc")}
							</p>
						</div>
					</div>

					<div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
						<div className="space-y-2">
							<Label className="text-xs sm:text-sm">{t("preferred_language_optional")}</Label>
							<Input
								value={language}
								onChange={(e) => handleLanguageChange(e.target.value)}
								placeholder="en-US"
								className="border-slate-400/20 focus-visible:border-slate-400/40"
							/>
							<p className="text-[10px] sm:text-xs text-muted-foreground">
								{t("language_tag_desc")}
							</p>
						</div>

						<div className="space-y-2">
							<Label className="text-xs sm:text-sm">{t("safesearch_optional")}</Label>
							<Input
								value={safesearch}
								onChange={(e) => handleSafesearchChange(e.target.value)}
								placeholder={t("safesearch_placeholder")}
								className="border-slate-400/20 focus-visible:border-slate-400/40"
							/>
							<p className="text-[10px] sm:text-xs text-muted-foreground">
								Set 0, 1, or 2 to adjust SafeSearch filtering. Leave blank to use the instance
								default.
							</p>
						</div>
					</div>

					<div className="flex items-center justify-between rounded-lg border border-slate-400/20 p-3 sm:p-4">
						<div>
							<Label className="text-xs sm:text-sm">{t("verify_ssl")}</Label>
							<p className="text-[10px] sm:text-xs text-muted-foreground">
								{t("verify_ssl_desc")}
							</p>
						</div>
						<Switch checked={verifySsl} onCheckedChange={handleVerifySslChange} />
					</div>
				</div>
			</div>
		</div>
	);
};

"use client";

import { KeyRound } from "lucide-react";
import type { FC } from "react";
import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { ConnectorConfigProps } from "../index";
import { useTranslations } from "next-intl";

export interface LumaConfigProps extends ConnectorConfigProps {
	onNameChange?: (name: string) => void;
}

export const LumaConfig: FC<LumaConfigProps> = ({
	connector,
	onConfigChange,
	onNameChange,
}) => {
	const t = useTranslations("assistant");
	const [apiKey, setApiKey] = useState<string>((connector.config?.LUMA_API_KEY as string) || "");
	const [name, setName] = useState<string>(connector.name || "");

	const handleApiKeyChange = (value: string) => {
		setApiKey(value);
		if (onConfigChange) {
			onConfigChange({
				...connector.config,
				LUMA_API_KEY: value,
			});
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
						placeholder={t("my_luma_connector")}
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

				<div className="space-y-2">
					<Label className="flex items-center gap-2 text-xs sm:text-sm">
						<KeyRound className="h-4 w-4" aria-hidden="true" />
						{t("luma_api_key")}
					</Label>
					<Input
						type="password"
						value={apiKey}
						onChange={(e) => handleApiKeyChange(e.target.value)}
						placeholder={t("your_api_key")}
						className="border-slate-400/20 focus-visible:border-slate-400/40"
					/>
					<p className="text-[10px] sm:text-xs text-muted-foreground">
						{t("update_luma_key")}
					</p>
				</div>
			</div>
		</div>
	);
};

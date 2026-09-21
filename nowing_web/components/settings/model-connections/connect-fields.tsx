import { Eye, EyeOff } from "lucide-react";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";

interface ApiBaseUrlFieldProps {
	value: string;
	onChange: (value: string) => void;
	/** Placeholder, typically the provider's prefilled default base URL. */
	placeholder?: string;
	hint?: ReactNode;
}

/** Shared API Base URL input. The prefilled default is passed in via `value`. */
export function ApiBaseUrlField({ value, onChange, placeholder, hint }: ApiBaseUrlFieldProps) {
	const t = useTranslations("settings");
	return (
		<div className="flex flex-col gap-2">
			<Label>{t("mc_api_base_url")}</Label>
			<Input
				value={value}
				onChange={(event) => onChange(event.target.value)}
				placeholder={placeholder || "https://api.example.com/v1"}
			/>
			{hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
		</div>
	);
}

interface ApiKeyFieldProps {
	value: string;
	onChange: (value: string) => void;
	label?: string;
	placeholder?: string;
}

/** Shared masked API Key input. */
export function ApiKeyField({ value, onChange, label, placeholder }: ApiKeyFieldProps) {
	const t = useTranslations("settings");
	const [showApiKey, setShowApiKey] = useState(false);
	const resolvedLabel = label ?? t("mc_api_key");
	const resolvedPlaceholder = placeholder ?? t("mc_api_key_ph");

	return (
		<div className="flex flex-col gap-2">
			<Label>{resolvedLabel}</Label>
			<div className="relative">
				<Input
					value={value}
					onChange={(event) => onChange(event.target.value)}
					placeholder={resolvedPlaceholder}
					type={showApiKey ? "text" : "password"}
					className="pr-11"
				/>
				<Button
					type="button"
					variant="ghost"
					size="icon"
					className="absolute top-1/2 right-1 size-8 -translate-y-1/2 text-muted-foreground"
					onClick={() => setShowApiKey((current) => !current)}
					disabled={!value}
					aria-label={showApiKey ? t("mc_hide_key") : t("mc_show_key")}
				>
					{showApiKey ? (
						<EyeOff className="h-4 w-4" aria-hidden="true" />
					) : (
						<Eye className="h-4 w-4" aria-hidden="true" />
					)}
				</Button>
			</div>
		</div>
	);
}

interface ConnectFormFooterProps {
	onCancel: () => void;
	onSubmit: () => void;
	canSubmit: boolean;
	isPending: boolean;
}

/** Shared Cancel / Connect footer for every provider connect form. */
export function ConnectFormFooter({
	onCancel,
	onSubmit,
	canSubmit,
	isPending,
}: ConnectFormFooterProps) {
	const t = useTranslations("settings");
	return (
		<DialogFooter className="shrink-0 border-t bg-popover px-6 py-4">
			<Button variant="secondary" onClick={onCancel}>
				{t("mc_cancel")}
			</Button>
			<Button
				onClick={onSubmit}
				disabled={isPending || !canSubmit}
				className="relative min-w-[96px]"
			>
				<span className={isPending ? "opacity-0" : ""}>{t("mc_connect")}</span>
				{isPending ? <Spinner size="sm" className="absolute" /> : null}
			</Button>
		</DialogFooter>
	);
}

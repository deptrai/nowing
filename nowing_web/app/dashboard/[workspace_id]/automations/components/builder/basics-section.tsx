"use client";
import { useTranslations } from "next-intl";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Field } from "./form-field";

interface BasicsSectionProps {
	name: string;
	description: string | null;
	errors: Record<string, string>;
	onChange: (patch: { name?: string; description?: string | null }) => void;
}

export function BasicsSection({ name, description, errors, onChange }: BasicsSectionProps) {
	const t = useTranslations("automations");
	return (
		<div className="space-y-4">
			<Field label={t("auto_name")} htmlFor="automation-name" required error={errors.name}>
				<Input
					id="automation-name"
					value={name}
					maxLength={200}
					placeholder={t("auto_weekly_research_digest")}
					onChange={(e) => onChange({ name: e.target.value })}
				/>
			</Field>

			<Field
				label={t("auto_description")}
				htmlFor="automation-description"
				hint="Optional. A short note about what this automation is for."
				error={errors.description}
			>
				<Textarea
					id="automation-description"
					value={description ?? ""}
					rows={2}
					placeholder={t("auto_summarize_what_changed_and")}
					onChange={(e) => onChange({ description: e.target.value })}
				/>
			</Field>
		</div>
	);
}

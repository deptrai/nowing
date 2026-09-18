"use client";

import { Info, Plus, Trash2 } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import {
	ACTION_METADATA,
	type BulkAction,
	type FilterClause,
	type FilterOperator,
} from "@/contracts/types/admin-bulk-ops.types";
import { useTranslations } from "next-intl";

interface FilterBuilderProps {
	action: BulkAction;
	filters: FilterClause[];
	onFiltersChange: (filters: FilterClause[]) => void;
	actionParams: Record<string, unknown>;
	onActionParamsChange: (params: Record<string, unknown>) => void;
	disabled?: boolean;
}

export function FilterBuilder({
	action,
	filters,
	onFiltersChange,
	actionParams,
	onActionParamsChange,
	disabled = false,
}: FilterBuilderProps) {
	const t = useTranslations("bulkOps");
	const meta = ACTION_METADATA[action];
	const availableFields = meta ? Object.keys(meta.fields) : [];

	const operatorLabels: Record<FilterOperator, string> = {
		eq: t("operator_eq"),
		neq: t("operator_neq"),
		gt: t("operator_gt"),
		gte: t("operator_gte"),
		lt: t("operator_lt"),
		lte: t("operator_lte"),
		in: t("operator_in"),
		not_in: t("operator_not_in"),
	};

	const handleAddFilter = () => {
		if (availableFields.length === 0) return;
		const defaultField = availableFields[0];
		const defaultOp = meta.fields[defaultField].operators[0] || "eq";
		const defaultVal = meta.fields[defaultField].type === "number" ? 30 : "";

		onFiltersChange([
			...filters,
			{
				field: defaultField,
				op: defaultOp,
				value: defaultVal,
			},
		]);
	};

	const handleRemoveFilter = (index: number) => {
		onFiltersChange(filters.filter((_, i) => i !== index));
	};

	const handleFieldChange = (index: number, newField: string) => {
		const fieldMeta = meta.fields[newField];
		const defaultOp = fieldMeta?.operators[0] || "eq";
		const defaultVal = fieldMeta?.type === "number" ? 0 : "";

		const updated = [...filters];
		updated[index] = {
			field: newField,
			op: defaultOp,
			value: defaultVal,
		};
		onFiltersChange(updated);
	};

	const handleOpChange = (index: number, newOp: FilterOperator) => {
		const updated = [...filters];
		updated[index] = {
			...updated[index],
			op: newOp,
		};
		onFiltersChange(updated);
	};

	const handleValueChange = (index: number, rawVal: string) => {
		const fieldMeta = meta.fields[filters[index].field];
		let parsedVal: unknown = rawVal;

		if (fieldMeta?.type === "number") {
			parsedVal = rawVal === "" ? "" : Number(rawVal);
		} else if (filters[index].op === "in" || filters[index].op === "not_in") {
			parsedVal = rawVal
				.split(",")
				.map((s) => s.trim())
				.filter(Boolean);
		}

		const updated = [...filters];
		updated[index] = {
			...updated[index],
			value: parsedVal,
		};
		onFiltersChange(updated);
	};

	const handleParamChange = (paramKey: string, rawVal: string, type: "string" | "number") => {
		onActionParamsChange({
			...actionParams,
			[paramKey]: type === "number" ? (rawVal === "" ? "" : Number(rawVal)) : rawVal,
		});
	};

	return (
		<div className="space-y-4">
			{/* Action-specific Required Parameters */}
			{meta.requiredParams && Object.keys(meta.requiredParams).length > 0 && (
				<div className="rounded-lg border p-4 bg-muted/20 space-y-3">
					<h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
						{t("required_parameters")}
					</h4>
					<div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
						{Object.entries(meta.requiredParams).map(([key, def]) => (
							<div key={key} className="space-y-1.5">
								<Label htmlFor={`param-${key}`} className="text-sm">
									{def.label} <span className="text-destructive">*</span>
								</Label>
								<Input
									id={`param-${key}`}
									type={def.type === "number" ? "number" : "text"}
									value={(actionParams[key] as string | number | undefined) ?? ""}
									onChange={(e) => handleParamChange(key, e.target.value, def.type)}
									disabled={disabled}
									placeholder={t("enter_param_placeholder", { param: def.label.toLowerCase() })}
								/>
							</div>
						))}
					</div>
				</div>
			)}

			{/* Filter Safety Warnings */}
			{action === "archive_inactive_workspaces" && (
				<Alert
					variant="default"
					className="border-amber-500/50 bg-amber-500/10 text-amber-900 dark:text-amber-200"
				>
					<Info className="h-4 w-4 text-amber-600" />
					<AlertDescription className="text-xs">
						{t("safety_constraint_prefix")}{" "}
						<strong>inactive_days &gt; 0</strong>{" "}
						{t("safety_constraint_suffix")}
					</AlertDescription>
				</Alert>
			)}

			{/* Structured Filter List */}
			<div className="space-y-3">
				<div className="flex items-center justify-between">
					<Label className="text-sm font-medium">{t("target_filters")}</Label>
					<Button
						type="button"
						variant="outline"
						size="sm"
						onClick={handleAddFilter}
						disabled={disabled}
						className="h-8 gap-1.5 text-xs"
					>
						<Plus className="h-3.5 w-3.5" />
						{t("add_filter")}
					</Button>
				</div>

				{filters.length === 0 ? (
					<div className="rounded-md border border-dashed p-6 text-center text-xs text-muted-foreground">
						{t("no_filters_configured")}
					</div>
				) : (
					<div className="space-y-2">
						{filters.map((filter, index) => {
							const fieldMeta = meta.fields[filter.field];
							const ops = fieldMeta?.operators || ["eq"];

							return (
								<div
									// biome-ignore lint/suspicious/noArrayIndexKey: clauses are dynamically ordered
									key={`filter-${filter.field}-${index}`}
									className="flex flex-col sm:flex-row items-start sm:items-center gap-2 p-2 rounded-md border bg-card text-card-foreground shadow-sm"
								>
									{/* Field Select */}
									<div className="w-full sm:w-1/3 min-w-[140px]">
										<Select
											value={filter.field}
											onValueChange={(val) => handleFieldChange(index, val)}
											disabled={disabled}
										>
											<SelectTrigger className="h-9 text-xs">
												<SelectValue placeholder={t("field_placeholder")} />
											</SelectTrigger>
											<SelectContent>
												{availableFields.map((f) => (
													<SelectItem key={f} value={f} className="text-xs">
														{meta.fields[f].label}
													</SelectItem>
												))}
											</SelectContent>
										</Select>
									</div>

									{/* Operator Select */}
									<div className="w-full sm:w-1/3 min-w-[130px]">
										<Select
											value={filter.op}
											onValueChange={(val) => handleOpChange(index, val as FilterOperator)}
											disabled={disabled}
										>
											<SelectTrigger className="h-9 text-xs">
												<SelectValue placeholder={t("operator_placeholder")} />
											</SelectTrigger>
											<SelectContent>
												{ops.map((op) => (
													<SelectItem key={op} value={op} className="text-xs">
														{operatorLabels[op]}
													</SelectItem>
												))}
											</SelectContent>
										</Select>
									</div>

									{/* Value Input */}
									<div className="w-full sm:flex-1">
										<Input
											type={
												fieldMeta?.type === "number"
													? "number"
													: fieldMeta?.type === "date"
														? "date"
														: "text"
											}
											value={
												Array.isArray(filter.value) ? filter.value.join(", ") : (filter.value ?? "")
											}
											onChange={(e) => handleValueChange(index, e.target.value)}
											placeholder={
												filter.op === "in" || filter.op === "not_in"
													? t("value_list_placeholder")
													: t("value_placeholder")
											}
											disabled={disabled}
											className="h-9 text-xs"
										/>
									</div>

									{/* Remove Clause Button */}
									<Button
										type="button"
										variant="ghost"
										size="icon"
										onClick={() => handleRemoveFilter(index)}
										disabled={disabled}
										className="h-9 w-9 text-muted-foreground hover:text-destructive shrink-0"
									>
										<Trash2 className="h-4 w-4" />
									</Button>
								</div>
							);
						})}
					</div>
				)}
			</div>
		</div>
	);
}

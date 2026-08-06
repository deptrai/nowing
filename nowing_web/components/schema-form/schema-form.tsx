"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useId, useMemo, useRef } from "react";
import { type ControllerRenderProps, useForm, useFormContext, useWatch } from "react-hook-form";
import type { z } from "zod";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import type { JSONSchema } from "@/contracts/types/schema-ui.types";
import { buildDefaultValues } from "@/lib/schema-form/build-default-values";
import { jsonSchemaToZod } from "@/lib/schema-form/json-schema-to-zod";
import {
	DEFAULT_DISTRICT_OPTIONS,
	deepEqual,
	fieldDescription,
	fieldLabel,
	fieldUi,
	optionsFromSchema,
	stringToValue,
	valueToString,
} from "@/lib/schema-form/utils";

export interface SchemaFormProps {
	schema: JSONSchema;
	/** Pre-fill values.  Missing fields are seeded from the schema defaults. */
	defaultValues?: Record<string, unknown>;
	/** Called when the user explicitly submits the form. */
	onSubmit?: (values: Record<string, unknown>) => void | Promise<void>;
	/** Called with the current valid values whenever the form changes. */
	onChange?: (values: Record<string, unknown>) => void;
	submitLabel?: string;
	className?: string;
}

/**
 * A single, schema-driven form renderer for both playbook ``inputs.schema``
 * and action ``params_schema``.  It reads ``x-ui`` hints to choose controls and
 * labels but never hard-codes a UI per tool.
 *
 * Supported JSON Schema subset: ``object``, ``string``, ``number``/``integer``,
 * ``boolean``, ``array`` (strings/enums), and ``enum``.  Unknown nodes fall
 * back to ``z.any()`` and a plain text input.
 */
export function SchemaForm({
	schema,
	defaultValues = {},
	onSubmit,
	onChange,
	submitLabel = "Submit",
	className,
}: SchemaFormProps) {
	const zodSchema = useMemo(
		() =>
			jsonSchemaToZod(schema, true, "", fieldUi(schema)) as unknown as z.ZodType<
				Record<string, unknown>,
				Record<string, unknown>
			>,
		[schema]
	);
	const formDefaultValues = useMemo(
		() => buildDefaultValues(schema, defaultValues) as Record<string, unknown>,
		[schema, defaultValues]
	);
	const form = useForm<Record<string, unknown>>({
		resolver: zodResolver(zodSchema),
		defaultValues: formDefaultValues,
		mode: "onChange",
	});

	const watchedValues = useWatch({ control: form.control });
	const isValid = form.formState.isValid;
	const lastEmittedRef = useRef<Record<string, unknown>>(formDefaultValues);

	useEffect(() => {
		if (!onChange) return;
		if (!isValid) return;
		if (!deepEqual(watchedValues, lastEmittedRef.current)) {
			lastEmittedRef.current = watchedValues;
			onChange(watchedValues);
		}
	}, [watchedValues, isValid, onChange]);

	const previousDefaultsRef = useRef<Record<string, unknown>>(formDefaultValues);
	useEffect(() => {
		if (!deepEqual(formDefaultValues, previousDefaultsRef.current)) {
			previousDefaultsRef.current = formDefaultValues;
			form.reset(formDefaultValues);
			lastEmittedRef.current = formDefaultValues;
		}
	}, [form, formDefaultValues]);

	return (
		<Form {...form}>
			<form onSubmit={onSubmit ? form.handleSubmit(onSubmit) : undefined} className={className}>
				{schema.type === "object" && schema.properties ? (
					<div className="space-y-4">
						{Object.entries(schema.properties).map(([key, prop]) => (
							<SchemaField
								key={key}
								name={key}
								schema={prop}
								required={schema.required?.includes(key) ?? false}
							/>
						))}
					</div>
				) : (
					<SchemaField name="value" schema={schema} required />
				)}

				{onSubmit && (
					<div className="flex justify-end pt-2">
						<Button type="submit" disabled={!isValid}>
							{submitLabel}
						</Button>
					</div>
				)}
			</form>
		</Form>
	);
}

interface SchemaFieldProps {
	name: string;
	schema: JSONSchema;
	required: boolean;
}

function SchemaField({ name, schema, required }: SchemaFieldProps) {
	const { control } = useFormContext();
	const ui = fieldUi(schema);
	const widget = ui?.widget ?? inferWidget(schema);
	const labelName = name.split(".").pop() ?? name;

	if (widget === "hidden") {
		return (
			<FormField
				control={control}
				name={name}
				render={({ field }) => (
					<input type="hidden" name={field.name} value={String(field.value ?? "")} />
				)}
			/>
		);
	}

	if (schema.type === "object" || (schema.type === undefined && schema.properties)) {
		const hasProperties = !!schema.properties && Object.keys(schema.properties).length > 0;
		if (!hasProperties) {
			return <JsonObjectField name={name} schema={schema} required={required} />;
		}
		const label = fieldLabel(schema, labelName);
		const description = fieldDescription(schema);
		return (
			<div className="space-y-3 rounded-md border border-border/40 p-3">
				{label && <Label className="text-sm font-medium">{label}</Label>}
				{description && <p className="text-xs text-muted-foreground">{description}</p>}
				<div className="space-y-4">
					{Object.entries(schema.properties ?? {}).map(([key, prop]) => (
						<SchemaField
							key={key}
							name={`${name}.${key}`}
							schema={prop}
							required={schema.required?.includes(key) ?? false}
						/>
					))}
				</div>
			</div>
		);
	}

	if (schema.type === "array" || (schema.type === undefined && schema.items)) {
		return <ArrayField name={name} schema={schema} required={required} />;
	}

	return (
		<FormField
			control={control}
			name={name}
			render={({ field, fieldState }) => (
				<FormItem className="space-y-1.5">
					<FormLabel>{fieldLabel(schema, labelName)}</FormLabel>
					<FormControl>
						<WidgetControl field={field} schema={schema} />
					</FormControl>
					{fieldDescription(schema) && (
						<FormDescription>{fieldDescription(schema)}</FormDescription>
					)}
					<FormMessage>{fieldState.error?.message}</FormMessage>
				</FormItem>
			)}
		/>
	);
}

function inferWidget(schema: JSONSchema): string {
	const ui = fieldUi(schema);
	if (ui?.widget) return ui.widget;
	const resolved =
		schema.type === undefined && schema.anyOf
			? schema.anyOf.find((b) => b.type !== "null")
			: schema;
	if (!resolved) return "text";
	if (resolved.type === "boolean") return "switch";
	if (resolved.type === "array") return "checkbox";
	if (resolved.type === "number" || resolved.type === "integer") {
		if (resolved.minimum !== undefined && resolved.maximum !== undefined) return "slider";
		return "text";
	}
	if (resolved.enum || optionsFromSchema(resolved).length > 0) return "select";
	return "text";
}

interface WidgetControlProps {
	field: ControllerRenderProps<Record<string, unknown>, string>;
	schema: JSONSchema;
}

function WidgetControl({ field, schema }: WidgetControlProps) {
	const ui = fieldUi(schema);
	const widget = ui?.widget ?? inferWidget(schema);
	const labelName = field.name.split(".").pop() ?? field.name;
	const label = fieldLabel(schema, labelName);
	const description = fieldDescription(schema);

	if (widget === "district-picker") {
		return (
			<SelectField
				field={field}
				schema={schema}
				options={ui?.options && ui.options.length > 0 ? ui.options : DEFAULT_DISTRICT_OPTIONS}
			/>
		);
	}

	if (
		widget === "select" ||
		widget === "checkbox" ||
		schema.enum ||
		optionsFromSchema(schema).length > 0
	) {
		if (schema.type === "array" || (schema.type === undefined && schema.items)) {
			return <CheckboxGroupField field={field} schema={schema} />;
		}
		const options = optionsFromSchema(schema);
		if (options.length > 0) {
			return <SelectField field={field} schema={schema} options={options} />;
		}
	}

	if (widget === "price-vnd") {
		return (
			<div className="relative flex items-center gap-2">
				<Input
					type="number"
					inputMode="numeric"
					value={(field.value as string | number | undefined) ?? ""}
					onChange={(e) => {
						const raw = e.target.value;
						field.onChange(raw === "" ? undefined : Number(raw));
					}}
					aria-label={label}
				/>
				{ui?.unit && (
					<span className="text-sm text-muted-foreground whitespace-nowrap">{ui.unit}</span>
				)}
			</div>
		);
	}

	if (widget === "slider") {
		const resolved =
			schema.type === undefined && schema.anyOf
				? schema.anyOf.find((b) => b.type !== "null")
				: schema;
		const min = resolved?.minimum ?? 0;
		const max = resolved?.maximum ?? 100;
		const step = resolved?.type === "integer" ? 1 : 0.1;
		return (
			<div className="space-y-2">
				<Slider
					min={min}
					max={max}
					step={step}
					value={[field.value === undefined ? min : Number(field.value)]}
					onValueChange={(v) => field.onChange(v[0])}
					aria-label={label}
				/>
				<div className="flex justify-between text-xs text-muted-foreground">
					<span>{min}</span>
					<span>{String(field.value ?? "")}</span>
					<span>{max}</span>
				</div>
			</div>
		);
	}

	if (widget === "switch") {
		return (
			<Switch
				checked={!!field.value}
				onCheckedChange={(v) => field.onChange(v)}
				aria-label={label}
			/>
		);
	}

	if (widget === "checkbox" && schema.type === "boolean") {
		return (
			<div className="flex items-center gap-2">
				<Checkbox
					checked={!!field.value}
					onCheckedChange={(v) => field.onChange(v)}
					aria-label={label}
				/>
				{description && <span className="text-xs text-muted-foreground">{description}</span>}
			</div>
		);
	}

	if (widget === "textarea") {
		return (
			<Textarea
				value={String(field.value ?? "")}
				onChange={(e) => field.onChange(e.target.value)}
				placeholder={description}
				aria-label={label}
			/>
		);
	}

	if (schema.type === "number" || schema.type === "integer") {
		return (
			<Input
				type="number"
				inputMode="numeric"
				value={(field.value as string | number | undefined) ?? ""}
				onChange={(e) => {
					const raw = e.target.value;
					field.onChange(raw === "" ? undefined : Number(raw));
				}}
				aria-label={label}
			/>
		);
	}

	return (
		<Input
			type="text"
			value={String(field.value ?? "")}
			onChange={(e) => field.onChange(e.target.value)}
			aria-label={label}
		/>
	);
}

function SelectField({
	field,
	schema,
	options,
}: {
	field: ControllerRenderProps<Record<string, unknown>, string>;
	schema: JSONSchema;
	options: { label: string; value: unknown }[];
}) {
	const labelName = field.name.split(".").pop() ?? field.name;
	const resolved =
		schema.type === undefined && schema.anyOf
			? schema.anyOf.find((b) => b.type !== "null")
			: schema;
	const baseType = resolved?.type;
	const value = valueToString(field.value);
	return (
		<Select
			value={value}
			onValueChange={(v) => {
				field.onChange(stringToValue(v, options, baseType));
			}}
		>
			<SelectTrigger className="w-full">
				<SelectValue placeholder={`Select ${fieldLabel(schema, labelName).toLowerCase()}`} />
			</SelectTrigger>
			<SelectContent>
				{options.map((opt) => (
					<SelectItem key={valueToString(opt.value)} value={valueToString(opt.value)}>
						{opt.label}
					</SelectItem>
				))}
			</SelectContent>
		</Select>
	);
}

function CheckboxGroupField({
	field,
	schema,
}: {
	field: ControllerRenderProps<Record<string, unknown>, string>;
	schema: JSONSchema;
}) {
	const baseId = useId();
	const itemSchema = schema.items ?? { type: "string" };
	const options =
		optionsFromSchema(schema).length > 0
			? optionsFromSchema(schema)
			: optionsFromSchema(itemSchema);
	const selected = new Set(Array.isArray(field.value) ? field.value.map((v) => String(v)) : []);

	function toggle(rawValue: unknown, checked: boolean) {
		const strValue = String(rawValue);
		const next = new Set(selected);
		if (checked) {
			next.add(strValue);
		} else {
			next.delete(strValue);
		}
		const values = Array.from(next);
		// Preserve original value types when possible.
		field.onChange(options.length > 0 ? values.map((v) => stringToValue(v, options)) : values);
	}

	if (options.length > 0) {
		return (
			<div className="space-y-2">
				{options.map((opt, index) => {
					const str = String(opt.value);
					const id = `${baseId}-${index}`;
					return (
						<label key={str} htmlFor={id} className="flex items-center gap-2 text-sm">
							<Checkbox
								id={id}
								checked={selected.has(str)}
								onCheckedChange={(v) => toggle(opt.value, !!v)}
							/>
							{opt.label}
						</label>
					);
				})}
			</div>
		);
	}

	// ponytail: generic array of primitives is rendered as a list of text inputs.
	return <ArrayInputField field={field} schema={schema} />;
}

function ArrayInputField({
	field,
	schema,
}: {
	field: ControllerRenderProps<Record<string, unknown>, string>;
	schema: JSONSchema;
}) {
	const itemSchema = schema.items ?? { type: "string" };
	const resolved =
		itemSchema.type === undefined && itemSchema.anyOf
			? itemSchema.anyOf.find((b) => b.type !== "null")
			: itemSchema;
	const itemType = resolved?.type;
	const values: unknown[] = Array.isArray(field.value) ? field.value : [];

	function update(next: unknown[]) {
		field.onChange(next);
	}

	function add() {
		update([...values, itemType === "number" || itemType === "integer" ? 0 : ""]);
	}

	function remove(index: number) {
		const next = [...values];
		next.splice(index, 1);
		update(next);
	}

	function setValue(index: number, raw: string) {
		const next = [...values];
		if (raw === "" && itemType !== "string") {
			next[index] = itemType === "number" || itemType === "integer" ? 0 : raw;
		} else if (itemType === "number" || itemType === "integer") {
			const n = Number(raw);
			next[index] = Number.isNaN(n) ? 0 : n;
		} else {
			next[index] = raw;
		}
		update(next);
	}

	return (
		<div className="space-y-2">
			{values.map((value, index) => (
				// biome-ignore lint/suspicious/noArrayIndexKey: no stable id for user-added array rows
				<div key={index} className="flex items-center gap-2">
					<Input
						type={itemType === "number" || itemType === "integer" ? "number" : "text"}
						value={String(value ?? "")}
						onChange={(e) => setValue(index, e.target.value)}
					/>
					<Button type="button" variant="ghost" size="sm" onClick={() => remove(index)}>
						Remove
					</Button>
				</div>
			))}
			<Button type="button" size="sm" onClick={add}>
				Add
			</Button>
		</div>
	);
}

function ArrayField({ name, schema, required: _required }: SchemaFieldProps) {
	const { control } = useFormContext();
	const labelName = name.split(".").pop() ?? name;
	return (
		<FormField
			control={control}
			name={name}
			render={({ field, fieldState }) => (
				<FormItem className="space-y-1.5">
					<FormLabel>{fieldLabel(schema, labelName)}</FormLabel>
					<FormControl>
						<CheckboxGroupField field={field} schema={schema} />
					</FormControl>
					{fieldDescription(schema) && (
						<FormDescription>{fieldDescription(schema)}</FormDescription>
					)}
					<FormMessage>{fieldState.error?.message}</FormMessage>
				</FormItem>
			)}
		/>
	);
}

function JsonObjectField({ name, schema, required: _required }: SchemaFieldProps) {
	const { control } = useFormContext();
	const labelName = name.split(".").pop() ?? name;
	return (
		<FormField
			control={control}
			name={name}
			render={({ field, fieldState }) => {
				const raw =
					field.value === undefined || field.value === null
						? ""
						: typeof field.value === "object"
							? JSON.stringify(field.value, null, 2)
							: String(field.value);
				return (
					<FormItem className="space-y-1.5">
						<FormLabel>{fieldLabel(schema, labelName)}</FormLabel>
						<FormControl>
							<Textarea
								value={raw}
								onChange={(e) => {
									const text = e.target.value.trim();
									if (!text) {
										field.onChange(_required ? (schema.type === "array" ? [] : {}) : null);
									} else {
										try {
											field.onChange(JSON.parse(text));
										} catch {
											field.onChange(text);
										}
									}
								}}
								placeholder="JSON value"
							/>
						</FormControl>
						<FormMessage>{fieldState.error?.message}</FormMessage>
					</FormItem>
				);
			}}
		/>
	);
}

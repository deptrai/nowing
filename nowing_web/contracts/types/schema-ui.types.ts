/**
 * TypeScript view of the ``x-ui`` hints that the single schema-driven form
 * renderer uses to localise and specialise a field without hard-coding a UI
 * per tool.
 *
 * These hints are intentionally small: ``widget``, ``label``, ``options``,
 * ``unit``, ``group``, and ``vertical``.  Any unknown keys are ignored so
 * schemas can evolve without breaking the renderer.
 */

export type SchemaUiWidget =
	| "text"
	| "textarea"
	| "select"
	| "checkbox"
	| "switch"
	| "slider"
	| "price-vnd"
	| "district-picker"
	| "hidden";

export interface SchemaUiOption {
	label: string;
	value: unknown;
}

export interface SchemaUiHints {
	/** Which control to render. ``undefined`` means "infer from JSON Schema type". */
	widget?: SchemaUiWidget;
	/** Localised label shown to the user. Falls back to ``title`` or the field name. */
	label?: string;
	/** Options for ``select`` / ``checkbox`` widgets. */
	options?: SchemaUiOption[];
	/** Unit text shown after the input, e.g. "VND", "m²". */
	unit?: string;
	/** Optional layout group for future multi-column layout. Currently used as a data attribute. */
	group?: string;
	/** Which vertical this field belongs to; used for filtering/grouping. */
	vertical?: string;
}

/**
 * A tiny JSON Schema subset that the renderer understands.  Keep this
 * intentionally permissive: the renderer ignores anything it does not know
 * how to draw and the validation layer (Zod) validates the common subset.
 */
export interface JSONSchema {
	type?: "object" | "string" | "number" | "integer" | "boolean" | "array" | "null";
	title?: string;
	description?: string;
	properties?: Record<string, JSONSchema>;
	required?: string[];
	enum?: unknown[];
	const?: unknown;
	items?: JSONSchema;
	default?: unknown;
	minimum?: number;
	maximum?: number;
	minLength?: number;
	maxLength?: number;
	anyOf?: JSONSchema[];
	"x-ui"?: SchemaUiHints;
	// biome-ignore lint/suspicious/noExplicitAny: JSON Schemas carry arbitrary metadata.
	[key: string]: any;
}

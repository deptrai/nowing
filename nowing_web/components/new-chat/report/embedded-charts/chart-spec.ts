// Shared types for chart code-block specs (```chart:id)

export interface ChartSpec {
	type: "line" | "pie" | "bar" | "area" | "candle";
	source?: string;
	xKey?: string;
	yKey?: string;
	nameKey?: string;
	valueKey?: string;
	data: Record<string, unknown>[];
	title?: string;
	yLabel?: string;
}

export function parseChartSpec(spec: string): ChartSpec | null {
	try {
		const lines = spec.trim().split("\n");
		const obj: Record<string, unknown> = {};
		let dataStartIdx = -1;

		for (let i = 0; i < lines.length; i++) {
			const line = lines[i];
			const kv = line.match(/^(\w+):\s*(.+)$/);
			if (kv) {
				const [, key, value] = kv;
				if (key === "data") {
					const rest = value.trim();
					if (rest.startsWith("[")) {
						obj.data = JSON.parse(rest);
					} else {
						dataStartIdx = i + 1;
					}
				} else {
					obj[key] = value.trim();
				}
			} else if (dataStartIdx >= 0 && i >= dataStartIdx) {
				// Skip blank lines, then collect remaining as JSON array
				if (line.trim() === "") continue;
				const remaining = lines.slice(i).join("\n").trim();
				obj.data = JSON.parse(remaining);
				break;
			}
		}

		if (!obj.type || !Array.isArray(obj.data) || obj.data.length === 0) return null;
		const result = obj as ChartSpec;
		// Validate required string fields
		if (typeof result.type !== "string") return null;
		return result;
	} catch {
		return null;
	}
}

"use client";

import { useEffect, useState } from "react";
import CeleryQueuePanel from "@/components/admin/telemetry/CeleryQueuePanel";
import GrossMarginAlert from "@/components/admin/telemetry/GrossMarginAlert";
import LlmCostPanel from "@/components/admin/telemetry/LlmCostPanel";
import ProxyHealthPanel from "@/components/admin/telemetry/ProxyHealthPanel";

export default function AdminTelemetryPage() {
	const [tick, setTick] = useState(0);

	useEffect(() => {
		const id = setInterval(() => setTick((t) => t + 1), 5000);
		return () => clearInterval(id);
	}, []);

	return (
		<div className="p-6">
			<div className="mb-6 flex items-center justify-between">
				<h1 className="text-2xl font-bold">Admin: Telemetry</h1>
				<div className="text-sm text-slate-500">Refreshes every 5s</div>
			</div>

			<div className="space-y-6">
				<GrossMarginAlert tick={tick} />
				<LlmCostPanel tick={tick} />
				<ProxyHealthPanel tick={tick} />
				<CeleryQueuePanel tick={tick} />
			</div>
		</div>
	);
}

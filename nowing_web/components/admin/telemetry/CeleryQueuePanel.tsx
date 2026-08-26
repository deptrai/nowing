"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
	adminTelemetryApiService,
	type CeleryQueueInfo,
} from "@/lib/apis/admin-telemetry-api.service";

function queueStatusClass(status: string) {
	switch (status) {
		case "healthy":
			return "bg-green-100 text-green-700";
		case "degraded":
			return "bg-amber-100 text-amber-700";
		case "backed_up":
			return "bg-red-100 text-red-700";
		default:
			return "bg-slate-100 text-slate-600";
	}
}

function useLongPress(onLongPress: () => void, ms = 2000) {
	const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

	const start = useCallback(() => {
		timer.current = setTimeout(onLongPress, ms);
	}, [onLongPress, ms]);

	const stop = useCallback(() => {
		if (timer.current) {
			clearTimeout(timer.current);
			timer.current = null;
		}
	}, []);

	return { start, stop };
}

interface CeleryQueuePanelProps {
	tick?: number;
}

export default function CeleryQueuePanel({ tick }: CeleryQueuePanelProps) {
	const [queues, setQueues] = useState<CeleryQueueInfo[]>([]);
	const [overall, setOverall] = useState<string>("unavailable");
	const [activeWorkers, setActiveWorkers] = useState<number>(0);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [confirmQueue, setConfirmQueue] = useState<string | null>(null);

	const load = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			const d = await adminTelemetryApiService.celeryQueues();
			setQueues(d.queues);
			setOverall(d.status);
			setActiveWorkers(d.active_workers);
		} catch (err) {
			setError(err instanceof Error ? err.message : "Failed to load Celery queues");
		} finally {
			setLoading(false);
		}
	}, []);

	// biome-ignore lint/correctness/useExhaustiveDependencies: tick is the auto-refresh trigger
	useEffect(() => {
		void load();
	}, [load, tick]);

	const purge = async (queueName: string) => {
		setConfirmQueue(null);
		setLoading(true);
		setError(null);
		try {
			await adminTelemetryApiService.purgeDeadQueue(queueName);
			await load();
		} catch (err) {
			setError(err instanceof Error ? err.message : "Failed to purge queue");
		} finally {
			setLoading(false);
		}
	};

	return (
		<div className="space-y-4 rounded border p-4">
			<div className="flex items-center justify-between">
				<h3 className="text-lg font-semibold">Celery Queues</h3>
				<div className="flex items-center gap-2">
					<span
						className={`rounded px-2 py-0.5 text-sm font-medium ${
							overall === "healthy" ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-600"
						}`}
					>
						{overall}
					</span>
					<span className="text-sm text-slate-500">{activeWorkers} workers</span>
					<button
						type="button"
						onClick={load}
						className="h-9 rounded border bg-slate-100 px-3 text-sm hover:bg-slate-200"
					>
						Refresh
					</button>
				</div>
			</div>

			{loading && <div className="text-sm text-slate-500">Loading...</div>}
			{error && (
				<div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
					{error}
				</div>
			)}

			<div className="grid grid-cols-1 gap-4 md:grid-cols-2">
				{queues.map((q) => (
					<QueueCard key={q.name} queue={q} onPurge={() => setConfirmQueue(q.name)} />
				))}
			</div>

			{confirmQueue && (
				<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
					<div className="w-full max-w-sm rounded bg-white p-4 shadow dark:bg-slate-900">
						<h4 className="text-lg font-semibold">Confirm purge</h4>
						<p className="my-2 text-sm text-slate-600">
							This will remove stalled tasks from <code>{confirmQueue}</code>. Continue?
						</p>
						<div className="flex justify-end gap-2">
							<button
								type="button"
								onClick={() => setConfirmQueue(null)}
								className="rounded border px-3 py-2 text-sm hover:bg-slate-50"
							>
								Cancel
							</button>
							<button
								type="button"
								onClick={() => purge(confirmQueue)}
								className="rounded bg-red-600 px-3 py-2 text-sm text-white hover:bg-red-700"
							>
								Purge
							</button>
						</div>
					</div>
				</div>
			)}
		</div>
	);
}

function QueueCard({ queue, onPurge }: { queue: CeleryQueueInfo; onPurge: () => void }) {
	const { start, stop } = useLongPress(onPurge);

	return (
		<div className="rounded border p-4">
			<div className="mb-2 flex items-center justify-between">
				<div>
					<div className="font-mono text-sm font-semibold">{queue.name}</div>
					<div className="text-xs text-slate-500">
						{queue.workers} workers · {queue.throughput_per_min}/min
					</div>
				</div>
				<span
					className={`rounded px-2 py-0.5 text-xs font-medium ${queueStatusClass(queue.status)}`}
				>
					{queue.status}
				</span>
			</div>
			<div className="mb-3">
				<div className="text-xs text-slate-500">Queue length</div>
				<div className="font-mono text-lg">{queue.length.toLocaleString()}</div>
				<div className="text-xs text-slate-500">Stalled: {queue.stalled_count}</div>
			</div>
			<button
				type="button"
				onMouseDown={start}
				onMouseUp={stop}
				onMouseLeave={stop}
				onTouchStart={start}
				onTouchEnd={stop}
				className="w-full rounded border px-3 py-2 text-sm hover:bg-slate-50 active:bg-red-50"
			>
				Hold 2s to purge
			</button>
		</div>
	);
}

"use client";

import { Activity, Layers, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import AlertBanner from "@/components/admin/health/AlertBanner";
import HealthCategoryTabs from "@/components/admin/health/HealthCategoryTabs";
import HealthDrillDown from "@/components/admin/health/HealthDrillDown";
import HealthOverviewGrid from "@/components/admin/health/HealthOverviewGrid";
import HealthStatusCard from "@/components/admin/health/HealthStatusCard";
import CeleryQueuePanel from "@/components/admin/telemetry/CeleryQueuePanel";
import GrossMarginAlert from "@/components/admin/telemetry/GrossMarginAlert";
import LlmCostPanel from "@/components/admin/telemetry/LlmCostPanel";
import ProxyHealthPanel from "@/components/admin/telemetry/ProxyHealthPanel";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
	adminHealthApiService,
	type HealthAlertItem,
	type HealthOverviewResponse,
	type HealthProbeResultResponse,
	type HealthStatusItem,
} from "@/lib/apis/admin-health-api.service";

export default function AdminTelemetryPage() {
	const [tick, setTick] = useState(0);
	const [activeTab, setActiveTab] = useState("health");

	// Health Dashboard State
	const [overview, setOverview] = useState<HealthOverviewResponse | null>(null);
	const [statuses, setStatuses] = useState<HealthStatusItem[]>([]);
	const [alerts, setAlerts] = useState<HealthAlertItem[]>([]);
	const [selectedCategory, setSelectedCategory] = useState("all");
	const [selectedService, setSelectedService] = useState<HealthStatusItem | null>(null);
	const [drillDownOpen, setDrillDownOpen] = useState(false);
	const [_loadingHealth, _setLoadingHealth] = useState(false);

	// Fetch health data with Promise.allSettled
	const fetchHealthData = useCallback(async () => {
		try {
			const [overviewRes, alertsRes] = await Promise.allSettled([
				adminHealthApiService.getOverview(),
				adminHealthApiService.getActiveAlerts(),
			]);

			if (overviewRes.status === "fulfilled") {
				setOverview(overviewRes.value);
			} else {
				console.error("Failed to load health overview:", overviewRes.reason);
			}

			if (alertsRes.status === "fulfilled") {
				setAlerts(alertsRes.value.items || []);
			} else {
				console.error("Failed to load health alerts:", alertsRes.reason);
			}
		} catch (err) {
			console.error("Failed to load health telemetry:", err);
		}
	}, []);

	// Fetch services by category
	const fetchServices = useCallback(async (cat: string) => {
		try {
			const category = cat === "all" ? undefined : cat;
			const res = await adminHealthApiService.getStatuses({ category });
			setStatuses(res.items || []);
		} catch (err) {
			console.error("Failed to load health statuses:", err);
		}
	}, []);

	// Initial load and periodic refresh (15s for health, 5s for metrics tick)
	useEffect(() => {
		const id = setInterval(() => setTick((t) => t + 1), 5000);
		return () => clearInterval(id);
	}, []);

	useEffect(() => {
		fetchHealthData();
		const healthInterval = setInterval(fetchHealthData, 15000);
		return () => clearInterval(healthInterval);
	}, [fetchHealthData]);

	useEffect(() => {
		fetchServices(selectedCategory);
	}, [selectedCategory, fetchServices]);

	const handleAcknowledgeAlert = async (alertId: number) => {
		try {
			await adminHealthApiService.acknowledgeAlert(alertId, 60);
			// Optimistically remove from alert list
			setAlerts((prev) => prev.filter((a) => a.id !== alertId));
			toast.success("Alert acknowledged and snoozed for 60 minutes");
			fetchHealthData();
		} catch (err) {
			console.error("Failed to acknowledge alert:", err);
			toast.error("Failed to acknowledge alert. Please check your network and permissions.");
		}
	};

	const handleCardClick = (item: HealthStatusItem) => {
		setSelectedService(item);
		setDrillDownOpen(true);
	};

	const handleProbeSuccess = (probeResult: HealthProbeResultResponse) => {
		// Update item in local statuses state or insert if new
		setStatuses((prev) => {
			const exists = prev.some((s) => s.service_id === probeResult.service_id);
			if (exists) {
				return prev.map((s) =>
					s.service_id === probeResult.service_id
						? {
								...s,
								status: probeResult.status as HealthStatusItem["status"],
								latency_ms: probeResult.latency_ms,
								last_error: probeResult.last_error,
								suggested_action: probeResult.suggested_action,
								last_probe_at: probeResult.probed_at,
							}
						: s
				);
			}
			const newItem: HealthStatusItem = {
				id: Date.now(),
				category: probeResult.category,
				service_id: probeResult.service_id,
				service_name: probeResult.service_name,
				display_group: probeResult.display_group,
				status: probeResult.status as HealthStatusItem["status"],
				last_probe_at: probeResult.probed_at,
				next_probe_at: null,
				latency_ms: probeResult.latency_ms,
				error_rate_15m: probeResult.error_rate_15m,
				success_rate_15m: probeResult.success_rate_15m,
				last_error: probeResult.last_error,
				suggested_action: probeResult.suggested_action,
				metadata_payload: probeResult.metadata,
				alert_threshold: null,
				acknowledged_until: null,
				updated_at: probeResult.probed_at,
			};
			return [newItem, ...prev];
		});
		fetchHealthData();
	};

	const categories = overview?.registered_categories || [
		"infra",
		"model",
		"scraper",
		"connector",
		"proxy",
		"research",
		"messaging",
		"payment",
		"storage",
	];

	return (
		<div className="p-6 space-y-6">
			<div className="flex items-center justify-between">
				<div>
					<h1 className="text-2xl font-bold tracking-tight">Admin: Operations & Telemetry</h1>
					<p className="text-sm text-slate-500">
						Centralized monitoring for infrastructure, third-party APIs, and real-time costs
					</p>
				</div>
				<div className="flex items-center gap-3">
					<div className="text-xs text-slate-500 flex items-center gap-1">
						<RefreshCw className="h-3 w-3 animate-spin text-slate-400" />
						Auto-refreshes live
					</div>
				</div>
			</div>

			<Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
				<TabsList className="h-10">
					<TabsTrigger value="health" className="gap-2" data-testid="tab-trigger-health">
						<Activity className="h-4 w-4" />
						Third-Party Health & Operations
					</TabsTrigger>
					<TabsTrigger value="telemetry" className="gap-2" data-testid="tab-trigger-telemetry">
						<Layers className="h-4 w-4" />
						Cost & Queue Telemetry
					</TabsTrigger>
				</TabsList>

				<TabsContent value="health" className="space-y-6">
					{/* Active Alerts Banner */}
					<AlertBanner alerts={alerts} onAcknowledge={handleAcknowledgeAlert} />

					{/* 5-Column Overview Metric Grid */}
					<HealthOverviewGrid overview={overview} />

					{/* Category Selector Tabs */}
					<div className="space-y-4">
						<div className="flex items-center justify-between">
							<h2 className="text-lg font-semibold tracking-tight">Monitored Services</h2>
							<span className="text-xs text-muted-foreground">
								Showing {statuses.length} services
							</span>
						</div>

						<HealthCategoryTabs
							categories={categories}
							selectedCategory={selectedCategory}
							onSelectCategory={setSelectedCategory}
							overview={overview}
						/>

						{/* Service Health Cards Grid */}
						{statuses.length === 0 ? (
							<div className="text-center py-12 text-sm text-muted-foreground border border-dashed rounded-lg space-y-3">
								<p>No services found for category &ldquo;{selectedCategory}&rdquo;.</p>
								{selectedCategory !== "all" && (
									<Button variant="outline" size="sm" onClick={() => setSelectedCategory("all")}>
										Switch to All Categories
									</Button>
								)}
							</div>
						) : (
							<div
								className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
								data-testid="health-status-grid"
							>
								{statuses.map((item) => (
									<HealthStatusCard key={item.service_id} item={item} onClick={handleCardClick} />
								))}
							</div>
						)}
					</div>

					{/* Service Detail Modal */}
					<HealthDrillDown
						item={selectedService}
						open={drillDownOpen}
						onOpenChange={setDrillDownOpen}
						onProbeSuccess={handleProbeSuccess}
					/>
				</TabsContent>

				<TabsContent value="telemetry" className="space-y-6">
					<GrossMarginAlert tick={tick} />
					<LlmCostPanel tick={tick} />
					<ProxyHealthPanel tick={tick} />
					<CeleryQueuePanel tick={tick} />
				</TabsContent>
			</Tabs>
		</div>
	);
}

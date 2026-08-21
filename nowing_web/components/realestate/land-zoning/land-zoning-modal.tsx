"use client";

import { MapPin } from "lucide-react";
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { scrapersApiService } from "@/lib/apis/scrapers-api.service";
import { cn } from "@/lib/utils";

import "leaflet/dist/leaflet.css";

type PlanningZone = {
	id: number;
	province: string;
	district: string | null;
	ward: string | null;
	zone_code: string;
	zone_name: string;
	planning_period: string | null;
	effective_year: number | null;
	expiry_year: number | null;
	legal_document_ref: string | null;
	polarity: "safe" | "danger" | "warning" | "commercial" | "agricultural" | "other";
	polarity_color: string;
};

type ZoningCheckOutput = {
	latitude: number;
	longitude: number;
	address: string | null;
	has_road_expansion_risk: boolean;
	zones: PlanningZone[];
	summary: string;
	risk_notes: string[];
	query_latency_ms: number | null;
};

// Leaflet must run only in the browser.
const MapWithNoSSR = dynamic(() => import("./zoning-map"), { ssr: false });

const polarityClass: Record<PlanningZone["polarity"], string> = {
	safe: "bg-green-100 text-green-800 border-green-200",
	danger: "bg-red-100 text-red-800 border-red-200",
	warning: "bg-orange-100 text-orange-800 border-orange-200",
	commercial: "bg-blue-100 text-blue-800 border-blue-200",
	agricultural: "bg-yellow-100 text-yellow-800 border-yellow-200",
	other: "bg-gray-100 text-gray-800 border-gray-200",
};

export interface LandZoningModalProps {
	workspaceId: number | string;
	open: boolean;
	onOpenChange: (open: boolean) => void;
	/** Optional initial coordinates. */
	initialLatitude?: number;
	initialLongitude?: number;
}

export function LandZoningModal({
	workspaceId,
	open,
	onOpenChange,
	initialLatitude,
	initialLongitude,
}: LandZoningModalProps) {
	const [lat, setLat] = useState<string>(initialLatitude?.toString() ?? "21.0285");
	const [lng, setLng] = useState<string>(initialLongitude?.toString() ?? "105.8542");
	const [result, setResult] = useState<ZoningCheckOutput | null>(null);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const handleCheck = async () => {
		const latitude = parseFloat(lat);
		const longitude = parseFloat(lng);
		if (Number.isNaN(latitude) || Number.isNaN(longitude)) {
			setError("Vui lòng nhập tọa độ hợp lệ");
			return;
		}
		setLoading(true);
		setError(null);
		try {
			const data = (await scrapersApiService.run(workspaceId, "realestate", "zoning", {
				latitude,
				longitude,
			})) as ZoningCheckOutput;
			setResult(data);
		} catch (err) {
			setError(err instanceof Error ? err.message : "Không thể tra cứu quy hoạch");
		} finally {
			setLoading(false);
		}
	};

	useEffect(() => {
		if (initialLatitude !== undefined && initialLongitude !== undefined) {
			setLat(initialLatitude.toString());
			setLng(initialLongitude.toString());
		}
	}, [initialLatitude, initialLongitude]);

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="max-w-3xl">
				<DialogHeader>
					<DialogTitle>Thẩm định quy hoạch đất đai</DialogTitle>
				</DialogHeader>

				<div className="grid gap-4 py-4">
					<div className="grid grid-cols-2 gap-4">
						<div className="space-y-1">
							<Label htmlFor="lat">Vĩ độ</Label>
							<Input
								id="lat"
								value={lat}
								onChange={(e) => setLat(e.target.value)}
								placeholder="21.0285"
							/>
						</div>
						<div className="space-y-1">
							<Label htmlFor="lng">Kinh độ</Label>
							<Input
								id="lng"
								value={lng}
								onChange={(e) => setLng(e.target.value)}
								placeholder="105.8542"
							/>
						</div>
					</div>
					<Button onClick={handleCheck} disabled={loading}>
						{loading ? "Đang tra cứu…" : "Kiểm tra quy hoạch"}
					</Button>

					{error && <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</div>}

					{result && (
						<div className="space-y-4">
							<div
								className={cn(
									"rounded-md border p-3 text-sm",
									result.has_road_expansion_risk
										? "border-red-200 bg-red-50 text-red-800"
										: "border-green-200 bg-green-50 text-green-800"
								)}
							>
								<p>{result.summary}</p>
								{result.query_latency_ms !== null && (
									<p className="mt-1 text-xs opacity-70">
										Thời gian truy vấn: {result.query_latency_ms.toFixed(2)}ms
									</p>
								)}
							</div>

							<div className="h-64 w-full overflow-hidden rounded-md border">
								<MapWithNoSSR
									latitude={result.latitude}
									longitude={result.longitude}
									zones={result.zones}
								/>
							</div>

							{result.risk_notes.length > 0 && (
								<div className="space-y-1">
									<h4 className="text-sm font-medium text-red-700">Cảnh báo rủi ro</h4>
									<ul className="list-disc space-y-1 pl-4 text-sm text-red-700">
										{result.risk_notes.map((note) => (
											<li key={note}>{note}</li>
										))}
									</ul>
								</div>
							)}

							<div className="space-y-2">
								<h4 className="text-sm font-medium">Các vùng quy hoạch phát hiện</h4>
								<div className="flex flex-wrap gap-2">
									{result.zones.map((zone) => (
										<Badge
											key={zone.id ?? `${zone.zone_code}-${zone.province}`}
											variant="outline"
											className={cn(polarityClass[zone.polarity] ?? polarityClass.other)}
										>
											<MapPin className="mr-1 h-3 w-3" />
											{zone.zone_name} ({zone.zone_code})
										</Badge>
									))}
								</div>
							</div>
						</div>
					)}
				</div>
			</DialogContent>
		</Dialog>
	);
}

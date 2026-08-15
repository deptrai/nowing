"use client";

import { useParams, useSearchParams } from "next/navigation";
import { useState } from "react";

import { LandZoningModal } from "@/components/realestate/land-zoning/land-zoning-modal";
import { Button } from "@/components/ui/button";

export default function LandZoningPage() {
	const params = useParams<{ workspace_id: string }>();
	const searchParams = useSearchParams();
	const [open, setOpen] = useState(true);

	const lat = searchParams.get("lat");
	const lng = searchParams.get("lng");

	return (
		<div className="mx-auto w-full max-w-3xl py-6 md:py-8">
			<Button onClick={() => setOpen(true)}>Mở Thẩm định Quy hoạch Đất đai</Button>
			<LandZoningModal
				workspaceId={params.workspace_id}
				open={open}
				onOpenChange={setOpen}
				initialLatitude={lat ? parseFloat(lat) : undefined}
				initialLongitude={lng ? parseFloat(lng) : undefined}
			/>
		</div>
	);
}

"use client";

import type { LatLngExpression } from "leaflet";
import L from "leaflet";
import { useEffect, useMemo } from "react";
import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";

const svgIconUrl =
	"data:image/svg+xml;base64," +
	btoa(
		`<svg xmlns="http://www.w3.org/2000/svg" width="25" height="41" viewBox="0 0 25 41">
			<path fill="#ef4444" d="M12.5 0C5.6 0 0 5.6 0 12.5c0 9.4 12.5 28.5 12.5 28.5S25 21.9 25 12.5C25 5.6 19.4 0 12.5 0z"/>
			<circle fill="#fff" cx="12.5" cy="12.5" r="5"/>
		</svg>`
	);

type Zone = {
	latitude: number;
	longitude: number;
	zones: {
		id?: number;
		province: string;
		district: string | null;
		ward: string | null;
		zone_code: string;
		zone_name: string;
		polarity_color: string;
	}[];
};

function MapRefresher({ center }: { center: LatLngExpression }) {
	const map = useMap();
	useEffect(() => {
		map.setView(center, 15);
	}, [map, center]);
	return null;
}

export default function ZoningMap({ latitude, longitude, zones }: Zone) {
	const center: LatLngExpression = [latitude, longitude];
	const markerIcon = useMemo(
		() =>
			new L.Icon({
				iconUrl: svgIconUrl,
				iconSize: [25, 41],
				iconAnchor: [12, 41],
				popupAnchor: [1, -34],
			}),
		[]
	);

	return (
		<MapContainer center={center} zoom={15} scrollWheelZoom className="h-full w-full">
			<TileLayer
				attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
				url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
			/>
			<MapRefresher center={center} />
			<Marker position={center} icon={markerIcon}>
				<Popup>
					<div className="space-y-1">
						<p className="font-medium">
							Tọa độ: {latitude}, {longitude}
						</p>
						{zones.slice(0, 5).map((zone) => (
							<p
								key={zone.id ?? `${zone.zone_code}-${zone.province}`}
								className="text-sm"
								style={{ color: zone.polarity_color }}
							>
								{zone.zone_name} ({zone.zone_code})
							</p>
						))}
					</div>
				</Popup>
			</Marker>
		</MapContainer>
	);
}

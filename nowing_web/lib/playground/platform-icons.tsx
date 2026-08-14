import { Briefcase, Building2, Home, TrendingUp } from "lucide-react";
import Image from "next/image";
import { cn } from "@/lib/utils";

/**
 * Full-color brand marks for the platform-native scraper verbs, served from
 * `/public/connectors/*.svg` (same asset library the connector UI uses). Each
 * is a `ComponentType<{ className?: string }>` so it drops into the playground
 * catalog and the composer badge exactly like a Lucide/Tabler icon.
 */
function brandIcon(src: string, alt: string) {
	return function BrandIcon({ className }: { className?: string }) {
		return (
			<Image
				src={src}
				alt={alt}
				width={20}
				height={20}
				className={cn("select-none object-contain pointer-events-none", className)}
				draggable={false}
			/>
		);
	};
}

export const BatdongsanIcon = brandIcon("/connectors/batdongsan.svg", "Batdongsan");
export const AmazonIcon = brandIcon("/connectors/amazon.svg", "Amazon");
export const RedditIcon = brandIcon("/connectors/reddit.svg", "Reddit");
export const YouTubeIcon = brandIcon("/connectors/youtube.svg", "YouTube");
export const InstagramIcon = brandIcon("/connectors/instagram.svg", "Instagram");
export const TikTokIcon = brandIcon("/connectors/tiktok.svg", "TikTok");
export const GoogleMapsIcon = brandIcon("/connectors/google-maps.svg", "Google Maps");
export const GoogleSearchIcon = brandIcon("/connectors/google-search.svg", "Google Search");
export const WebIcon = brandIcon("/connectors/web.svg", "Web");

export const ChototIcon = Home;
export const MuabanBdsIcon = Building2;

export const IndeedIcon = brandIcon("/connectors/indeed.svg", "Indeed");

// Epic 12 — Vietnam Job Market. Using Lucide Briefcase as a shared job-market
// mark until dedicated brand SVGs are added to /public/connectors.
export const VietnamworksIcon = Briefcase;
export const TopcvIcon = Briefcase;
export const ItviecIcon = Briefcase;
export const VnJobsIcon = Briefcase;

// Epic 2.7 — Walmart product + reviews scraper. Briefcase is a placeholder
// until a dedicated Walmart brand SVG is added to /public/connectors.
export const WalmartIcon = Briefcase;

// Epic 15.1 — CafeF stock / financial data. TrendingUp is a placeholder
// until a dedicated CafeF brand SVG is added to /public/connectors.
export const CafeFIcon = TrendingUp;

// Epic 15.2 — Vietstock stock / financial data. TrendingUp is a placeholder
// until a dedicated Vietstock brand SVG is added to /public/connectors.
export const VietstockIcon = TrendingUp;

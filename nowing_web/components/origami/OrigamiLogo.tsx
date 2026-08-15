import type React from "react";
import { cn } from "@/lib/utils";

interface OrigamiLogoProps {
	className?: string;
	size?: number;
	showText?: boolean;
	textClassName?: string;
}

export const OrigamiLogo: React.FC<OrigamiLogoProps> = ({
	className,
	size = 32,
	showText = false,
	textClassName,
}) => {
	return (
		<div className={cn("inline-flex items-center gap-2.5 select-none", className)}>
			{/* Origami Geometric Icon in Mint & Emerald Green */}
			<div
				style={{ width: size, height: size }}
				className="relative flex items-center justify-center rounded-lg bg-gradient-to-br from-emerald-400 via-teal-500 to-emerald-600 shadow-md shadow-emerald-500/20 text-white flex-shrink-0"
			>
				<svg
					viewBox="0 0 24 24"
					width={size * 0.65}
					height={size * 0.65}
					fill="currentColor"
					xmlns="http://www.w3.org/2000/svg"
					aria-label="Nowing Origami Logo"
				>
					{/* Geometric origami facets */}
					<path d="M12 2L2 9.5L12 17L22 9.5L12 2Z" fill="white" fillOpacity="0.95" />
					<path d="M12 17L2 9.5L12 22L22 9.5L12 17Z" fill="white" fillOpacity="0.65" />
					<path d="M12 2L12 17L22 9.5L12 2Z" fill="white" fillOpacity="0.8" />
				</svg>
			</div>

			{showText && (
				<div className={cn("flex items-center gap-1.5", textClassName)}>
					<span className="font-extrabold text-xl tracking-tight text-slate-900 dark:text-white">
						Nowing
					</span>
					<span className="text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-400 border border-emerald-200/60 dark:border-emerald-800/60">
						AI Lead
					</span>
				</div>
			)}
		</div>
	);
};

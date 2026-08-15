"use client";

import { Check, Code2, Copy, Download, FileCode } from "lucide-react";
import type React from "react";
import { useState } from "react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

export interface ArtifactsStudioPanelProps {
	workspaceId?: string | number;
	className?: string;
}

export const ArtifactsStudioPanel: React.FC<ArtifactsStudioPanelProps> = ({
	workspaceId: _workspaceId = "1",
	className,
}) => {
	const [hasCopied, setHasCopied] = useState(false);
	const [activeFile, setActiveFile] = useState<"zns_template" | "crawler_script">("zns_template");

	const sampleZnsPayload = `{
  "phone": "0986267856",
  "template_id": "zns_lead_outreach_v1",
  "template_data": {
    "customer_name": "Anh Việt Anh",
    "company_name": "Công ty BĐS Việt Anh",
    "property_interest": "Dự án Biệt thự phía Tây Hà Nội",
    "consultant_name": "Nowing AI Sales Rep",
    "booking_link": "https://nowing.net/bds/meet?ref=lead_4"
  },
  "tracking_source": "origami_outbound"
}`;

	const sampleCrawlerPython = `# Auto-generated Scraper Script for Batdongsan.com.vn
import asyncio
from nowing_scraper import FastCrawler

async def run():
    crawler = FastCrawler(anti_captcha=True, session_pool_size=5)
    results = await crawler.scrape_listings(
        location="Hà Nội",
        category="Bán nhà mặt phố",
        min_price=5_000_000_000,
        limit=20
    )
    print(f"Discovered {len(results)} high-intent leads!")

if __name__ == "__main__":
    asyncio.run(run())
`;

	const currentCode = activeFile === "zns_template" ? sampleZnsPayload : sampleCrawlerPython;

	const handleCopy = async () => {
		await navigator.clipboard.writeText(currentCode);
		setHasCopied(true);
		toast.success("Đã sao chép nội dung vào Clipboard!");
		setTimeout(() => setHasCopied(false), 2000);
	};

	const handleDownload = () => {
		const filename =
			activeFile === "zns_template" ? "zalo_zns_template.json" : "scrape_batdongsan.py";
		const blob = new Blob([currentCode], { type: "text/plain;charset=utf-8" });
		const url = URL.createObjectURL(blob);
		const a = document.createElement("a");
		a.href = url;
		a.download = filename;
		a.click();
		URL.revokeObjectURL(url);
		toast.success(`Đã tải về tệp ${filename}`);
	};

	return (
		<div
			className={cn(
				"h-full flex flex-col bg-background text-foreground overflow-hidden font-sans",
				className
			)}
		>
			{/* Top Bar */}
			<div className="h-10 border-b border-border/80 bg-muted/30 flex items-center justify-between px-4 shrink-0">
				<div className="flex items-center gap-1.5">
					<button
						type="button"
						onClick={() => setActiveFile("zns_template")}
						className={cn(
							"flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-md transition-colors cursor-pointer",
							activeFile === "zns_template"
								? "bg-background text-foreground shadow-xs border border-border/80"
								: "text-muted-foreground hover:text-foreground hover:bg-muted/60"
						)}
					>
						<Code2 className="w-3.5 h-3.5 text-blue-500" />
						<span>zalo_zns_template.json</span>
					</button>
					<button
						type="button"
						onClick={() => setActiveFile("crawler_script")}
						className={cn(
							"flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-md transition-colors cursor-pointer",
							activeFile === "crawler_script"
								? "bg-background text-foreground shadow-xs border border-border/80"
								: "text-muted-foreground hover:text-foreground hover:bg-muted/60"
						)}
					>
						<FileCode className="w-3.5 h-3.5 text-emerald-500" />
						<span>scrape_batdongsan.py</span>
					</button>
				</div>

				<div className="flex items-center gap-2">
					<button
						type="button"
						onClick={handleCopy}
						className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-md border border-border/80 bg-card hover:bg-muted text-foreground transition-colors cursor-pointer"
					>
						{hasCopied ? (
							<Check className="w-3 h-3 text-emerald-600" />
						) : (
							<Copy className="w-3 h-3" />
						)}
						<span>{hasCopied ? "Đã chép" : "Sao chép"}</span>
					</button>
					<button
						type="button"
						onClick={handleDownload}
						className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-md bg-emerald-600 hover:bg-emerald-500 text-white transition-colors cursor-pointer shadow-xs"
					>
						<Download className="w-3 h-3" />
						<span>Tải Về</span>
					</button>
				</div>
			</div>

			{/* Code Studio Area */}
			<div className="flex-1 overflow-y-auto p-4 bg-zinc-950 text-zinc-100 font-mono text-xs leading-relaxed select-text scrollbar-thin">
				<pre className="overflow-x-auto">
					<code>{currentCode}</code>
				</pre>
			</div>
		</div>
	);
};

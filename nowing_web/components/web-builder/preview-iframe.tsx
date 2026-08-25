"use client";

import { useEffect, useRef } from "react";

export interface MarkElementData {
	selector: string;
	tag: string;
	text: string;
	rect?: { x: number; y: number; width: number; height: number };
	component_hint?: string;
}

interface PreviewIframeProps {
	src: string;
	appId: string;
	title: string;
	isMarkToolActive: boolean;
	previewOrigin: string;
	onMarkElementSelected: (data: MarkElementData) => void;
	iframeKey?: number;
}

export function PreviewIframe({
	src,
	appId,
	title,
	isMarkToolActive,
	previewOrigin,
	onMarkElementSelected,
	iframeKey = 0,
}: PreviewIframeProps) {
	const iframeRef = useRef<HTMLIFrameElement>(null);

	// Send the Mark Tool toggle state to the preview iframe, targeting its origin.
	useEffect(() => {
		const iframe = iframeRef.current;
		if (!iframe?.contentWindow || !previewOrigin) return;
		iframe.contentWindow.postMessage(
			{ type: "TOGGLE_MARK_TOOL", active: isMarkToolActive },
			previewOrigin
		);
	}, [isMarkToolActive, previewOrigin]);

	// Listen for selected element messages from the preview iframe.
	useEffect(() => {
		const handleMessage = (event: MessageEvent) => {
			if (event.origin !== previewOrigin) return;
			if (event.source !== iframeRef.current?.contentWindow) return;
			if (event.data?.type === "MARK_ELEMENT_SELECTED") {
				onMarkElementSelected({
					selector: event.data.selector || "",
					tag: event.data.tag || "",
					text: event.data.text || "",
					rect: event.data.rect,
					component_hint: event.data.component_hint,
				});
			}
		};

		window.addEventListener("message", handleMessage);
		return () => window.removeEventListener("message", handleMessage);
	}, [previewOrigin, onMarkElementSelected]);

	return (
		<iframe
			ref={iframeRef}
			key={`${appId}-${iframeKey}`}
			id="web-builder-preview-iframe"
			data-testid="web-app-preview-frame"
			src={src}
			title={title}
			sandbox="allow-scripts allow-same-origin"
			className="w-full h-full border-0 bg-slate-950"
			onLoad={() => {
				if (iframeRef.current?.contentWindow && previewOrigin) {
					iframeRef.current.contentWindow.postMessage(
						{ type: "TOGGLE_MARK_TOOL", active: isMarkToolActive },
						previewOrigin
					);
				}
			}}
		/>
	);
}

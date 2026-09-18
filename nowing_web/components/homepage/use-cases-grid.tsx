"use client";

import { AnimatePresence, motion } from "motion/react";
import Image from "next/image";
import { ExpandedGifOverlay, useExpandedGif } from "@/components/ui/expanded-gif-overlay";
import { useTranslations } from "next-intl";

function getUseCases(t: (k: string) => string) {
	return [
		{ title: t("g1_title"), description: t("g1_desc"), src: "/homepage/hero_tutorial/BSNCGif.gif" },
		{ title: t("g2_title"), description: t("g2_desc"), src: "/homepage/hero_tutorial/BQnaGif_compressed.gif" },
		{ title: t("g3_title"), description: t("g3_desc"), src: "/homepage/hero_tutorial/ReportGenGif_compressed.gif" },
		{ title: t("g4_title"), description: t("g4_desc"), src: "/homepage/hero_tutorial/PodcastGenGif.gif" },
		{ title: t("g5_title"), description: t("g5_desc"), src: "/homepage/hero_tutorial/ImageGenGif.gif" },
		{ title: t("g6_title"), description: t("g6_desc"), src: "/homepage/hero_realtime/RealTimeChatGif.gif" },
		{ title: t("g7_title"), description: t("g7_desc"), src: "/homepage/hero_realtime/RealTimeCommentsFlow.gif" },
	];
}

function UseCaseCard({
	title,
	description,
	src,
	className,
}: {
	title: string;
	description: string;
	src: string;
	className?: string;
}) {
	const { expanded, open, close } = useExpandedGif();

	return (
		<>
			<motion.div
				initial="hidden"
				whileInView="visible"
				viewport={{ once: true, margin: "-60px" }}
				variants={{
					hidden: { opacity: 0, y: 24 },
					visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: "easeOut" } },
				}}
				className={`group overflow-hidden rounded-2xl border border-neutral-200/60 bg-white shadow-sm transition-shadow duration-300 hover:shadow-xl dark:border-neutral-700/60 dark:bg-neutral-900 ${className ?? ""}`}
			>
				{/* biome-ignore lint/a11y/useSemanticElements: div wraps img, button would break layout */}
				<div
					role="button"
					tabIndex={0}
					aria-label={`Expand ${title}`}
					className="cursor-pointer overflow-hidden bg-neutral-50 p-2 dark:bg-neutral-950"
					onClick={open}
					onKeyDown={(e) => {
						if (e.key === "Enter" || e.key === " ") {
							e.preventDefault();
							open();
						}
					}}
				>
					<img
						src={src}
						alt={title}
						className="w-full rounded-xl object-cover transition-transform duration-500 group-hover:scale-[1.02]"
					/>
					<div className="relative w-full h-48">
						<Image
							src={src}
							alt={title}
							fill
							className="rounded-xl object-cover transition-transform duration-500 group-hover:scale-[1.02]"
							unoptimized={src.endsWith(".gif")}
						/>
					</div>
				</div>
				<div className="px-5 py-4">
					<h3 className="text-base font-semibold text-neutral-900 dark:text-white">{title}</h3>
					<p className="mt-1 text-sm text-neutral-500 dark:text-neutral-400">{description}</p>
				</div>
			</motion.div>

			<AnimatePresence>
				{expanded && <ExpandedGifOverlay src={src} alt={title} onClose={close} />}
			</AnimatePresence>
		</>
	);
}

export function UseCasesGrid() {
	const t = useTranslations("homepage");
	const useCases = getUseCases(t);
	return (
		<section className="relative mx-auto max-w-7xl px-4 py-4 sm:px-6 sm:py-8 lg:px-8">
			<div className="mb-6 text-center">
				<h2 className="font-serif text-3xl font-normal tracking-tight text-neutral-900 sm:text-4xl dark:text-white">{t("home_what_you_can_do")}</h2>
			</div>

			{/* Row 1: 2 larger cards */}
			<div className="grid grid-cols-1 gap-5 md:grid-cols-2">
				{useCases.slice(0, 2).map((useCase) => (
					<UseCaseCard key={useCase.title} {...useCase} />
				))}
			</div>

			{/* Row 2: 3 equal cards */}
			<div className="mt-5 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
				{useCases.slice(2, 5).map((useCase) => (
					<UseCaseCard key={useCase.title} {...useCase} />
				))}
			</div>

			{/* Row 3: 2 cards */}
			<div className="mt-5 grid grid-cols-1 gap-5 md:grid-cols-2">
				{useCases.slice(5).map((useCase) => (
					<UseCaseCard key={useCase.title} {...useCase} />
				))}
			</div>

			<p className="mt-8 text-center text-sm text-neutral-500 dark:text-neutral-400">{t("home_and_more_coming_soon")}</p>
		</section>
	);
}

"use client";

import styles from "./AmbientBackground.module.css";

export const AmbientBackground = () => {
	return (
		<div
			className="pointer-events-none absolute inset-0 z-0 h-full w-full overflow-hidden"
			aria-hidden="true"
		>
			<div className={`${styles.beamOne} absolute left-0 top-0`} />
			<div className={`${styles.beamTwo} absolute left-0 top-0`} />
			<div className={`${styles.beamThree} left-0 top-0`} />
		</div>
	);
};

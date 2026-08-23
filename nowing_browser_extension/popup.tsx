import { Storage } from "@plasmohq/storage";
import { useEffect, useState } from "react";
import { MemoryRouter } from "react-router-dom";
import { Routing } from "~routes";
import { Toaster } from "~routes/ui/toaster";
import { buildBackendUrl } from "~utils/backend-url";

const storage = new Storage({ area: "local" });

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function IndexPopup() {
	const [resuming, setResuming] = useState(false);
	const [activeMissionId, setActiveMissionId] = useState<string | null>(null);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		storage.get("activeMissionId").then((id) => {
			if (typeof id === "string" && UUID_RE.test(id)) {
				setActiveMissionId(id);
			}
		});
	}, []);

	const handleReleaseControl = async () => {
		setError(null);
		if (!activeMissionId) {
			return;
		}
		if (!UUID_RE.test(activeMissionId)) {
			setError("Invalid mission ID");
			return;
		}
		setResuming(true);
		try {
			const token = await storage.get("token");
			if (!token) {
				setError("Not authenticated");
				return;
			}
			const url = await buildBackendUrl(`/api/v1/dsh/missions/${activeMissionId}/resume`);
			const res = await fetch(url, {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
					Authorization: `Bearer ${token}`,
				},
			});
			if (!res.ok) {
				const body = await res.text().catch(() => "");
				throw new Error(`Resume failed: ${res.status} ${body}`);
			}
			await storage.remove("activeMissionId");
			setActiveMissionId(null);
		} catch (error: unknown) {
			console.error("Failed to release control and resume mission:", error);
			const msg = error instanceof Error ? error.message : "Resume failed";
			setError(msg);
		} finally {
			setResuming(false);
		}
	};

	return (
		<MemoryRouter>
			<div className="p-4 flex flex-col items-center space-y-4 min-w-[240px]">
				<Routing />
				{error && <div className="text-sm text-red-500">{error}</div>}
				{activeMissionId && (
					<div className="flex flex-col items-center space-y-2 w-full">
						<p className="text-sm text-gray-700 text-center">
							Mission {activeMissionId.slice(0, 8)} is awaiting human takeover
						</p>
						<button
							type="button"
							onClick={handleReleaseControl}
							disabled={resuming}
							className="px-4 py-2 bg-red-500 hover:bg-red-600 text-white rounded font-medium disabled:opacity-50 w-full"
						>
							{resuming ? "Resuming..." : "Release Control"}
						</button>
					</div>
				)}
			</div>
			<Toaster />
		</MemoryRouter>
	);
}

export default IndexPopup;

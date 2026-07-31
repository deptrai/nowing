import { RuntimeConfig } from "@/components/providers/runtime-config.server";
import { AdminShell } from "./admin-shell";

interface AdminLayoutProps {
	children: React.ReactNode;
}

export default function AdminLayout({ children }: AdminLayoutProps) {
	return (
		<RuntimeConfig>
			<AdminShell>{children}</AdminShell>
		</RuntimeConfig>
	);
}

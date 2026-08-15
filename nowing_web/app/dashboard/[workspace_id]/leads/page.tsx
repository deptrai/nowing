import { redirect } from "next/navigation";

export default async function LeadsPage(props: { params: Promise<{ workspace_id: string }> }) {
	const { workspace_id } = await props.params;
	redirect(`/dashboard/${workspace_id}/new-chat?mode=leads`);
}

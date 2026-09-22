/**
 * Curated example chat prompts shown on the empty new-chat screen.
 *
 * These mirror the homepage hero's "use case" concept but with runnable chat
 * queries, grouped into a few broad categories. Bracketed slots like `[topic]`
 * are intentional: clicking a prompt prefills the composer so the user can fill
 * them in before sending.
 *
 * Labels and prompts are i18n keys (namespace `newChat`) resolved at render
 * time by the consumer via `useTranslations`.
 *
 * This is a module-scope constant so it is created once, not per render.
 */

export interface ChatExampleCategory {
	/** Stable id used as the Tabs value */
	id: string;
	/** i18n key (namespace `newChat`) for the tab label */
	labelKey: string;
	/** i18n keys (namespace `newChat`) for the runnable example queries */
	promptKeys: string[];
}

export const CHAT_EXAMPLE_CATEGORIES: ChatExampleCategory[] = [
	{
		id: "research",
		labelKey: "cat_research_label",
		promptKeys: [
			"prompt_research_1",
			"prompt_research_2",
			"prompt_research_3",
			"prompt_research_4",
		],
	},
	{
		id: "listen",
		labelKey: "cat_listen_label",
		promptKeys: [
			"prompt_listen_1",
			"prompt_listen_2",
			"prompt_listen_3",
			"prompt_listen_4",
		],
	},
	{
		id: "monitor",
		labelKey: "cat_monitor_label",
		promptKeys: [
			"prompt_monitor_1",
			"prompt_monitor_2",
			"prompt_monitor_3",
			"prompt_monitor_4",
			"prompt_monitor_5",
		],
	},
	{
		id: "automate",
		labelKey: "cat_automate_label",
		promptKeys: [
			"prompt_automate_1",
			"prompt_automate_2",
			"prompt_automate_3",
			"prompt_automate_4",
		],
	},
	{
		id: "tools",
		labelKey: "cat_tools_label",
		promptKeys: [
			"prompt_tools_1",
			"prompt_tools_2",
			"prompt_tools_3",
			"prompt_tools_4",
		],
	},
];

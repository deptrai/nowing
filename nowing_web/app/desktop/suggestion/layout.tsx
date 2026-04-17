import "./suggestion.css";

export const metadata = {
	title: "Nowing Suggestion",
};

export default function SuggestionLayout({ children }: { children: React.ReactNode }) {
	return <div className="suggestion-body">{children}</div>;
}

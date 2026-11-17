declare module "linkedom" {
	export class DOMParser {
		parseFromString(string: string, type: string): Document;
	}
}

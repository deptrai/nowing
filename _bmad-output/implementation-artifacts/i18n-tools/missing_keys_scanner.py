"""Scan repo for t("key") calls whose keys are missing from messages/{en,vi}.json."""
import glob, re, json, sys
from collections import defaultdict

WEB = "/Users/luisphan/Documents/GitHub/nowing/nowing_web"

def resolve_key(d, ns, key):
    curr = d
    for part in (ns.split('.') + key.split('.')):
        if not isinstance(curr, dict) or part not in curr:
            return None
        curr = curr[part]
    return curr if isinstance(curr, str) else None

def scan():
    en = json.load(open(f"{WEB}/messages/en.json"))
    vi = json.load(open(f"{WEB}/messages/vi.json"))
    hook_pattern = re.compile(r'(?:const|let|var)\s+(\w+)\s*=\s*(?:await\s+)?(?:useTranslations|getTranslations)\s*\(\s*["\']([^"\']+)["\']\s*\)')
    call_pattern = re.compile(r'\b(\w+)\s*\(\s*["\']([a-zA-Z0-9_.-]+)["\']')
    files = glob.glob(f"{WEB}/app/**/*.tsx", recursive=True) + glob.glob(f"{WEB}/components/**/*.tsx", recursive=True) + glob.glob(f"{WEB}/features/**/*.tsx", recursive=True)
    missing = defaultdict(set)
    file_map = defaultdict(set)
    for path in sorted(files):
        try: content = open(path, encoding='utf-8').read()
        except Exception: continue
        var_to_ns = {m.group(1): m.group(2) for m in hook_pattern.finditer(content)}
        if not var_to_ns: continue
        for i, line in enumerate(content.split('\n')):
            for m in call_pattern.finditer(line):
                fn, key = m.group(1), m.group(2)
                if fn in var_to_ns:
                    ns = var_to_ns[fn]
                    if resolve_key(en, ns, key) is None or resolve_key(vi, ns, key) is None:
                        missing[ns].add(key)
                        file_map[(ns, key)].add(path.replace(WEB + "/", ""))
    return missing, file_map

if __name__ == "__main__":
    missing, file_map = scan()
    total = sum(len(k) for k in missing.values())
    print(f"MISSING KEYS: {total} unique across {len(missing)} namespaces")
    for ns, keys in sorted(missing.items(), key=lambda x: -len(x[1])):
        print(f"\n'{ns}' ({len(keys)}):")
        for k in sorted(keys):
            print(f"   {k}  <- {sorted(file_map[(ns, k)])[0]}")

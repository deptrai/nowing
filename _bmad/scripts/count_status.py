import re

with open('/Users/luisphan/Documents/GitHub/nowing/_bmad-output/implementation-artifacts/sprint-status.yaml', 'r') as f:
    lines = f.readlines()

epics = 0
in_progress_epics = 0
stories = 0
done_stories = 0

for line in lines:
    line = line.strip()
    if not line or line.startswith('#'):
        continue
    
    parts = line.split(':')
    if len(parts) < 2:
        continue
        
    key = parts[0].strip()
    val = parts[1].strip()
    
    if key.startswith('epic-') and not key.endswith('-retrospective'):
        epics += 1
        if val == 'in-progress':
            in_progress_epics += 1
    elif (re.match(r'^\d+-\d+-', key) or re.match(r'^\d+-UX-', key) or re.match(r'^\d+-DF-', key) or re.match(r'^\d+-\d+[a-zA-Z]*-', key) or re.match(r'^11-\d+-', key) or re.match(r'^10-\d+-', key) or re.match(r'^8-\d+-', key)):
        stories += 1
        if val == 'done':
            done_stories += 1

print(f"epic_count: {epics}")
print(f"story_count: {stories}")
print(f"in_progress_count: {in_progress_epics}")
print(f"done_count: {done_stories}")

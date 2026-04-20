import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
content = open('main.py', encoding='utf-8').read()

# Search for the collector that actually writes snapshot data
# Look for the api/collect or scheduler
patterns = [
    r'def.*collect.*\(',
    r'def.*snapshot.*\(',
    r'def.*daily.*\(',
    r'scheduler',
    r'APScheduler',
    r'cron',
    r'schedule',
    r'BackgroundTasks',
]
lines = content.splitlines()
for i, l in enumerate(lines, start=1):
    for p in patterns:
        if re.search(p, l, re.IGNORECASE):
            print(f'{i}: {l[:110]}')
            break

# Also find the /api/collect or /api/admin/collect endpoint
for i, l in enumerate(lines, start=1):
    if '/collect' in l or '/snapshot/run' in l or '/run_snapshot' in l:
        print(f'ENDPOINT {i}: {l[:110]}')

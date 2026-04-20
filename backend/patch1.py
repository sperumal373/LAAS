import sys

f = open(r'C:\caas-dashboard\frontend\src\MigrationPage.jsx', 'r', encoding='utf-8')
c = f.read()
f.close()

# 1. Add state vars
old1 = '  const [migSchedule, setMigSchedule] = useState("");'
new1 = old1 + '\n  const [migCutoverMode, setMigCutoverMode] = useState("auto");\n  const [migCutoverDatetime, setMigCutoverDatetime] = useState("");'
if 'migCutoverMode' not in c:
    c = c.replace(old1, new1, 1)
    print("1. Added state vars")

# 2. Add to options payload
old2 = 'schedule: migSchedule || null,\n        },\n        notes: migNotes,'
new2 = 'schedule: migSchedule || null,\n          cutover_mode: migCutoverMode,\n          cutover_datetime: migCutoverMode === "scheduled" ? migCutoverDatetime : null,\n        },\n        notes: migNotes,'
if 'cutover_mode' not in c:
    c = c.replace(old2, new2, 1)
    print("2. Added options payload")

f = open(r'C:\caas-dashboard\frontend\src\MigrationPage.jsx', 'w', encoding='utf-8')
f.write(c)
f.close()
print("Done. migCutoverMode count:", c.count('migCutoverMode'))

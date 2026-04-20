p = r'C:\caas-dashboard\backend\hyperv_migrate.py'
t = open(p, 'r', encoding='utf-8').read()
t = t.replace('-VhdType DynamicDisk', '-VhdType Dynamic')
open(p, 'w', encoding='utf-8').write(t)
print(f'PATCHED {t.count("-VhdType Dynamic")} occurrences')

p = r'C:\caas-dashboard\backend\hyperv_migrate.py'
t = open(p, 'r', encoding='utf-8').read()
t = t.replace('-VhdType Dynamic', '-VhdType DynamicallyExpanding')
open(p, 'w', encoding='utf-8').write(t)
print('PATCHED')

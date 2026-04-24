path = r'C:\caas-dashboard\backend\hyperv_client.py'
data = open(path, 'r', encoding='utf-8').read()
data = data.replace('-Authentication Negotiate', '-Authentication Basic')
open(path, 'w', encoding='utf-8').write(data)
print("Fixed: Negotiate -> Basic")

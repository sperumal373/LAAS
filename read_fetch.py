lines = open(r'C:\caas-dashboard\backend\main.py','r',encoding='utf-8').readlines()
for i in range(57, 75):
    print(f"{i+1}: {lines[i]}", end='')

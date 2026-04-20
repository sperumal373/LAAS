f = r'C:\caas-dashboard\frontend\src\App.jsx'
with open(f, encoding='utf-8') as fh:
    content = fh.read()

# The DNS JSX render is at pos 543081
idx = 543081
print(repr(content[idx:idx+300]))

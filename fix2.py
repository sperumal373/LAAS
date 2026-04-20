path = r'C:\caas-dashboard\frontend\src\App.jsx'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()
# Remove lazy and Suspense from React import
content = content.replace(', lazy, Suspense', '', 1)
with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")

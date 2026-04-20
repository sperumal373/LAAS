p = r"C:\caas-dashboard\backend\hyperv_migrate.py"
t = open(p, "r", encoding="utf-8").read()

# Fix the spammy download logging - log only every 200MB
old1 = 'if log_fn and downloaded % (200*1024*1024) < 8*1024*1024:'
new1 = 'if log_fn and (downloaded % (200*1024*1024)) == 0:'

# Replace all occurrences
count = t.count(old1)
t = t.replace(old1, new1)
open(p, "w", encoding="utf-8").write(t)
print(f"PATCHED {count} occurrences")

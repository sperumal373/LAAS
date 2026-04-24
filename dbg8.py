text = open(r"C:\caas-dashboard\frontend\src\MigrationPage.jsx","rb").read().decode("utf-8")

# Find what's actually around the setPtAapInstances call
idx = text.find("setPtAapInstances(_okI)")
print(f"Found at {idx}")
print("CONTEXT:", repr(text[idx-200:idx+200]))
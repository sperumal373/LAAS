path = r"C:\caas-dashboard\frontend\src\MigrationPage.jsx"
data = open(path, "rb").read()

# 1. Add getToken import after the last import line
# Find the line with 'from "./api"' or add after last import
if b'getToken' not in data.split(b'\r\n')[0:15].__repr__().encode():
    # Add import for getToken after the react import
    data = data.replace(
        b'import { useState, useEffect, useRef, useCallback } from "react";',
        b'import { useState, useEffect, useRef, useCallback } from "react";\r\nimport { getToken } from "./api";'
    )
    print("Added getToken import")

# 2. Replace all localStorage.getItem("token") with getToken()
count = data.count(b'localStorage.getItem("token")')
data = data.replace(b'localStorage.getItem("token")', b'getToken()')
print(f"Replaced {count} localStorage.getItem calls")

open(path, "wb").write(data)
print("Saved")

import requests
requests.packages.urllib3.disable_warnings()
r = requests.get("https://localhost/", verify=False)
print("STATUS:", r.status_code)
print("CONTENT-TYPE:", r.headers.get("content-type"))
print("LENGTH:", len(r.text))
print("---FULL HTML---")
print(r.text)
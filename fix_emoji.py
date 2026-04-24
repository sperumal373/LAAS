path = r"C:\caas-dashboard\frontend\src\MigrationPage.jsx"
data = open(path, "rb").read()
# Replace the bad unicode escape with actual emoji bytes
data = data.replace(b'{"\\u{1F517}"}', b'"\xf0\x9f\x94\x97"'.replace(b'"', b''))
# Actually let's just use simple text
data = data.replace(b'<span style={{ fontSize: 12 }}>{\"\\u{1F517}\"}</span> Cluster', b'\xf0\x9f\x94\x97 Cluster')
data = data.replace(b'<span style={{ fontSize: 12 }}>{\"\\u{1F4E6}\"}</span> Standalone', b'\xf0\x9f\x93\xa6 Standalone')
open(path, "wb").write(data)
print("Fixed emoji encoding")

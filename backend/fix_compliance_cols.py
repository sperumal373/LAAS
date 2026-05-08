import psycopg2
conn = psycopg2.connect(host="127.0.0.1", port=5433, dbname="caas_dashboard",
                        user="postgres", password="CaaS@2024#DB")
cur = conn.cursor()
cur.execute("ALTER TABLE compliance_assets ADD COLUMN IF NOT EXISTS extra_data JSONB DEFAULT '{}'")
cur.execute("ALTER TABLE compliance_assets ADD COLUMN IF NOT EXISTS ssh_auth_failed BOOLEAN DEFAULT FALSE")
conn.commit()
print("OK - columns added")

# also check vmware_client functions
import ast, pathlib
src = pathlib.Path("vmware_client.py").read_text(errors="ignore")
tree = ast.parse(src)
funcs = [n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
print("vmware_client functions:", funcs)
conn.close()

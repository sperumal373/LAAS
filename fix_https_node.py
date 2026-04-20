import subprocess, time, sys, os

FRONTEND_DIR = "C:/caas-dashboard/frontend"
CERT_DIR     = "C:/caas-dashboard/certs"
SERVER_IP    = "172.17.70.100"

def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)

def nssm(args):
    r = run("nssm " + args)
    out = (r.stdout + r.stderr).strip()
    if out: print(" ", out)

key_fwd = CERT_DIR + "/caas.key"
crt_fwd = CERT_DIR + "/caas.crt"

js = """const https = require('https');
const http  = require('http');
const fs    = require('fs');
const path  = require('path');

const KEY  = fs.readFileSync('""" + key_fwd + """');
const CERT = fs.readFileSync('""" + crt_fwd + """');
const DIST = path.join(__dirname, 'dist');

const MIME = {
  '.html':'text/html', '.js':'application/javascript', '.css':'text/css',
  '.json':'application/json', '.png':'image/png', '.ico':'image/x-icon',
  '.svg':'image/svg+xml', '.woff2':'font/woff2'
};

function serve(req, res) {
  var fp = path.join(DIST, req.url === '/' ? 'index.html' : req.url);
  try {
    if (!fs.existsSync(fp) || fs.statSync(fp).isDirectory())
      fp = path.join(DIST, 'index.html');
  } catch(e) { fp = path.join(DIST, 'index.html'); }
  var ext = path.extname(fp);
  res.writeHead(200, {'Content-Type': MIME[ext] || 'text/plain'});
  fs.createReadStream(fp).pipe(res);
}

https.createServer({key: KEY, cert: CERT}, serve)
  .listen(443, '0.0.0.0', function() {
    console.log('CaaS HTTPS running');
  });

http.createServer(function(req, res) {
  res.writeHead(301, {Location: 'https://""" + SERVER_IP + """'  + req.url});
  res.end();
}).listen(80, '0.0.0.0', function() {
  console.log('HTTP redirect port 80');
});
"""

cjs_path = FRONTEND_DIR + "/https_server.cjs"
with open(cjs_path, "w") as f:
    f.write(js)
print("[1] Written:", cjs_path)
print(js)

node_path = run("where node").stdout.strip().splitlines()[0]
print("[2] Testing Node...")
proc = subprocess.Popen([node_path, cjs_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
time.sleep(4)
proc.terminate()
out, err = proc.communicate(timeout=3)
stdout = out.decode(errors="replace").strip()
stderr = err.decode(errors="replace").strip()
if stdout: print("   stdout:", stdout)
if stderr:
    print("   FAIL:", stderr)
    sys.exit(1)
print("   OK - no errors")

print("[3] Updating NSSM service...")
nssm("stop \"CaaS-Frontend-HTTPS\"")
time.sleep(2)
nssm("set \"CaaS-Frontend-HTTPS\" AppParameters \"https_server.cjs\"")
nssm("start \"CaaS-Frontend-HTTPS\"")
time.sleep(4)
r = run("nssm status \"CaaS-Frontend-HTTPS\"")
status = (r.stdout + r.stderr).strip()
print("   Status:", status)
if "RUNNING" in status.replace(" ",""):
    print("[OK] https://" + SERVER_IP + " is live!")
else:
    print("[FAIL] still not running")

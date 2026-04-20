// CaaS HTTPS Server + Reverse Proxy — v5.7
// Fixes: proper header forwarding so HTTPS is bit-for-bit identical to HTTP:3000
const https = require('https');
const http  = require('http');
const fs    = require('fs');
const path  = require('path');

const KEY  = fs.readFileSync('C:/caas-dashboard/certs/caas.key');
const CERT = fs.readFileSync('C:/caas-dashboard/certs/caas.crt');
const DIST = path.join(__dirname, 'dist');

const MIME = {
  '.html':'text/html; charset=utf-8','.js':'application/javascript; charset=utf-8','.css':'text/css; charset=utf-8',
  '.json':'application/json; charset=utf-8','.png':'image/png','.ico':'image/x-icon',
  '.svg':'image/svg+xml; charset=utf-8','.woff2':'font/woff2','.woff':'font/woff',
  '.ttf':'font/ttf','.map':'application/json; charset=utf-8'
};

function proxyToBackend(req, res) {
  // Forward all headers but fix host so FastAPI doesn't reject
  var hdrs = Object.assign({}, req.headers);
  hdrs['host'] = '127.0.0.1:8001';
  hdrs['x-forwarded-proto'] = 'https';
  hdrs['x-forwarded-for']   = req.socket.remoteAddress || '';

  var chunks = [];
  req.on('data', function(c){ chunks.push(c); });
  req.on('end', function(){
    var body = Buffer.concat(chunks);
    if (body.length > 0) hdrs['content-length'] = body.length;

    // AI chat needs longer timeout for local LLM inference
    var timeoutMs = req.url.startsWith('/api/ai/chat') ? 180000 : 30000;

    var options = {
      hostname: '127.0.0.1',
      port: 8001,
      path: req.url,
      method: req.method,
      headers: hdrs,
      timeout: timeoutMs
    };

    var proxy = http.request(options, function(backRes) {
      // Pass all backend headers through untouched
      var outHdrs = Object.assign({}, backRes.headers);
      // Remove conflicting transfer-encoding when content-length present
      if (outHdrs['transfer-encoding'] && outHdrs['content-length']) {
        delete outHdrs['transfer-encoding'];
      }
      res.writeHead(backRes.statusCode, outHdrs);
      backRes.pipe(res, { end: true });
    });

    proxy.on('error', function(e) {
      if (!res.headersSent) {
        res.writeHead(502, {'Content-Type':'application/json'});
        res.end(JSON.stringify({detail:'Backend unavailable: ' + e.message}));
      }
    });

    proxy.on('timeout', function() {
      proxy.destroy();
      if (!res.headersSent) {
        res.writeHead(504, {'Content-Type':'application/json'});
        res.end(JSON.stringify({detail:'Request timed out'}));
      }
    });

    if (body.length > 0) proxy.write(body);
    proxy.end();
  });
}

function serveStatic(req, res) {
  var urlPath = req.url.split('?')[0];
  var fp = path.join(DIST, urlPath === '/' ? 'index.html' : urlPath);
  try {
    if (!fs.existsSync(fp) || fs.statSync(fp).isDirectory())
      fp = path.join(DIST, 'index.html');
  } catch(e) { fp = path.join(DIST, 'index.html'); }
  var ext = path.extname(fp);
  var ct  = MIME[ext] || 'text/plain';
  try {
    var data = fs.readFileSync(fp);
    res.writeHead(200, {'Content-Type': ct, 'Content-Length': data.length,
                          'Cache-Control': 'no-cache'});
    res.end(data);
  } catch(e) {
    res.writeHead(404); res.end('Not found');
  }
}

function handler(req, res) {
  var url = req.url;
  if (url.startsWith('/api/') || url.startsWith('/token') || url === '/api') {
    proxyToBackend(req, res);
  } else {
    serveStatic(req, res);
  }
}

https.createServer({key: KEY, cert: CERT}, handler)
  .listen(443, '0.0.0.0', function() {
    console.log('CaaS HTTPS ready: https://caas-dashboard.sdxtest.local');
  });

// HTTP on port 80 - serves app + proxies API (for ngrok/external access)
http.createServer(handler).listen(80, '0.0.0.0', function() {
  console.log('CaaS HTTP ready on port 80 (for tunnel/external access)');
});

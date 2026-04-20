const https = require('https');
const http  = require('http');
const fs    = require('fs');
const path  = require('path');

const KEY  = fs.readFileSync('C:/caas-dashboard/certs/caas.key');
const CERT = fs.readFileSync('C:/caas-dashboard/certs/caas.crt');
const DIST = path.join(__dirname, 'dist');

const MIME = {
  '.html':'text/html; charset=utf-8', '.js':'application/javascript; charset=utf-8', '.css':'text/css; charset=utf-8',
  '.json':'application/json; charset=utf-8', '.png':'image/png', '.ico':'image/x-icon',
  '.svg':'image/svg+xml; charset=utf-8', '.woff2':'font/woff2', '.woff':'font/woff',
  '.ttf':'font/ttf', '.map':'application/json; charset=utf-8'
};

function serve(req, res) {
  var fp = path.join(DIST, req.url === '/' ? 'index.html' : req.url);
  try {
    if (!fs.existsSync(fp) || fs.statSync(fp).isDirectory())
      fp = path.join(DIST, 'index.html');
  } catch(e) { fp = path.join(DIST, 'index.html'); }
  var ext = path.extname(fp);
  res.writeHead(200, {'Content-Type': MIME[ext] || 'text/plain; charset=utf-8', 'Cache-Control': 'no-cache'});
  fs.createReadStream(fp).pipe(res);
}

https.createServer({key:KEY, cert:CERT}, serve).listen(8444, '0.0.0.0', function(){
  console.log('CaaS HTTPS frontend: https://172.17.70.100:8444');
});

http.createServer(function(req,res){
  res.writeHead(301, {Location: 'https://172.17.70.100:8444' + req.url});
  res.end();
}).listen(8080, '0.0.0.0', function(){
  console.log('HTTP->HTTPS redirect on port 80');
});
#!/usr/bin/env node
/*
 * trace-proxy.js — a tiny local MITM proxy for capturing browser network
 * traffic inside Claude Code on the Web (CCotw).
 *
 * WHY THIS EXISTS
 * ---------------
 * In CCotw, outbound HTTPS goes through a policy egress proxy ($HTTPS_PROXY)
 * that RE-TERMINATES TLS. Recent Chromium (>=131, incl. Playwright's bundled
 * build) sends a post-quantum key share (X25519MLKEM768) in its ClientHello.
 * The egress TLS terminator resets that handshake, so every navigation dies
 * with net::ERR_CONNECTION_RESET (netlog: net_error -101 / os_error 104 at the
 * TLS layer). curl and Node tunnel fine because their ClientHello is smaller
 * and carries no PQ share. Chromium flags that supposedly disable PQ
 * (--disable-features=PostQuantumKyber, etc.) did NOT fix it in testing on
 * Chromium 141.
 *
 * THE FIX (and a bonus)
 * ---------------------
 * Interpose our own MITM proxy on localhost:
 *
 *   Chromium --(TLS, self-signed cert, errors ignored)--> THIS PROXY
 *            --(plaintext, we read/log it)-->
 *            --(CONNECT tunnel via $HTTPS_PROXY, Node TLS)--> real origin
 *
 * Chromium now does TLS to US (localhost, we accept its PQ hello happily), and
 * WE re-originate each request outward through the agent proxy exactly the way
 * curl/Node do (which works). Side effect: because we terminate TLS, we see
 * every request in plaintext — host, method, path, and (optionally) bodies.
 * That is the network trace.
 *
 * USAGE
 *   node trace-proxy.js            # prints MITM_PORT=<n>, writes trace.json
 *   TRACE_DIR=/path node trace-proxy.js
 *   CAPTURE_BODIES=1 node trace-proxy.js   # also save non-GET bodies to bodies/
 *
 * Point Playwright at it (see run-trace.js for a full driver):
 *   chromium.launch({ proxy: { server: 'http://127.0.0.1:'+PORT },
 *                     args: ['--ignore-certificate-errors','--no-sandbox',
 *                            '--disable-quic','--disable-background-networking',
 *                            '--disable-component-update'] })
 *
 * REQUIREMENTS
 *   - $HTTPS_PROXY set (CCotw always sets it)
 *   - CA bundle at $CCR_CA or /root/.ccr/ca-bundle.crt (to verify origins)
 *   - a self-signed cert/key pair; generate once with:
 *       openssl req -x509 -newkey rsa:2048 -keyout mitm.key -out mitm.crt \
 *         -days 2 -nodes -subj "/CN=trace-proxy" \
 *         -addext "subjectAltName=DNS:localhost,DNS:*.com,DNS:*.net,DNS:*.io"
 *     (SAN barely matters — Chromium runs with --ignore-certificate-errors.)
 *
 * Read-only capture tool. It records what the browser was going to send anyway;
 * it does not modify traffic. Use it to audit your own testing, not to intercept
 * anyone else's session.
 */
const net = require('net'), tls = require('tls'), http = require('http'),
      fs = require('fs'), url = require('url'), path = require('path');

const DIR = process.env.TRACE_DIR || process.cwd();
const CA_PATH = process.env.CCR_CA || '/root/.ccr/ca-bundle.crt';
const CAPTURE_BODIES = !!process.env.CAPTURE_BODIES;
const BODY_HOST_RE = new RegExp(process.env.BODY_HOSTS || 'filestack|amazonaws|\\.s3|upload|spreedly');

const KEY = fs.readFileSync(process.env.MITM_KEY || path.join(DIR, 'mitm.key'));
const CRT = fs.readFileSync(process.env.MITM_CRT || path.join(DIR, 'mitm.crt'));
const CA = fs.readFileSync(CA_PATH);
const AP = new url.URL(process.env.HTTPS_PROXY);
if (CAPTURE_BODIES) fs.mkdirSync(path.join(DIR, 'bodies'), { recursive: true });

const log = [];
let seq = 0;
const dump = () => { try { fs.writeFileSync(path.join(DIR, 'trace.json'), JSON.stringify(log)); } catch (e) {} };

// Open a TLS socket to `host:port` through the agent proxy (the curl/Node path
// that the egress terminator accepts).
function originTLS(host, port, cb) {
  const s = net.connect(+AP.port, AP.hostname, () => {
    s.write(`CONNECT ${host}:${port} HTTP/1.1\r\nHost: ${host}:${port}\r\n\r\n`);
  });
  let hdr = '', done = false;
  s.on('data', function onData(d) {
    if (done) return;
    hdr += d.toString('latin1');
    if (hdr.indexOf('\r\n\r\n') < 0) return;
    done = true; s.removeListener('data', onData);
    if (!/^HTTP\/1\.[01] 200/.test(hdr)) { cb(new Error('proxy CONNECT: ' + hdr.split('\r\n')[0])); return; }
    const t = tls.connect({ socket: s, servername: host, ca: CA, ALPNProtocols: ['http/1.1'] }, () => cb(null, t));
    t.on('error', e => cb(e));
  });
  s.on('error', e => { if (!done) cb(e); });
}

// HTTP server that receives DECRYPTED requests from Chromium and forwards them.
const server = http.createServer((req, res) => {
  const host = req.socket.__host, port = req.socket.__port || 443;
  const rec = { host, path: req.url.slice(0, 80), method: req.method };
  log.push(rec);
  const capture = CAPTURE_BODIES && BODY_HOST_RE.test(host) && req.method !== 'GET';
  let chunks = [];
  if (capture) req.on('data', c => { if (chunks.reduce((a, b) => a + b.length, 0) < 8e6) chunks.push(c); });
  originTLS(host, port, (err, ot) => {
    if (err) { res.writeHead(502); res.end('trace-proxy: ' + err.message); return; }
    const headers = Object.assign({}, req.headers);
    headers.host = host; delete headers['proxy-connection']; headers.connection = 'close';
    const preq = http.request({ createConnection: () => ot, host, port, method: req.method, path: req.url, headers },
      pres => { res.writeHead(pres.statusCode, pres.headers); pres.pipe(res); });
    preq.on('error', e => { if (!res.headersSent) res.writeHead(502); res.end('up: ' + e.message); });
    if (capture) req.on('end', () => {
      try {
        const b = Buffer.concat(chunks);
        const fn = path.join(DIR, 'bodies', `${++seq}_${host.replace(/[^a-z0-9]/gi, '_')}.bin`);
        fs.writeFileSync(fn, b); rec.savedBody = fn; rec.bodyLen = b.length;
      } catch (e) {}
    });
    req.pipe(preq);
  });
});
server.on('clientError', (e, sock) => { try { sock.destroy(); } catch (_) {} });

// Raw TCP proxy: accept CONNECT, terminate TLS with our cert, hand the
// decrypted duplex to `server` as if it were an ordinary connection.
const proxy = net.createServer(sock => {
  sock.once('data', d => {
    const m = d.toString('latin1').split('\r\n')[0].match(/^CONNECT ([^:]+):(\d+)/);
    if (!m) { sock.write('HTTP/1.1 405\r\n\r\n'); sock.end(); return; }
    sock.write('HTTP/1.1 200 Connection Established\r\n\r\n');
    const tsock = new tls.TLSSocket(sock, { isServer: true, key: KEY, cert: CRT, ALPNProtocols: ['http/1.1'] });
    tsock.__host = m[1]; tsock.__port = +m[2];
    tsock.on('error', () => {});
    server.emit('connection', tsock);
  });
  sock.on('error', () => {});
});
proxy.listen(0, '127.0.0.1', () => {
  const port = proxy.address().port;
  fs.writeFileSync(path.join(DIR, 'mitm.port'), String(port));
  console.log('MITM_PORT=' + port);
});
setInterval(dump, 500);
process.on('SIGTERM', () => { dump(); process.exit(0); });
process.on('SIGINT', () => { dump(); process.exit(0); });

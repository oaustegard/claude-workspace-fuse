#!/usr/bin/env node
/*
 * run-trace.js — example Playwright driver that loads a URL through the
 * trace-proxy and prints every host the page contacted.
 *
 *   MITM_PORT=$(cat trace.dir/mitm.port) node run-trace.js <url>
 * or, simplest, pass the port explicitly:
 *   node run-trace.js <url> <mitm_port>
 *
 * Adapt the body: fill form fields, attach files via page.on('filechooser'),
 * etc. The trace-proxy logs everything server-side to trace.json regardless of
 * what the browser-side listeners here capture.
 */
const PW = '/opt/node22/lib/node_modules/playwright'; // Playwright's own install in CCotw
const { chromium } = require(PW);

const URL_ARG = process.argv[2] || 'https://example.com/';
const PORT = process.argv[3] || process.env.MITM_PORT;
if (!PORT) { console.error('need MITM_PORT (arg 3 or env)'); process.exit(1); }

(async () => {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium',      // CCotw's pre-installed Chromium
    proxy: { server: 'http://127.0.0.1:' + PORT },     // <-- the trace-proxy, NOT $HTTPS_PROXY
    args: [
      '--ignore-certificate-errors',   // trust the trace-proxy's self-signed cert
      '--no-sandbox',
      '--disable-quic',                // force TCP so everything goes through the proxy
      '--disable-background-networking',
      '--disable-component-update',
    ],
  });
  const ctx = await browser.newContext({ ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  const hosts = {};
  page.on('request', r => { try { const h = new URL(r.url()).host; hosts[h] = (hosts[h] || 0) + 1; } catch (e) {} });

  const resp = await page.goto(URL_ARG, { waitUntil: 'networkidle', timeout: 60000 })
    .catch(e => ({ err: e.message.split('\n')[0] }));
  console.log('NAV:', resp && resp.err ? 'ERR ' + resp.err : 'status ' + resp.status());
  await page.waitForTimeout(6000);
  console.log('TITLE:', await page.title());
  console.log('=== HOSTS CONTACTED (browser-side) ===');
  Object.entries(hosts).sort((a, b) => b[1] - a[1]).forEach(([h, c]) => console.log(String(c).padStart(4), h));
  await browser.close();
})();

#!/usr/bin/env python3
"""Real-browser checks; optional private stock input enables Python/JS parity.

Install playwright, then its Chromium browser, or use installed Google Chrome.
No firmware is committed, uploaded, or retained by this test.
"""
import argparse
import base64
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'firmware_builder/direct'))
from core import sha
from playwright.sync_api import sync_playwright, expect


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--factory', type=Path)
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    handler = functools.partial(QuietHandler, directory=ROOT / 'website')
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}'
    receipt = {'status': 'PASS', 'synthetic_checks': [], 'private_parity': 'NOT RUN'}
    try:
        with sync_playwright() as p, tempfile.TemporaryDirectory(prefix='px-re-qa-') as temp:
            chrome = Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
            options = {'executable_path': str(chrome)} if chrome.exists() else {}
            browser = p.chromium.launch(**options)
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()
            errors, requests = [], []
            page.on('pageerror', lambda error: errors.append(str(error)))
            context.on('request', lambda request: requests.append((request.method, request.url)))
            page.goto(base + '/index.html')
            expect(page.locator('#firmware-create')).to_be_disabled()
            receipt['browser'] = browser.version
            # Parser fixtures, corruption, exact-size gate and recipe tampering.
            receipt['synthetic_checks'] = page.evaluate('''async () => {
              const passed = [];
              function check(ok, name) { if (!ok) throw new Error(name); passed.push(name); }
              async function rejects(fn, name) {
                let failed = false; try { await fn(); } catch { failed = true; }
                check(failed, name);
              }
              const records = [1,2,3].map(kind => {
                const header = new Uint8Array([kind,123,2,2,2,0,0,122,0,0,0,2]);
                const payload = new Uint8Array([kind,0]);
                return {kind, header, payload, trailer: new Uint8Array(kind < 3 ? [kind,0] : [48,48])};
              });
              const bytes = PX.serialize(records);
              check(PX.parse(bytes).length === 3, 'container round trip');
              for (const [offset, name] of [[0,'framing'],[1,'record header'],[13,'record checksum'],[47,'PIC trailer']]) {
                const bad = bytes.slice(); bad[offset] ^= 1;
                await rejects(() => PX.parse(bad), 'reject ' + name);
              }
              await rejects(() => PX.parse(bytes.slice(0,-1)), 'reject truncated container');
              await rejects(() => PX.sum16(new Uint8Array(1)), 'reject odd checksum payload');
              await rejects(() => PX.validateInput(new Uint8Array(1)), 'reject wrong file size');
              await rejects(() => PX.validateInput(new Uint8Array(PX.FACTORY_SIZE)), 'reject wrong stock hash');
              await rejects(() => PX.elfLayout(new Uint8Array(64)), 'reject invalid ELF');
              await PX.loadRecipe(); passed.push('recipe integrity pin');
              const saved = PX_RECIPE_JSON; PX_RECIPE_JSON += ' ';
              await rejects(() => PX.loadRecipe(), 'reject recipe tampering'); PX_RECIPE_JSON = saved;
              const input = new Uint8Array([1,2,3,4]), guard = await PX.sha(input);
              const write = {offset:0,size:4,owner:'test',source:'fixture',factory_sha256:guard,
                generated_sha256:guard,ops:[['copy',0,4]]};
              const spec = {factory_size:4,factory_sha256:guard,final_size:4,writes:[write]};
              check((await PX.component(input,input,spec))[0] === 1, 'guarded factory copy');
              await rejects(() => PX.component(input,input,{...spec,writes:[write,write]}), 'reject overlapping owners');
              await rejects(() => PX.component(input,input,{...spec,final_size:5}), 'reject unowned extension');
              await rejects(() => PX.component(input,input,{...spec,writes:[{...write,factory_sha256:'bad'}]}), 'reject write guard');
              await rejects(() => PX.component(input,input,{...spec,writes:[{...write,generated_sha256:'bad'}]}), 'reject generated write hash');
              await rejects(() => PX.component(input,input,{...spec,writes:[{...write,ops:[['copy',2,4]]}]}), 'reject copy bounds');
              return passed;
            }''')
            assert page.locator('#firmware-create').is_disabled()
            page.locator('#firmware-file').set_input_files({'name': 'bad.bin', 'mimeType': 'application/octet-stream', 'buffer': b'bad'})
            expect(page.locator('#firmware-status')).to_contain_text('Wrong file size')
            assert page.locator('#firmware-create').is_disabled()
            assert page.locator('#downloads a').count() == 0
            # Renaming a same-size arbitrary input must still fail in the UI.
            page.locator('#firmware-file').set_input_files({'name':'PxUpdate_V2.2.2.0.0.bin', 'mimeType':'application/octet-stream', 'buffer':bytes(3099064)})
            expect(page.locator('#firmware-status')).to_contain_text('SHA-256 mismatch')
            assert page.locator('#firmware-create').is_disabled()
            assert page.locator('#downloads a').count() == 0
            page.set_viewport_size({'width':375,'height':812})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            receipt['synthetic_checks'] += ['UI rejects invalid inputs without downloads', '375px layout has no horizontal overflow']
            if args.factory:
                from build import build
                stock = args.factory.read_bytes()
                reference, report = build(stock, ROOT / 'firmware_builder/direct/cache')
                before = sha(stock)
                page.locator('#firmware-file').set_input_files(args.factory)
                expect(page.locator('#firmware-create')).to_be_enabled()
                page.locator('#firmware-create').click()
                expect(page.locator('#downloads a')).to_have_count(2, timeout=60000)
                with page.expect_download() as download:
                    page.locator('#downloads a').nth(0).click()
                output = download.value
                assert output.suggested_filename == 'PxUpdate_V2.2.2.2.2.bin'
                saved = Path(temp) / output.suggested_filename
                output.save_as(saved)
                assert saved.read_bytes() == reference, 'Browser/Python output differs'
                with page.expect_download() as download:
                    page.locator('#downloads a').nth(1).click()
                report_path = Path(temp) / 'report.json'
                download.value.save_as(report_path)
                js_report = json.loads(report_path.read_text())
                assert js_report['checks'] == report['checks']
                assert js_report['sha256'] == sha(reference)
                # Clear stale successful output on a new invalid selection.
                page.locator('#firmware-file').set_input_files({'name':'bad.bin','mimeType':'application/octet-stream','buffer':b'bad'})
                assert page.locator('#downloads a').count() == 0
                # Exercise independent final validation against a corrupted output.
                encoded = base64.b64encode(reference).decode()
                stock64 = base64.b64encode(stock).decode()
                assert page.evaluate('''async ([stock64, out64]) => {
                  const decode = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));
                  const out = decode(out64); out[100] ^= 1;
                  try { await PX.validateOutput(decode(stock64), out, await PX.loadRecipe()); return false; }
                  catch { return true; }
                }''', [stock64, encoded])
                # file:// fallback works without a server, worker, or connection.
                offline = browser.new_context(accept_downloads=True, offline=True)
                local = offline.new_page()
                local.goto((ROOT / 'website/index.html').as_uri())
                local.locator('#firmware-file').set_input_files(args.factory)
                expect(local.locator('#firmware-create')).to_be_enabled()
                local.locator('#firmware-create').click()
                expect(local.locator('#downloads a')).to_have_count(2, timeout=60000)
                with local.expect_download() as download:
                    local.locator('#downloads a').nth(0).click()
                download.value.save_as(saved)
                assert saved.read_bytes() == reference, 'Offline browser/Python output differs'
                offline.close()
                assert sha(args.factory.read_bytes()) == before
                receipt.update(private_parity='PASS', byte_identical=True, offline_byte_identical=True,
                               factory_unchanged=True, final_size=len(reference), final_sha256=sha(reference),
                               checks=js_report['checks'])
            allowed = {'/index.html','/style.css','/recipe.js','/recipe-pin.js','/patcher.js','/ui.js','/worker.js','/favicon.ico'}
            assert all(method == 'GET' and url.startswith(base) and url[len(base):] in allowed for method,url in requests), requests
            assert not errors, errors
            receipt['network_check'] = 'PASS: only local static GET requests; no uploads or external requests'
            context.close()
            browser.close()
    finally:
        server.shutdown()
    if args.receipt:
        args.receipt.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()

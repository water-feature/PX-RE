// MIT. Local file selection, verification and explicit Blob downloads only.
'use strict';
(() => {
  const input = document.getElementById('firmware-file'), button = document.getElementById('firmware-create');
  const status = document.getElementById('firmware-status'), downloads = document.getElementById('downloads');
  let generation = 0, selected = null, worker = null, urls = [];
  function clear() {
    for (const url of urls) URL.revokeObjectURL(url);
    urls = []; downloads.replaceChildren();
  }
  function link(bytes, filename, label, type) {
    const url = URL.createObjectURL(new Blob([bytes], {type})); urls.push(url);
    const p = document.createElement('p'), a = document.createElement('a');
    a.href = url; a.download = filename; a.textContent = label; p.append(a); downloads.append(p);
  }
  input.addEventListener('change', async () => {
    const current = ++generation; selected = null; button.disabled = true; clear();
    if (worker) { worker.terminate(); worker = null; }
    const file = input.files[0];
    if (!file) { status.textContent = 'No file selected.'; return; }
    if (file.size !== PX.FACTORY_SIZE) {
      status.textContent = 'Wrong file size. Select the original PxUpdate_V2.2.2.0.0.bin (3,099,064 bytes).'; return;
    }
    status.textContent = 'Checking stock firmware SHA-256 and container…';
    try {
      const bytes = new Uint8Array(await file.arrayBuffer());
      await PX.validateInput(bytes);
      if (current !== generation) return;
      selected = bytes; button.disabled = false;
      status.textContent = 'Verified stock 2.2.2.0.0 firmware. Ready to patch.';
    } catch (error) { if (current === generation) status.textContent = 'Cannot patch: ' + error.message; }
  });
  button.addEventListener('click', async () => {
    if (!selected) return;
    button.disabled = true; input.disabled = true; clear();
    const update = text => { status.textContent = text; };
    try {
      let result;
      if (location.protocol !== 'file:' && typeof Worker !== 'undefined') {
        result = await new Promise((resolve, reject) => {
          worker = new Worker('worker.js');
          worker.onmessage = ({data}) => {
            if (data.progress) update(data.progress);
            else if (data.error) reject(new Error(data.error));
            else resolve({output: new Uint8Array(data.output), report: data.report});
          };
          worker.onerror = () => reject(new Error('The patch worker could not start. Reload the page or use the offline copy.'));
          const copy = selected.slice(); worker.postMessage(copy.buffer, [copy.buffer]);
        });
      } else result = await PX.build(selected, update);
      link(result.output, 'PxUpdate_V2.2.2.2.2.bin', 'Download PxUpdate_V2.2.2.2.2.bin', 'application/octet-stream');
      link(JSON.stringify(result.report, null, 2) + '\n', 'PxUpdate_V2.2.2.2.2.bin.report.json', 'Download verification report', 'application/json');
      status.textContent = 'Verified patched firmware: 3,187,784 bytes. SHA-256: ' + result.report.sha256;
    } catch (error) { clear(); status.textContent = 'Cannot create firmware: ' + error.message; }
    finally {
      if (worker) { worker.terminate(); worker = null; }
      input.disabled = false; button.disabled = !selected;
    }
  });
  window.addEventListener('pagehide', () => { clear(); if (worker) worker.terminate(); });
})();

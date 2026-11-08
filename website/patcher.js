// MIT — port of the direct builder's byte guards, container and final checks.
// See ../LICENSE, ../NOTICE and README.md. No network or filesystem APIs.
'use strict';
globalThis.PX = (() => {
  const FACTORY_SHA256 = 'a4b304b3bb48ca933ae63c99c0098698c497ebfc7c38ab2a823b5e0df4919fa9';
  const FINAL_SHA256 = '488444589607a1b4e793a8d8f79a67c5bd50773b722c302e6d80bc1db77b4b7c';
  const FACTORY_SIZE = 3099064, FINAL_SIZE = 3187784;
  function require(ok, message) { if (!ok) throw new Error(message); }
  const equal = (a, b) => a.length === b.length && a.every((v, i) => v === b[i]);
  const view = a => new DataView(a.buffer, a.byteOffset, a.byteLength);
  const integer = n => Number.isSafeInteger(n) && n >= 0;
  function bounds(a, start, size) {
    require(integer(start) && integer(size) && start + size <= a.length, 'Byte range exceeds input');
  }
  async function sha(a) {
    require(globalThis.crypto?.subtle, 'SHA-256 is unavailable. Use HTTPS or localhost in a current browser.');
    return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', a)), b => b.toString(16).padStart(2, '0')).join('');
  }
  function sum16(a) {
    require(a.length % 2 === 0, 'Odd payload length');
    const v = view(a); let sum = 0;
    for (let i = 0; i < a.length; i += 2) sum = (sum + v.getUint16(i, true)) & 65535;
    return sum;
  }
  function parse(a) {
    require(a[0] === 0xf0 && a[a.length - 1] === 0xf7, 'Invalid SysEx framing');
    let cursor = 1; const records = [];
    for (const kind of [1, 2, 3]) {
      bounds(a, cursor, 12);
      const header = a.slice(cursor, cursor + 12);
      require(header[0] === kind && header[1] === 123 && header[7] === 122, 'Invalid record header');
      const size = view(header).getUint32(8, false), end = cursor + 12 + size;
      require(end + 2 <= a.length - 1, 'Truncated record');
      const payload = a.slice(cursor + 12, end), trailer = a.slice(end, end + 2);
      if (kind < 3) require(view(trailer).getUint16(0, true) === sum16(payload), 'Record checksum mismatch');
      else require(trailer[0] === 48 && trailer[1] === 48, 'Unexpected PIC legacy trailer');
      records.push({kind, header, payload, trailer}); cursor = end + 2;
    }
    require(cursor === a.length - 1, 'Unexpected trailing bytes');
    return records;
  }
  function serialize(records) {
    const out = new Uint8Array(2 + records.reduce((n, r) => n + 14 + r.payload.length, 0));
    out[0] = 0xf0; let cursor = 1;
    for (const r of records) {
      require(r.header.length === 12 && r.trailer.length === 2, 'Invalid record field length');
      require(view(r.header).getUint32(8, false) === r.payload.length, 'Header payload length mismatch');
      for (const part of [r.header, r.payload, r.trailer]) { out.set(part, cursor); cursor += part.length; }
    }
    out[cursor] = 0xf7; return out;
  }
  function elfLayout(a) {
    require(equal(a.slice(0, 6), new Uint8Array([127, 69, 76, 70, 2, 1])), 'Application is not little-endian ELF64');
    bounds(a, 0, 64); const v = view(a);
    function u64(at) { const n = Number(v.getBigUint64(at, true)); require(integer(n), 'Unsafe ELF integer'); return n; }
    const shoff = u64(40), phoff = u64(32), shsize = v.getUint16(58, true), shcount = v.getUint16(60, true);
    const namesIndex = v.getUint16(62, true), phsize = v.getUint16(54, true), phcount = v.getUint16(56, true);
    require(shsize === 64 && phsize === 56, 'Unexpected ELF descriptor sizes');
    bounds(a, shoff, shcount * shsize); bounds(a, phoff, phcount * phsize);
    require(namesIndex < shcount, 'Invalid section name index');
    const rows = [];
    for (let i = 0; i < shcount; i++) {
      const at = shoff + i * 64;
      rows.push({nameIndex: v.getUint32(at, true), type: v.getUint32(at + 4, true),
        address: u64(at + 16), offset: u64(at + 24), size: u64(at + 32)});
    }
    const names = rows[namesIndex]; bounds(a, names.offset, names.size);
    const strings = a.slice(names.offset, names.offset + names.size), sections = Object.create(null);
    for (const row of rows) {
      require(row.nameIndex < strings.length, 'Invalid section name offset');
      let end = row.nameIndex;
      while (end < strings.length && strings[end]) { require(strings[end] < 128, 'Non-ASCII ELF name'); end++; }
      require(end < strings.length, 'Unterminated ELF section name');
      const name = String.fromCharCode(...strings.slice(row.nameIndex, end));
      if (row.type !== 8) bounds(a, row.offset, row.size);
      sections[name] = row;
    }
    const programs = [];
    for (let i = 0; i < phcount; i++) {
      const at = phoff + i * 56;
      const p = {type: v.getUint32(at, true), flags: v.getUint32(at + 4, true),
        offset: u64(at + 8), address: u64(at + 16), fileSize: u64(at + 32), memorySize: u64(at + 40)};
      bounds(a, p.offset, p.fileSize); programs.push(p);
    }
    return {sections, programs};
  }
  async function loadRecipe() {
    require(typeof globalThis.PX_RECIPE_JSON === 'string', 'Patch recipe is missing');
    require(await sha(new TextEncoder().encode(PX_RECIPE_JSON)) === globalThis.PX_RECIPE_SHA256, 'Patch recipe integrity mismatch');
    const r = JSON.parse(PX_RECIPE_JSON);
    require(r.format === 1 && r.factory_sha256 === FACTORY_SHA256 && r.final_sha256 === FINAL_SHA256 &&
      r.factory_size === FACTORY_SIZE && r.final_size === FINAL_SIZE, 'Unsupported patch recipe identity');
    require(r.components.length === 2 && r.components[0].name === 'QNX' && r.components[1].name === 'PIC', 'Invalid recipe components');
    return r;
  }
  async function validateInput(factory) {
    require(factory instanceof Uint8Array, 'Input must be bytes');
    require(factory.length === FACTORY_SIZE, 'Wrong file size. Select the original PxUpdate_V2.2.2.0.0.bin (3,099,064 bytes).');
    require(await sha(factory) === FACTORY_SHA256, 'Factory SHA-256 mismatch. Only the exact stock 2.2.2.0.0 firmware is accepted.');
    const old = parse(factory);
    require(equal(serialize(old), factory), 'Factory container round trip mismatch');
    return old;
  }
  async function component(before, factory, spec) {
    require(before.length === spec.factory_size && await sha(before) === spec.factory_sha256, 'Component factory identity mismatch');
    require(integer(spec.final_size) && spec.final_size >= before.length && spec.final_size <= FINAL_SIZE, 'Invalid component extent');
    const result = new Uint8Array(spec.final_size); result.set(before);
    const owned = new Uint8Array(result.length);
    for (const w of spec.writes) {
      require(integer(w.offset) && integer(w.size) && w.size > 0 && w.owner && w.source, 'Invalid write ownership');
      bounds(result, w.offset, w.size);
      require(!owned.subarray(w.offset, w.offset + w.size).some(Boolean), 'Overlapping final owners');
      require(await sha(before.slice(w.offset, Math.min(w.offset + w.size, before.length))) === w.factory_sha256, 'Factory write guard mismatch');
      const data = new Uint8Array(w.size); let cursor = 0;
      for (const op of w.ops) {
        let part;
        if (op[0] === 'copy') { bounds(factory, op[1], op[2]); part = factory.subarray(op[1], op[1] + op[2]); }
        else if (op[0] === 'zero') {
          require(integer(op[1]) && op[1] <= w.size - cursor, 'Invalid zero run'); part = new Uint8Array(op[1]);
        } else if (op[0] === 'literal') part = Uint8Array.from(atob(op[1]), c => c.charCodeAt(0));
        else throw new Error('Unknown recipe operation');
        require(cursor + part.length <= data.length, 'Recipe write overflow'); data.set(part, cursor); cursor += part.length;
      }
      require(cursor === w.size && await sha(data) === w.generated_sha256, 'Generated write identity mismatch');
      result.set(data, w.offset); owned.fill(1, w.offset, w.offset + w.size);
    }
    for (let i = 0; i < result.length; i++)
      require(owned[i] || (i < before.length && result[i] === before[i]), 'Unowned changed byte or extension');
    return result;
  }
  async function validateOutput(factory, output, recipe) {
    const old = parse(factory), records = parse(output);
    require(equal(serialize([old[1]]), serialize([records[1]])), 'FPGA record changed');
    for (const [index, spec] of [[0, recipe.components[0]], [2, recipe.components[1]]]) {
      const before = old[index].payload, after = records[index].payload, owned = new Uint8Array(after.length);
      for (const w of spec.writes) {
        bounds(after, w.offset, w.size);
        require(!owned.subarray(w.offset, w.offset + w.size).some(Boolean), 'Invalid final ownership receipt');
        require(await sha(before.slice(w.offset, w.offset + w.size)) === w.factory_sha256 &&
          await sha(after.slice(w.offset, w.offset + w.size)) === w.generated_sha256, 'Ownership receipt hash mismatch');
        owned.fill(1, w.offset, w.offset + w.size);
      }
      for (let i = 0; i < after.length; i++) require(owned[i] || (i < before.length && after[i] === before[i]), 'Unowned changed byte');
      require(equal(records[index].header.slice(2, 7), new Uint8Array([2, 2, 2, 2, 2])), 'Wrong final revision header');
    }
    const app = records[0].payload, layout = elfLayout(app), allocated = [];
    for (const p of layout.programs) if (p.type === 1) require(p.fileSize <= p.memorySize, 'ELF load size exceeds memory size');
    for (const name of ['.b5.text', '.b5.eh_frame', '.b8.text', '.b8.eh_frame', '.b15_text', '.b15_eh_frame']) {
      const s = layout.sections[name]; require(s && s.type !== 8, 'Missing added ELF section');
      const lo = s.address, hi = lo + s.size;
      require(!allocated.some(([a, b]) => lo < b && a < hi), 'Added ELF sections overlap'); allocated.push([lo, hi]);
      require(layout.programs.some(p => p.type === 1 && (p.flags & 4) && p.address <= lo && hi <= p.address + p.fileSize), 'Added ELF section is not readable');
    }
    const h = layout.sections['.eh_frame_hdr']; require(h, 'Missing unwind index');
    bounds(app, h.offset, h.size); const hdr = app.subarray(h.offset, h.offset + h.size), hv = view(hdr), av = view(app);
    require(equal(hdr.slice(0, 4), new Uint8Array([1, 27, 3, 59])), 'Unsupported unwind index encoding');
    bounds(hdr, 0, 12); const count = hv.getUint32(8, true);
    require(count === 910 && hdr.length === 12 + count * 8, 'Final unwind index mismatch');
    let previous = [-1, -1];
    for (let i = 0; i < count; i++) {
      const pc = h.address + hv.getInt32(12 + i * 8, true), fde = h.address + hv.getInt32(16 + i * 8, true);
      require(pc > previous[0] || (pc === previous[0] && fde >= previous[1]), 'Unsorted unwind index'); previous = [pc, fde];
      bounds(app, fde, 16);
      const length = av.getUint32(fde, true), cie = av.getUint32(fde + 4, true), delta = av.getInt32(fde + 8, true), extent = av.getUint32(fde + 12, true);
      require(cie && length >= 12 && fde + 4 + length <= app.length && fde + 8 + delta === pc, 'Indexed FDE target or extent mismatch');
      require(layout.programs.some(p => p.type === 1 && (p.flags & 1) && p.address <= pc && pc + extent <= p.address + p.fileSize), 'FDE code is outside executable mapping');
    }
    require(av.getUint32(0x1f4e3, true) === 0x40139222 && app[0x250e2] === 2 && app[0x250ef] === 2, 'DSP/updater revision mismatch');
    require(output.length === FINAL_SIZE && await sha(output) === FINAL_SHA256, 'Final update identity mismatch');
    return {factory_identity: 'PASS', record_checksums: 'PASS', final_identity: 'PASS', FPGA_unchanged: 'PASS',
      changed_byte_ownership: 'PASS', ELF_added_sections_and_loads: 'PASS', indexed_FDEs: count, revision_headers_and_gates: 'PASS'};
  }
  async function build(input, progress = () => {}) {
    // Snapshot so callers cannot change bytes during asynchronous verification.
    const factory = new Uint8Array(input); progress('Checking stock firmware…');
    const old = await validateInput(factory), recipe = await loadRecipe();
    progress('Applying guarded QNX and PIC writes…');
    const app = await component(old[0].payload, factory, recipe.components[0]);
    const dsp = await component(old[2].payload, factory, recipe.components[1]);
    function record(original, payload) {
      const header = original.header.slice(); header.set([2, 2, 2, 2, 2], 2); view(header).setUint32(8, payload.length, false);
      const trailer = original.trailer.slice(); if (original.kind === 1) view(trailer).setUint16(0, sum16(payload), true);
      return {...original, header, payload, trailer};
    }
    const output = serialize([record(old[0], app), old[1], record(old[2], dsp)]);
    progress('Verifying checksums, ownership, ELF and all 910 unwind entries…');
    const checks = await validateOutput(factory, output, recipe);
    return {output, report: {status: 'PASS', size: output.length, sha256: FINAL_SHA256, checks,
      recipe_sha256: globalThis.PX_RECIPE_SHA256, engine: 'JavaScript guarded write recipe', hardware: 'NOT VERIFIED'}};
  }
  return {FACTORY_SHA256, FINAL_SHA256, FACTORY_SIZE, FINAL_SIZE, sha, sum16, parse, serialize, elfLayout,
    loadRecipe, validateInput, component, validateOutput, build};
})();

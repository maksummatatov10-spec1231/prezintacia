#!/usr/bin/env node
// LibreOffice (WASM) bridge for pptkit.
//   node office.mjs images --input deck.pptx --outdir DIR [--dpi 144] [--pages 1,3] [--fonts d1:d2]
//   node office.mjs pdf    --input deck.pptx --output deck.pdf [--fonts d1:d2]
//   node office.mjs convert --input deck.pptx --output deck.odp|.docx|.png ...
// Prints ONE JSON line with the result (or {"error":...}) on stdout.
import path from 'node:path';
import { createConverter } from '@deepseek-ai/libreoffice-kit';

const argv = process.argv.slice(2);
const cmd = argv[0];
const opt = {};
for (let i = 1; i < argv.length; i += 2) opt[argv[i].replace(/^--/, '')] = argv[i + 1];

const FALLBACKS = [
  ['Arial', 'Arimo', 'Liberation Sans', 'DejaVu Sans'], ['Helvetica', 'Arimo'], ['Calibri', 'Carlito'],
  ['Calibri Light', 'Carlito'], ['Cambria', 'Caladea'], ['Times New Roman', 'Tinos'], ['Courier New', 'Cousine'],
  ['Georgia', 'Gelasio'], ['Segoe UI', 'Open Sans'], ['Verdana', 'DejaVu Sans'], ['Tahoma', 'DejaVu Sans'],
  ['Comic Sans MS', 'Comic Neue'], ['Century Gothic', 'Didact Gothic'], ['Trebuchet MS', 'Open Sans'],
  ['Arial Black', 'Arimo'],
];

const t0 = Date.now();
try {
  const fontDirectories = (opt.fonts || '').split(':').filter(Boolean);
  const conv = await createConverter({
    timeoutMs: Number(opt.timeout || 240000),
    ...(fontDirectories.length ? { fontDirectories } : {}),
    fontFallbacks: FALLBACKS,
    maxImageResolution: Number(opt.pdfdpi || 200),
  });
  let result;
  const input = path.resolve(opt.input);
  if (cmd === 'images') {
    const req = { inputPath: input, outputDir: path.resolve(opt.outdir), dpi: Number(opt.dpi || 144) };
    if (opt.pages) req.pages = opt.pages.split(',').map(Number);
    result = await conv.renderImages(req);
  } else if (cmd === 'pdf') {
    result = await conv.render({ inputPath: input, outputPath: path.resolve(opt.output) });
  } else if (cmd === 'convert') {
    result = await conv.convert({ inputPath: input, outputPath: path.resolve(opt.output) });
  } else {
    throw new Error('unknown command ' + cmd);
  }
  await conv.dispose();
  console.log(JSON.stringify({ ok: true, ms: Date.now() - t0, ...result }));
} catch (e) {
  console.log(JSON.stringify({ ok: false, ms: Date.now() - t0, error: String(e && e.message || e), code: e && e.code }));
  process.exitCode = 1;
}

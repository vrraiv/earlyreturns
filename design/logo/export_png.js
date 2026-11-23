// Renders the Early Returns PNGs from src/site/brand/*.svg (SI-9). Run from the repo root:
//   python src/site/brand/brand.py && node design/logo/export_png.js && python design/logo/make_ico.py
// Needs Playwright with a Chromium. Writes into src/site/brand/.
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
const dir = path.join(__dirname, '..', '..', 'src', 'site', 'brand');
const LIGHT = '#1B4978', DARK = '#C9CFD8', BG = '#FAF8F4';
const read = f => fs.readFileSync(path.join(dir, f), 'utf8');
// a standalone file with its colour fixed (no light/dark switch) for raster output
const fixed = (f, colour) => read(f).replace(/<style>.*?<\/style>/, '').replace(/fill="#1B4978"/, `fill="${colour}"`);
const jobs = [
  ['favicon-16.png', 16, fixed('favicon.svg', LIGHT), null, 0],
  ['favicon-32.png', 32, fixed('favicon.svg', LIGHT), null, 0],
  ['favicon-48.png', 48, fixed('favicon.svg', LIGHT), null, 0],
  ['apple-touch-icon.png', 180, fixed('favicon.svg', LIGHT), BG, 26],
  ['mark-512.png', 512, fixed('mark.svg', LIGHT), null, 0],
  ['mark-512-dark.png', 512, fixed('mark.svg', DARK), null, 0],
];
(async () => {
  const b = await chromium.launch();
  for (const [name, size, svg, bg, pad] of jobs) {
    const p = await b.newPage({ viewport: { width: size, height: size }, deviceScaleFactor: 1 });
    const inner = svg.replace('<svg ', `<svg width="${size - 2 * pad}" height="${size - 2 * pad}" `);
    await p.setContent(`<html><body style="margin:0;background:${bg || 'transparent'}">
      <div style="width:${size}px;height:${size}px;display:flex;align-items:center;justify-content:center">${inner}</div></body></html>`);
    await p.screenshot({ path: path.join(dir, name), omitBackground: !bg });
    await p.close();
  }
  await b.close();
})();

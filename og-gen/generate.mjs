import puppeteer from 'puppeteer';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function generateImages() {
  const browser = await puppeteer.launch({ headless: 'new' });
  const page = await browser.newPage();
  await page.setViewport({ width: 1200, height: 630, deviceScaleFactor: 2 });
  const htmlPath = path.join(__dirname, 'og-home.html');
  await page.goto(`file://${htmlPath}`, { waitUntil: 'networkidle0' });
  await page.evaluateHandle('document.fonts.ready');
  await new Promise(r => setTimeout(r, 1000));

  const outputPath = path.join(__dirname, '..', '.portfolio', 'preview.png');
  const element = await page.$('.og-card');
  if (element) {
    await element.screenshot({ path: outputPath, type: 'png' });
    console.log('Generated: ' + outputPath);
  } else {
    console.error('Could not find .og-card element');
    process.exit(1);
  }
  await page.close();
  await browser.close();
}

generateImages().catch(e => { console.error(e); process.exit(1); });

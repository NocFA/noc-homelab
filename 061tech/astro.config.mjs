import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://061tech.ie',
  output: 'static',
  integrations: [sitemap()],
  build: {
    assets: 'assets',
    inlineStylesheets: 'always'
  },
  compressHTML: true
});

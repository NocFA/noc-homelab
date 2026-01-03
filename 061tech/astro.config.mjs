import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://061tech.ie',
  output: 'static',
  build: {
    assets: 'assets'
  },
  compressHTML: true
});

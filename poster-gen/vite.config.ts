import { defineConfig } from 'vite';

export default defineConfig({
  build: {
    target: 'ES2022',
    lib: {
      entry: './src/app/index.ts',
      name: 'PosterGen',
      fileName: 'poster-gen',
    },
    rollupOptions: {
      output: {
        globals: {},
      },
    },
  },
});

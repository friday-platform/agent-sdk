import { defineConfig } from "vite-plus";

export default defineConfig({
  test: {
    execArgv: ["--experimental-wasm-jspi"],
    hookTimeout: 120000, // 2 minutes for compilation
    testTimeout: 30000, // 30 seconds for individual tests
  },
});

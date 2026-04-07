import { defineConfig } from "vite-plus";

export default defineConfig({
  test: {
    execArgv: ["--experimental-wasm-jspi"],
  },
});

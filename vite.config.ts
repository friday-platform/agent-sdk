import { defineConfig } from "vite-plus";

export default defineConfig({
  staged: {
    "!(packages/python/examples/**/agent-js/**)": "vp check --fix",
  },
  fmt: {},
  lint: { options: { typeAware: true, typeCheck: true } },
  test: {
    execArgv: ["--experimental-wasm-jspi"],
  },
  run: {
    cache: true,
  },
});

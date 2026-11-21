import { fileURLToPath } from "node:url";

// explicit path: the dev server may be started from another working directory
export default {
  plugins: {
    tailwindcss: { config: fileURLToPath(new URL("./tailwind.config.ts", import.meta.url)) },
    autoprefixer: {},
  },
};

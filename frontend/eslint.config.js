import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "node_modules", "src/lib/api/schema.d.ts"] },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: { ecmaVersion: 2023, globals: globals.browser },
    plugins: { "react-hooks": reactHooks, "react-refresh": reactRefresh },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      "@typescript-eslint/consistent-type-imports": "error",
      // Architecture rule: all HTTP goes through src/lib/api/client.ts.
      "no-restricted-imports": [
        "error",
        { paths: [{ name: "axios", message: "Use api.* from '@/lib/api/client' instead." }] },
      ],
      // Design rule: colours come from the tokens in styles/index.css, not hex codes.
      "no-restricted-syntax": [
        "error",
        {
          selector: "Literal[value=/#[0-9a-fA-F]{6}\\b/]",
          message: "Use a design token (bg-primary, text-muted, ...) instead of a hex colour.",
        },
      ],
    },
  },
  {
    // The client itself may use axios.
    files: ["src/lib/api/**"],
    rules: { "no-restricted-imports": "off" },
  },
  {
    files: ["**/*.test.{ts,tsx}", "src/test/**"],
    rules: { "no-restricted-syntax": "off" },
  },
);

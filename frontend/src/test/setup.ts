import "@testing-library/jest-dom/vitest";

import { cleanup, configure } from "@testing-library/react";
import { afterEach } from "vitest";

// findBy*/waitFor give up after 1 s by default. The full suite runs files in
// parallel, so on a busy laptop a screen can take longer than that to appear.
configure({ asyncUtilTimeout: 3000 });

afterEach(() => cleanup());

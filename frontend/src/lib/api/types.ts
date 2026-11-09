/**
 * Friendly names for the generated API types. `schema.d.ts` is generated from
 * the backend's OpenAPI schema (`npm run api:types`): never edit it by hand.
 */
import type { components } from "./schema";

export type Schemas = components["schemas"];

export type User = Schemas["User"];
export type Role = Schemas["RoleEnum"];

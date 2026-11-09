# Chalkboard frontend

The web app for Sai Personal Tuitions: a staff workspace (admin, teacher) and a
phone-first portal for parents and students. React 19 + TypeScript + Vite,
served as static files on the same address as the Django API.

## Run it locally

```powershell
# 1. the backend, in another terminal (see ../backend/README.md)
cd ../backend; .venv\Scripts\activate; python manage.py runserver

# 2. the frontend
cd frontend
npm install
npm run dev          # http://localhost:5173
```

The dev server forwards `/api` to Django on `127.0.0.1:8000`, so the app and the
API share one origin, like production behind Caddy (needed for the login cookie).
Point it elsewhere with `VITE_API_PROXY_TARGET`.

Dev-only previews (no login): `/dev/ui` (every shared component), `/dev/staff`,
`/dev/portal`.

## Commands

| Command             | What                                                            |
| ------------------- | --------------------------------------------------------------- |
| `npm run dev`       | Dev server with hot reload                                      |
| `npm run build`     | Type-check + production build into `dist/`                      |
| `npm test`          | Unit tests (Vitest + Testing Library + MSW)                     |
| `npm run check`     | Everything CI runs: format, lint, types, tests                  |
| `npm run api:types` | Regenerate `src/lib/api/schema.d.ts` from `openapi/schema.yaml` |

After a backend API change, export the schema and regenerate the types:

```powershell
cd ../backend; python manage.py spectacular --file ../frontend/openapi/schema.yaml
cd ../frontend; npm run api:types
```

## Architecture

```
src/
├── app/            router, route guards, layouts (StaffShell, PortalShell), providers
├── components/
│   ├── ui/         primitives: Button, Input, NativeSelect, Dialog, Table, Card, Skeleton
│   └── shared/     reusable blocks: DataTable, FilterBar, PageHeader, FormField, StatCard,
│                   StatusBadge, Money, ConfirmDialog, EmptyState, ErrorState, Logo
├── features/<area>/  one folder per business area: api.ts (query hooks), components/, pages/
├── lib/            api client (envelope, 401 → refresh → retry), session, formatting
└── styles/         design tokens: the ONLY place colours and fonts are defined
```

Rules:

1. Pages compose feature hooks and shared components. They never call axios.
2. All HTTP goes through `lib/api/client.ts` (`api.get/list/post/patch/delete/download`).
3. No raw colours: use the tokens from `styles/index.css` (`bg-primary`, `text-muted`...).
4. A UI pattern used twice moves into `components/shared/`.
5. Server data lives in TanStack Query; list filters and pages live in the URL (nuqs).

## Login model

- Access token (15 min) in memory only, never in localStorage.
- Refresh token in an HttpOnly cookie set by the backend; the app never sees it.
- On any 401 the client makes ONE shared refresh and retries; if that fails the
  session ends and the guards show the login page (remembering where you were).
- Logging out in one tab logs out the others.

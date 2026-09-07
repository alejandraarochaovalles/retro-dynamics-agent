# Agente de Dinámicas de Retrospectiva

🇪🇸 Español | [🇬🇧 English](README.en.md)

Genera dinámicas de retrospectiva interesantes y fuera de lo común, las facilita en un tablero colaborativo en tiempo real (posición libre, tipo Miro) y convierte los hallazgos en tickets de Jira o Azure DevOps.

**Demo en vivo**: [retro-dynamics-agent-gcdg.vercel.app](https://retro-dynamics-agent-gcdg.vercel.app) — backend en [retro-dynamics-agent.vercel.app](https://retro-dynamics-agent.vercel.app/health) / [docs](https://retro-dynamics-agent.vercel.app/docs).

## Por qué existe

Las retros suelen repetir el mismo formato (Start/Stop/Continue) hasta que dejan de generar insights nuevos. Este agente propone dinámicas distintas según el contexto del sprint (incidentes, sprint tranquilo, equipo nuevo, etc.), coordina la sesión en vivo con el equipo —estén donde estén, en la misma computadora o no— y cierra el círculo creando las acciones directamente en el backlog.

## Arquitectura

```
apps/web/                     → frontend (tablero en tiempo real, canvas de posición libre)
  src/shared/api/client.ts       → cliente HTTP hacia apps/api (tipos espejo de models.py)
  src/shared/components/organisms/ → StickyNote (variante canvas), ver su README
  src/features/session-setup/    → pantalla real: crear equipo, crear/unirse a sesión
  src/features/board/            → tablero en vivo — canvas de escritorio (ver su README)
  scripts/verify-board-sync.mjs  → prueba de sync en tiempo real con dos clientes, sin navegador
apps/api/                      → backend Python (FastAPI)
  main.py                        → entrypoint, monta los routers bajo /api
  config.py                      → variables de entorno (todas opcionales)
  db.py                          → engine/sesión de SQLAlchemy (Postgres, o SQLite si no hay DATABASE_URL)
  db_models.py                   → tablas ORM: Team, RetroSession, ActionItem
  alembic/                       → migraciones (fuente de verdad del esquema)
  models.py                      → schemas pydantic del contrato
  routes/                        → un endpoint (o grupo) por archivo, ver tabla abajo
  agents/                        → dynamic_generator.py, consolidator.py
  integrations/                  → jira_client.py, jira_oauth.py ("Connect with Jira"), oauth_state.py, azure_devops_client.py
  crypto.py                      → cifrado (Fernet) de los tokens OAuth en reposo
  tests/                         → tests con pytest + FastAPI TestClient, contra Postgres real
packages/contracts/            → contrato de API compartido (OpenAPI)
docs/adr/                       → decisiones de arquitectura documentadas
```

Ver el razonamiento detrás de cada decisión en [docs/adr](docs/adr/README.md).

## Stack

- **Frontend**: React + Liveblocks (tiempo real, canvas de posición libre) — desplegado en Vercel
- **Backend**: Python, funciones serverless (generación de dinámicas vía LLM, consolidación, integraciones)
- **Base de datos**: Postgres (Supabase)
- **Integraciones**: Jira Cloud y Azure DevOps

## Cómo correrlo

```bash
# Postgres local (una sola vez) — o usa tu propio Supabase/Postgres y saltá esto
brew install postgresql@16 && brew services start postgresql@16
createuser -s user 2>/dev/null; psql postgres -c "ALTER ROLE \"user\" WITH PASSWORD 'password'"
createdb -O user retro_dynamics        # coincide con .env.example
createdb -O user retro_dynamics_test   # solo para pytest, ver tests/conftest.py

# Backend (apps/api)
cd apps/api
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp ../../.env.example ../../.env   # opcional: sin GROQ/LIVEBLOCKS/JIRA/ADO, cada integración usa un modo "no configurado"
alembic upgrade head                # crea el esquema en Postgres
uvicorn main:app --reload          # http://127.0.0.1:8000/docs

# Frontend (apps/web), en otra terminal
cd apps/web
npm install
cp .env.example .env                # opcional: solo si el backend no corre en 127.0.0.1:8000
npm run dev                        # http://127.0.0.1:5173
```

Para el tablero en vivo con sync real (no solo verificado por tipos): creá un proyecto gratis en [liveblocks.io](https://liveblocks.io), copiá la **secret key** a `LIVEBLOCKS_SECRET_KEY` en el `.env` de la raíz del repo, reiniciá `uvicorn`, y corré `npm run verify:board` desde `apps/web` para la prueba de dos clientes.

```bash
# Tests del backend
cd apps/api && source .venv/bin/activate && pytest

# Lint + tests del frontend
cd apps/web && npm run lint && npm run test -- --run
```

### Persistencia

El estado ya no vive en memoria: `apps/api` usa SQLAlchemy + Alembic sobre Postgres.

- **Esquema**: 3 tablas — `teams`, `sessions`, `action_items` (FK `sessions.team_id → teams.id`, `action_items.session_id → sessions.id`). `notes`/`groups` quedan como columnas JSON dentro de `sessions` en vez de tablas propias: los produce `agents/consolidator.py` de una sola vez al cerrar la sesión y se leen igual, no se consultan nota por nota — ver el comentario en [db_models.py](apps/api/db_models.py).
- **Migraciones**: `alembic upgrade head` aplica el esquema; `alembic revision --autogenerate -m "..."` genera una nueva migración tras cambiar `db_models.py`. `alembic/env.py` toma la URL de `DATABASE_URL`, no del `alembic.ini` (placeholder sin usar).
- **Sin `DATABASE_URL`**: cae a un archivo SQLite local (`apps/api/dev.db`, gitignored) para que el backend arranque en cero configuración — igual que el resto de integraciones.
- **Tests**: corren contra una base Postgres real y separada (`retro_dynamics_test` por defecto, override con `TEST_DATABASE_URL`), no contra SQLite ni mocks — ver [tests/conftest.py](apps/api/tests/conftest.py). CI levanta un contenedor de Postgres para el job `api` (ver [.github/workflows/ci.yml](.github/workflows/ci.yml)).

### Contrato OpenAPI formalizado

`packages/contracts/openapi.yaml` ya no es solo la lista de paths — `components.schemas` tiene los 28 schemas reales, generados desde `apps/api/models.py` (vía el propio `/openapi.json` de FastAPI), no escritos a mano. Eso significa que el contrato no puede desincronizarse en silencio del código: si cambiás un campo en `models.py`, el contrato viejo queda desactualizado de forma visible, no incorrecto de forma invisible.

Para regenerarlo tras cambiar `models.py` o la firma de un endpoint (no se edita a mano):

```bash
cd apps/api && source .venv/bin/activate
python scripts/generate_openapi_contract.py   # no necesita servidor ni DB corriendo
```

El script toma el esquema directo de `app.openapi()`, le saca el prefijo `/api` a cada path (el contrato usa `servers: [{url: /api}]` + paths relativos), mantiene el `summary` humano de cada `operationId` (definido en el propio script) y limpia el `title` cosmético que FastAPI agrega a cada nodo de schema — con cuidado de no tocar los modelos que tienen un *campo* real llamado `title` (`ActionItem.title`, `SessionOut.title`, etc.), que casi se pierden en la primera versión de este script.

Nota: subimos el archivo de `openapi: 3.0.3` a `3.1.0` porque es lo que FastAPI + Pydantic v2 emiten nativamente (nullable vía `anyOf`/`type: null`, no `nullable: true`) — forzar 3.0.3 hubiera significado reescribir esa semántica a mano.

### Endpoints implementados

Las 19 operaciones (18 paths) del contrato ([packages/contracts/openapi.yaml](packages/contracts/openapi.yaml)) están implementadas sobre Postgres:

| Recurso | Endpoints |
|---|---|
| Equipos ([routes/teams.py](apps/api/routes/teams.py)) | `POST /teams`, `POST /teams/{id}/integration`, `GET /teams/{id}/sessions` |
| Dinámicas ([routes/dynamics.py](apps/api/routes/dynamics.py)) | `POST /dynamics/generate` |
| Sesiones ([routes/sessions.py](apps/api/routes/sessions.py)) | `POST /sessions`, `GET /sessions/{id}`, `POST /sessions/{id}/start`, `POST /sessions/{id}/phase`, `POST /sessions/join`, `POST /sessions/{id}/close`, `GET /sessions/{id}/summary` |
| Liveblocks ([routes/liveblocks_auth.py](apps/api/routes/liveblocks_auth.py)) | `POST /liveblocks/auth` |
| Consolidación ([routes/consolidation.py](apps/api/routes/consolidation.py)) | `GET /sessions/{id}/groups`, `PATCH /sessions/{id}/groups/{group_id}`, `GET /sessions/{id}/votes-summary` |
| Acciones ([routes/action_items.py](apps/api/routes/action_items.py)) | `POST /sessions/{id}/action-items`, `PATCH .../{item_id}`, `DELETE .../{item_id}` |
| Exportación ([routes/export.py](apps/api/routes/export.py)) | `POST /sessions/{id}/export` |

Todas bajo el prefijo `/api` (más `GET /health` sin prefijo). Documentación interactiva en `/docs` una vez levantado el servidor.

### Frontend conectado al backend

`apps/web` ya no es solo el shell: la pantalla `SessionSetup` ([src/features/session-setup](apps/web/src/features/session-setup/SessionSetup.tsx)) llama al backend real a través de [shared/api/client.ts](apps/web/src/shared/api/client.ts) y cubre el flujo completo desde crear el equipo hasta el resumen de una sesión cerrada:

1. chequea `/health` al montar y muestra si el backend está `online`/`offline`,
2. crea un equipo (`POST /teams`),
3. genera una tanda de 3 dinámicas propuestas (`POST /dynamics/generate`) y deja elegir una — o pedir 3 más (sin duplicar por nombre) para ir creciendo el pool a 6, 9, etc. — y luego crea la sesión con la dinámica elegida adjunta (`POST /sessions`), mostrando el `join_code` — o se une con un código existente (`POST /sessions/join`),
4. arranca la sesión (`POST /sessions/{id}/start`) — al llegar a fase `active`, monta el tablero en vivo (`BoardScreen`, ver abajo),
5. al cerrarse la sesión (fase `closed`), muestra `SessionSummaryScreen` ([src/features/summary](apps/web/src/features/summary/SessionSummaryScreen.tsx)): las notas y votos consolidados (`GET /sessions/{id}/summary`), un botón "+ Action item" por nota (`POST /sessions/{id}/action-items`), y un formulario para conectar el proyecto de Jira/Azure DevOps del equipo (`POST /teams/{id}/integration`) más exportación individual o masiva (`POST /sessions/{id}/export`) — la exportación es idempotente y muestra exactamente por qué falló un item (sin integración conectada, credenciales faltantes, etc.) en vez de fallar en silencio.

CORS en `apps/api` ya acepta `http://localhost:5173` y `http://127.0.0.1:5173` (el dev server de Vite arranca en cualquiera de las dos formas).

### Conexión con Jira vía OAuth 2.0 ("Connect with Jira")

Exportar a Jira dependía de un único token global (`JIRA_API_TOKEN`), configurado a mano por quien tuviera acceso al dashboard de Vercel — inviable si querés que otros equipos (u otras empresas) usen la app con su propia cuenta de Jira. Ahora cualquier equipo puede conectar su propio Jira con un flujo real de **OAuth 2.0 (3LO)** contra Atlassian, sin tocar variables de entorno ni tener acceso al código:

- **Botón "Connect with Jira"** en `SessionSummaryScreen`: redirige a `auth.atlassian.com`, el usuario consiente en el sitio de Atlassian y vuelve autenticado, sin que el backend vea ni guarde su contraseña.
- **`state` firmado, sin sesiones en el servidor** ([integrations/oauth_state.py](apps/api/integrations/oauth_state.py)): HMAC-SHA256 + TTL, coherente con el resto de la app (serverless en Vercel, sin estado entre invocaciones — ver ADR-0003). El `state` también transporta el `session_id` de la retro: como el frontend no tiene persistencia propia (ni localStorage ni router), es lo que le permite retomar exactamente la misma pantalla al volver del redirect de Atlassian.
- **Tokens cifrados en reposo** ([crypto.py](apps/api/crypto.py)): Fernet simétrico sobre `access_token`/`refresh_token` — nunca quedan como JSON plano en la base.
- **Rotación de refresh token**: Atlassian emite un `refresh_token` nuevo en cada refresh; [jira_client.py](apps/api/integrations/jira_client.py) persiste siempre el par rotado, no solo el `access_token` nuevo.
- **Fallback intacto**: si un equipo no conecta por OAuth, `jira_client.create_issue` sigue usando el token global `JIRA_API_TOKEN` exactamente como antes. El formulario manual ("Advanced / manual setup") sigue disponible como plan B, y es la única vía para Azure DevOps (su OAuth exige registrar una app en Microsoft Entra ID, fuera de alcance de esta pasada).
- **Cobertura de tests**: `test_oauth_state.py`, `test_crypto.py`, `test_jira_oauth_routes.py` y `test_jira_client_oauth.py` cubren la firma/verificación del `state`, el cifrado, el round-trip completo `/connect` → `/callback` (con las llamadas a Atlassian mockeadas) y los dos caminos de `create_issue` (OAuth y token global).

### Tablero en vivo (Liveblocks)

`features/board` cubre el **canvas de escritorio**: notas adhesivas con posición libre, arrastre en vivo (la posición se sincroniza en cada `pointermove`, no solo al soltar — es justamente lo que ADR-0002 usa para justificar Liveblocks sobre Supabase Realtime), voto alternable (ADR-0004) y cursores de otros participantes en vivo.

- **Modelo de datos en Liveblocks** (ver [types.ts](apps/web/src/features/board/types.ts)): `notes: LiveList<LiveObject<Note>>`, `votes: LiveMap<participante, LiveList<noteId>>` (cada participante escribe solo su propia entrada, sin conflictos de escritura), `phaseIndex: LiveObject<{value}>` durable. Presencia (efímera): `{name, cursor}`.
- **Auth**: `apps/api`'s `/api/liveblocks/auth` ya existía, pero no estaba verificado en vivo — al revisar el código fuente del SDK `@liveblocks/node` (no hay SDK oficial en Python) encontramos que la respuesta del endpoint real de Liveblocks es texto plano (el JWT), no `{"token": ...}` como asumía el código original; corregido en [routes/liveblocks_auth.py](apps/api/routes/liveblocks_auth.py).
- **Tipado**: los hooks de Liveblocks (`useStorage`, `useMutation`, etc.) están tipados en toda la app vía *declaration merging* (`declare global { interface Liveblocks {...} } }` en `types.ts`), no con genéricos por-llamada. `npx tsc --noEmit` pasa limpio contra los tipos reales de `@liveblocks/core@2.24.4` instalado.
- **Alcance de esta pasada**: canvas de escritorio, ahora con responsividad básica en mobile (el composer y los botones se acomodan y siguen usables por debajo de 640px) y un mensaje de estado de conexión más claro (vía `useStatus()`) cuando una red corporativa/VPN bloquea el WebSocket de Liveblocks, en vez de quedarse en "Connecting…" para siempre. La vista de lista mobile dedicada y la agrupación por lazo (ADR-0006) quedan para una pasada siguiente — ver [features/board/README.md](apps/web/src/features/board/README.md) para el detalle de qué falta.
- **Verificación**: sin una cuenta de Liveblocks real a mano, esto se verificó por tipos (`tsc`) y lógica pura (`votes.ts` con tests), no en vivo. `npm run verify:board` (dos clientes Liveblocks reales, sin navegador, probando que una nota/voto/cambio de fase de uno se ve en el otro) queda listo para correr en cuanto haya un `LIVEBLOCKS_SECRET_KEY` real en `.env`.

### Comportamiento sin credenciales

Cada integración externa se degrada a una respuesta clara en vez de romper el flujo:

| Variable faltante | Efecto |
|---|---|
| `GROQ_API_KEY` | `POST /dynamics/generate` responde con 3 dinámicas fijas (Sailboat, 4Ls, Mad/Sad/Glad) y `source: "fallback"` |
| `LIVEBLOCKS_SECRET_KEY` | `POST /liveblocks/auth` responde `configured: false` en vez de fallar |
| `JIRA_*` (equipo sin conectar por OAuth) / `AZURE_DEVOPS_*` | `POST /sessions/{id}/export` marca cada item como `status: "failed"` con el detalle de qué falta |
| `DATABASE_URL` | el backend usa un SQLite local (`apps/api/dev.db`) en vez de Postgres — ver [db.py](apps/api/db.py) |

Jira es la excepción: un equipo puede evitar esta dependencia por completo conectando su propia cuenta vía OAuth ("Connect with Jira", ver arriba) en vez de depender del token global.

## Estado del proyecto

🚧 En construcción, pero **desplegado en producción** (ver ADR-0003): backend y frontend corren en Vercel (funciones serverless + Vite estático), con Postgres real en Supabase, Groq y Liveblocks configurados y verificados end-to-end. El backend (`apps/api`) expone los endpoints del contrato con persistencia real en Postgres (SQLAlchemy + Alembic), y el frontend tiene el flujo completo hasta el tablero en vivo y una pantalla de resumen post-sesión (crear/unirse a sesión → canvas de escritorio con Liveblocks → resumen consolidado con exportación a Jira/Azure DevOps). La responsividad en mobile (layout, botones) está resuelta, aunque la vista de canvas mobile dedicada de ADR-0006 todavía no está construida. La exportación a Jira funciona de punta a punta en producción: cualquier equipo puede conectar su propia cuenta vía OAuth 2.0 ("Connect with Jira") sin depender de ninguna credencial global. Azure DevOps, en cambio, todavía depende del token global manual (`AZURE_DEVOPS_*`), que no está configurado en producción, así que esas exportaciones fallan con un mensaje claro de "no configurado" hasta que se sume su propio flujo de OAuth. El diseño completo está documentado en [docs/adr](docs/adr/README.md).

## Licencia

MIT — ver [LICENSE](LICENSE).

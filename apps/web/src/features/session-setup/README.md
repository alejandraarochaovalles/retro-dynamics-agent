# session-setup

First real screen wired to `apps/api`: create a team, start a retro session
for it (shows the join code), or join an existing one by code. Ends at the
lobby — phase "active" onward is the [board](../board/README.md) feature,
not yet implemented.

Talks to the backend through `shared/api/client.ts`. No routing library is
in place yet, so this is plain component state, not a route.

// SPA entry point. Screen-level routing (home, new retro, board,
// consolidation...) is defined as each feature in src/features/* is
// implemented.
import { SessionSetup } from "./features/session-setup/SessionSetup";

export default function App() {
  return (
    <main className="app-shell">
      <header className="app-header">
        <h1>Retro Dynamics Agent</h1>
        <p>Run a live retro, vote on what matters, ship the actions.</p>
      </header>
      <SessionSetup />
    </main>
  );
}

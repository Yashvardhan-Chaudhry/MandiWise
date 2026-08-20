# Improvements

Deferred work backlog. Items here are explicitly out of scope for now — not forgotten, not rejected outright, just not being built yet. Each item has one line on why it's deferred.

---

- **Arrivals volume via AGMARKNET scraping** — deferred: no official volume API; scraping is extra engineering and legal/ToS risk not yet worth taking on.
- **Transporter role (vehicle registry + booking)** — deferred: pooling can work via manual coordination first; a full transport marketplace is scope creep for the initial build.
- **Mandi steward role (operating hours, closures, notices)** — deferred: no steward stakeholder engaged yet, and no data source for this information.
- **Price trend view rather than single-day** — deferred: needs a historical data pipeline that doesn't exist yet.
- **Voice output for low-literacy users** — deferred: needs TTS integration; secondary to getting the core multilingual text UI working first.
- **Offline/low-bandwidth mode** — deferred: needs sync architecture; not worth building until the core flows are stable.

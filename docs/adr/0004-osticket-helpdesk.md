# osTicket as the helpdesk, with MySQL beside Postgres

Escalations must land in a real, self-hosted helpdesk reachable from Python over HTTP with the lightest possible compose stack. Candidates compared on 2026-09-22: Zammad (5 to 9 containers, Elasticsearch, 4GB+ RAM), Chatwoot (4+ containers, 4GB+), FreeScout (ticket API is a paid module), UVdesk (thin docs), Peppermint (archived), Helpy (unmaintained). osTicket runs as two containers and its free API creates tickets with an API key, which is the only helpdesk operation the agent needs. The cost is a MySQL container next to the project's Postgres. The helpdesk sits behind a small adapter interface with an in-memory fake, so swapping to Zammad later touches one file.

## Consequences

- Two database engines in compose.
- The osTicket API key is create-only; reading tickets back happens in its web UI, not from the agent or the Streamlit UI.

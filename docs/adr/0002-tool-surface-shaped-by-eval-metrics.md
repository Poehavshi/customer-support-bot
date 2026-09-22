# No order lookup tool, and enum-only escalation parameters

The harness scores tool precision as expected calls over all calls the agent made, and parameter accuracy as an exact match on the argument dict. A `get_order` tool would halve precision on every scenario, and a free-text `summary` argument on `escalate_to_human` could never match. So the agent gets the order as a snapshot rendered into the system prompt at the start of each run, and `escalate_to_human` takes only `order_id` and a closed `reason` enum; the ticket body is built server-side from the conversation in graph state. A customer naming a different order id is escalated with `order_not_found` rather than looked up.

## Consequences

- The agent can act on exactly one order per conversation. Multi-order support needs a lookup tool and an eval that tolerates it.
- Adding a free-text field to any tool will silently zero its parameter accuracy.

# LangGraph for the agent loop

The vendored harness imports the agent file and expects a `graph` or `construct_graph()` exposing LangGraph's `invoke`, passes LangChain message objects in state, and reads tool calls off `AIMessage` internals. A framework-free loop on the Anthropic SDK would need an adapter that fakes those message types, which is more code than the graph itself. We use LangGraph with `langchain-anthropic`, and keep tools, rules, the Order Store, and the helpdesk adapter as plain Python modules so the graph is a thin shell.

## Consequences

- Model calls go through `langchain-anthropic`, not the Anthropic SDK directly. Features the wrapper lags on (new thinking or effort parameters) may be unavailable until it catches up.

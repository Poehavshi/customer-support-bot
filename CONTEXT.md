# Customer Support Agent

An LLM-driven support agent for an e-commerce shop. It reads a customer conversation about one order, acts on that order through a fixed set of tools, and escalates to a human when the tools cannot fulfil the request. Its quality is measured against a fixed set of evaluation scenarios.

## Language

**Order**:
A single customer purchase, identified by an order id, with a total, a status, and a shipping address.
_Avoid_: purchase, transaction

**Order Status**:
Where an order is in its life: `pending`, `shipped`, or `delivered`, ending in `cancelled` or `refunded`. Cancel applies only to pending orders, refund only to delivered ones, address changes only to pending ones.
_Avoid_: state, stage

**Customer**:
The person who placed an order and is writing to support.
_Avoid_: user, client

**Support Agent**:
The LLM-driven program that reads the conversation and decides which tool to call.
_Avoid_: bot, assistant (the eval data uses "assistant" for its prior turns; in our language those are the agent's earlier replies)

**Tool**:
One of the fixed actions the support agent may take on an order: cancel, refund, modify, or escalate.
_Avoid_: function, action, skill

**Escalation**:
The support agent handing a request it cannot fulfil with the other tools to a human, as a ticket in the helpdesk.
_Avoid_: handoff, transfer

**Escalation Reason**:
The fixed category recorded on an escalation: why no tool could fulfil the request. One of `human_requested`, `unsupported_request`, `order_shipped`, `order_not_found`, `tool_failed`; never free text.
_Avoid_: cause, note, summary

**Ticket**:
The record an escalation creates in the helpdesk, holding the order, the reason, and the conversation so far.
_Avoid_: case, issue

**Scenario**:
One evaluation case: a conversation so far, the order it concerns, and the single tool call the agent is expected to make next.
_Avoid_: sample, test case, example

**Order Store**:
The system of record for orders, which the tools read and mutate.
_Avoid_: database (the store is a concept; PostgreSQL is its implementation)

**Helpdesk**:
The external system where escalations land as tickets and a human would pick them up.
_Avoid_: desk, ticketing system, queue

# Log Schema

Each normalized record:

{
  "timestamp": 1700000000,
  "action": "agent_fill_form",
  "correction": "",
  "metadata": {
    "role": "agent",
    "target_id": "address_field",
    "content": "北京市海淀区xx路"
  }
}

Rules:
- timestamp: integer unix seconds
- action: string event type
- correction: empty string or normalized correction code
- metadata: optional context payload

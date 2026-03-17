# Event Types

This reference defines normalized action values used by behavior-monitor.

## Agent actions
- agent_fill_form
- agent_click
- agent_submit
- agent_navigate

## User actions
- input
- clear
- delete
- undo
- cancel
- back
- confirm

## Correction mapping
- clear/delete/undo -> user_modified_previous_action
- cancel/back -> user_interrupted
- other actions -> empty correction string

"""Memory extraction — automatically extract and save memories from conversations.

Corresponds to TS: services/extractMemories/extractMemories.ts + prompts.ts.

Runs after each completed turn in the REPL. Analyzes recent messages and
saves any noteworthy information to the project memory directory.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from cc.memory.session_memory import load_memories, save_memory

if TYPE_CHECKING:

    from cc.models.messages import Message

logger = logging.getLogger(__name__)

# Minimum new messages before triggering extraction
MIN_NEW_MESSAGES = 4

# Extraction system prompt — corresponds to TS: services/extractMemories/prompts.ts
# Uses the same four-type taxonomy and frontmatter format as the main system prompt.
EXTRACTION_SYSTEM_PROMPT = """You are a memory extraction agent. Analyze the conversation below and determine if there is anything worth saving to persistent memory.

## What to save

Save information that would be useful in FUTURE conversations:

- **user**: User's role, preferences, expertise level, goals
- **feedback**: Corrections or confirmations about how to approach work
- **project**: Ongoing work context, decisions, deadlines (convert relative dates to absolute)
- **reference**: Pointers to external resources (Linear projects, Slack channels, dashboards)

## What NOT to save

- Code patterns, conventions, architecture, file paths, or project structure — these can be derived by reading the current project state.
- Git history, recent changes, or who-changed-what — `git log` / `git blame` are authoritative.
- Debugging solutions or fix recipes — the fix is in the code; the commit message has the context.
- Anything already documented in CLAUDE.md files.
- Ephemeral task details: in-progress work, temporary state, current conversation context.

These exclusions apply even when the user explicitly asks you to save. If they ask you to save a PR list or activity summary, ask what was *surprising* or *non-obvious* about it — that is the part worth keeping.

## Output format

If you find something worth saving, respond with EXACTLY this JSON format (no other text):

```json
{"memories": [{"name": "short_filename", "type": "user|feedback|project|reference", "content": "The memory content in markdown with frontmatter"}]}
```

If there is nothing worth saving, respond with exactly:

```json
{"memories": []}
```

Important:
- Each memory's content MUST include frontmatter:
  ---
  name: {{memory name}}
  description: {{one-line description}}
  type: {{user, feedback, project, reference}}
  ---
- For feedback/project types, structure content as: rule/fact, then **Why:** and **How to apply:** lines.
- Be very selective. Most turns have nothing worth saving.
- Never save API keys, passwords, or credentials.
- Do not duplicate information that already exists in the provided existing memories."""


async def extract_memories(
    messages: list[Message],
    cwd: str,
    call_model: Any,
    new_message_count: int | None = None,
    claude_dir: Any = None,
) -> list[str]:
    """Extract and save memories from recent conversation messages.

    Corresponds to TS: services/extractMemories/extractMemories.ts main flow.

    Args:
        messages: Full conversation messages.
        cwd: Current working directory (determines project).
        call_model: Async generator function for API calls.
        new_message_count: Number of new messages since last extraction.
        claude_dir: Override for ~/.claude directory (for testing).

    Returns:
        List of saved memory names (empty if nothing extracted).
    """
    from cc.models.messages import AssistantMessage, UserMessage

    # Count model-visible messages
    visible = [m for m in messages if isinstance(m, (UserMessage, AssistantMessage))]
    if new_message_count is None:
        new_message_count = len(visible)

    if new_message_count < MIN_NEW_MESSAGES:
        return []

    # Build context: recent messages as text + existing memories
    existing = load_memories(cwd, claude_dir=claude_dir)
    existing_text = ""
    if existing:
        existing_text = "\n".join(f"- {m['name']}: {m['content'][:100]}" for m in existing)

    # Build the conversation excerpt for the extractor
    recent: list[Message] = list(visible[-new_message_count:])
    conversation_text = _format_messages_for_extraction(recent)

    # Build the extraction prompt
    user_prompt = f"""## Existing memories

{existing_text or "(none)"}

## Recent conversation ({new_message_count} messages)

{conversation_text}

Analyze the above and extract any memories worth saving."""

    # Call the model
    from cc.core.events import TextDelta, TurnComplete
    from cc.models.messages import normalize_messages_for_api

    extract_messages: list[Message] = [UserMessage(content=user_prompt)]
    api_messages = normalize_messages_for_api(extract_messages)

    response_parts: list[str] = []
    try:
        async for event in call_model(
            messages=api_messages,
            system=EXTRACTION_SYSTEM_PROMPT,
            tools=None,
        ):
            if isinstance(event, TextDelta):
                response_parts.append(event.text)
            elif isinstance(event, TurnComplete):
                break
    except Exception as e:
        logger.warning("Memory extraction failed: %s", e)
        return []

    response = "".join(response_parts).strip()

    # Parse the response
    saved_names: list[str] = []
    try:
        # Extract JSON from response (may be wrapped in ```json blocks)
        json_str = response
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0]
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0]

        data = json.loads(json_str.strip())
        memories = data.get("memories", [])

        for mem in memories:
            name = mem.get("name", "")
            content = mem.get("content", "")
            if name and content:
                save_memory(cwd, name, content, claude_dir=claude_dir)
                saved_names.append(name)
                logger.info("Saved memory: %s", name)

    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.debug("Could not parse extraction response: %s", e)

    return saved_names


def _format_messages_for_extraction(messages: list[Message]) -> str:
    """Format messages into text for the extraction prompt."""
    from cc.models.messages import AssistantMessage, UserMessage

    parts: list[str] = []
    for msg in messages:
        if isinstance(msg, UserMessage):
            content = msg.content if isinstance(msg.content, str) else "[tool results]"
            parts.append(f"User: {content}")
        elif isinstance(msg, AssistantMessage):
            text = msg.get_text()
            if text:
                parts.append(f"Assistant: {text}")
    return "\n\n".join(parts)

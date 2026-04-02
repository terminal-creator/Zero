"""System prompt assembly.

Corresponds to TS: utils/systemPrompt.ts + constants/prompts.ts getSystemPrompt().
"""

from __future__ import annotations

import os
import platform
from datetime import UTC, datetime
from pathlib import Path

from .sections import (
    SUMMARIZE_TOOL_RESULTS,
    build_memory_prompt,
    get_actions_section,
    get_doing_tasks_section,
    get_intro_section,
    get_output_efficiency_section,
    get_system_section,
    get_tone_style_section,
    get_using_tools_section,
)


def compute_env_info(
    cwd: str,
    model: str,
    is_git: bool | None = None,
) -> str:
    """Compute environment information section.

    Corresponds to TS: constants/prompts.ts computeSimpleEnvInfo().
    """
    if is_git is None:
        is_git = Path(cwd, ".git").exists()

    shell = os.environ.get("SHELL", "unknown")
    shell_name = "zsh" if "zsh" in shell else ("bash" if "bash" in shell else shell)

    try:
        uname_sr = f"{platform.system()} {platform.release()}"
    except Exception:
        uname_sr = "Unknown"

    today = datetime.now(UTC).strftime("%Y-%m-%d")

    return f"""# Environment
You have been invoked in the following environment:
 - Primary working directory: {cwd}
  - Is a git repository: {is_git}
 - Platform: {platform.system().lower()}
 - Shell: {shell_name}
 - OS Version: {uname_sr}
 - You are powered by the model {model}.
 - The current date is {today}."""


def build_system_prompt(
    cwd: str,
    model: str,
    claude_md_content: str | None = None,
    memory_dir: str | None = None,
    memory_index_content: str | None = None,
) -> list[str]:
    """Build the complete system prompt.

    Corresponds to TS: constants/prompts.ts getSystemPrompt().

    Args:
        cwd: Current working directory.
        model: Model identifier string.
        claude_md_content: Loaded CLAUDE.md text (if any).
        memory_dir: Absolute path to the memory directory (enables memory prompt).
        memory_index_content: Content of MEMORY.md index file (if exists).

    Returns a list of prompt sections that are joined by the API layer.
    """
    sections: list[str | None] = [
        # Static (cacheable) sections
        get_intro_section(),
        get_system_section(),
        get_doing_tasks_section(),
        get_actions_section(),
        get_using_tools_section(),
        get_tone_style_section(),
        get_output_efficiency_section(),
        # Dynamic sections
        compute_env_info(cwd, model),
        SUMMARIZE_TOOL_RESULTS,
    ]

    # Memory system prompt — full behavioral instructions + MEMORY.md content
    # 对应 TS: memdir/memdir.ts loadMemoryPrompt() → buildMemoryPrompt()
    if memory_dir:
        sections.append(build_memory_prompt(memory_dir, memory_index_content))

    # CLAUDE.md content injection
    if claude_md_content:
        sections.append(f"""# CLAUDE.md
Codebase and user instructions are shown below. Be sure to adhere to these instructions.

{claude_md_content}""")

    return [s for s in sections if s is not None]

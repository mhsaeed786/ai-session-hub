"""Master Index adapter — parses sessions cataloged in AI-Agent-Sessions-Master/**/*.md."""

import os
import re
from datetime import datetime, timezone
from typing import Generator

from adapters.base import BaseAdapter, ParsedSession, ParsedMessage


class MasterIndexAdapter(BaseAdapter):
    TOOL_NAME = "master_index"
    DISPLAY_NAME = "AI-Agent-Sessions-Master"

    def discover_sessions(self) -> Generator[ParsedSession, None, None]:
        seen = set()
        for base in self.all_paths():
            if not os.path.isdir(base):
                continue
            for root, _dirs, files in os.walk(base):
                for fname in files:
                    if not fname.endswith(".md") or fname == "README.md":
                        continue
                    fpath = os.path.join(root, fname)
                    tool_dir = os.path.basename(root)
                    if tool_dir.lower() in ("no-data-found", ".git"):
                        continue
                    # Parse the markdown file for sessions
                    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                        text = f.read()

                    # Find sessions separated by "## Session"
                    sections = re.split(r"(?m)^##\s+Session\s+", text)
                    stat = os.stat(fpath)
                    for idx, sec in enumerate(sections[1:], 1):
                        lines = sec.strip().splitlines()
                        header = lines[0] if lines else f"Session {idx}"
                        # Try to extract title, date, prompt, summary
                        m_title = re.search(r"\*\*Title\*\*:\s*(.*)", sec)
                        m_date = re.search(r"\*\*Date\*\*:\s*(.*)", sec)
                        m_prompt = re.search(r"-\s+\*\*Initial Prompt\*\*:\s*[\"']?(.*?)[\"']?(?:\n|$)", sec)
                        
                        sid = f"{tool_dir}_{idx}"
                        if ":" in header:
                            parts = header.split(":", 1)
                            raw_id = parts[1].strip()
                            if len(raw_id) > 4:
                                sid = f"{tool_dir}_{raw_id}"

                        if sid in seen:
                            continue
                        seen.add(sid)

                        title = ""
                        if m_title and m_title.group(1).strip():
                            title = m_title.group(1).strip()
                        elif m_prompt and m_prompt.group(1).strip():
                            title = m_prompt.group(1).strip()
                        else:
                            title = f"{tool_dir} - {header}"

                        if len(title) > 80:
                            title = title[:77] + "..."

                        yield ParsedSession(
                            session_id=f"master:{sid}",
                            title=title,
                            project_path=None,
                            model=tool_dir.lower(),
                            status="completed",
                            started_at=m_date.group(1).strip() if m_date else None,
                            ended_at=None,
                            file_path=fpath,
                            file_size_bytes=stat.st_size,
                            file_mtime=stat.st_mtime,
                            raw_metadata={"tool_dir": tool_dir, "section_idx": idx, "section_text": sec[:50000]},
                        )

    def parse_messages(self, session: ParsedSession) -> Generator[ParsedMessage, None, None]:
        sec = (session.raw_metadata or {}).get("section_text", "")
        if not sec:
            return

        m_prompt = re.search(r"-\s+\*\*Initial Prompt\*\*:\s*[\"']?(.*?)[\"']?(?:\n-|\n\n|$)", sec, re.DOTALL)
        m_summary = re.search(r"-\s+\*\*Summary\*\*:\s*(.*?)(?:\n-|\n\n|$)", sec, re.DOTALL)
        m_repl = re.search(r"-\s+\*\*Master Replication Prompt\*\*:\s*(.*?)(?:\n---|\Z)", sec, re.DOTALL)

        seq = 0
        if m_prompt and m_prompt.group(1).strip():
            seq += 1
            yield ParsedMessage(
                message_id=f"{session.session_id}_user",
                role="user",
                content_text=self._truncate(m_prompt.group(1).strip(), 20_000),
                content_type="text",
                seq=seq,
            )

        if m_summary and m_summary.group(1).strip():
            seq += 1
            yield ParsedMessage(
                message_id=f"{session.session_id}_summary",
                role="assistant",
                content_text=self._truncate(f"[Summary of Session]\n{m_summary.group(1).strip()}", 20_000),
                content_type="text",
                seq=seq,
            )

        if m_repl and m_repl.group(1).strip():
            seq += 1
            yield ParsedMessage(
                message_id=f"{session.session_id}_master",
                role="assistant",
                content_text=self._truncate(f"[Master Replication Prompt]\n{m_repl.group(1).strip()}", 20_000),
                content_type="text",
                seq=seq,
            )

        if seq == 0:
            # Fallback: yield the section text as user prompt
            yield ParsedMessage(
                message_id=f"{session.session_id}_raw",
                role="user",
                content_text=self._truncate(sec, 20_000),
                content_type="text",
                seq=1,
            )

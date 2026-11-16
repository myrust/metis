"""JSON persistence for To-do list, Ideas, and Custom Charts under ~/.metis/data/."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any


class WorkbenchStore:
    """Stores personal todos, ideas, and custom chart definitions."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._todos_file = self.data_dir / "todos.json"
        self._ideas_file = self.data_dir / "ideas.json"
        self._charts_file = self.data_dir / "charts.json"
        self._sessions_file = self.data_dir / "sessions.json"
        self._projects_file = self.data_dir / "projects.json"

    @staticmethod
    def _read_list(path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    @staticmethod
    def _write_list(path: Path, items: list[dict[str, Any]]) -> None:
        path.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")

    # --- To-dos ---
    def list_todos(self) -> list[dict[str, Any]]:
        return self._read_list(self._todos_file)

    def add_todo(self, title: str, priority: str = "medium") -> dict[str, Any]:
        items = self.list_todos()
        item = {
            "id": uuid.uuid4().hex[:10],
            "title": title.strip(),
            "done": False,
            "priority": priority,
            "created_at": time.time(),
        }
        items.insert(0, item)
        self._write_list(self._todos_file, items)
        return item

    def toggle_todo(self, todo_id: str, done: bool | None = None) -> dict[str, Any]:
        items = self.list_todos()
        for item in items:
            if item.get("id") == todo_id:
                item["done"] = (not bool(item.get("done"))) if done is None else done
                self._write_list(self._todos_file, items)
                return item
        raise KeyError(f"Todo not found: {todo_id}")

    def delete_todo(self, todo_id: str) -> None:
        items = self.list_todos()
        filtered = [i for i in items if i.get("id") != todo_id]
        if len(filtered) == len(items):
            raise KeyError(f"Todo not found: {todo_id}")
        self._write_list(self._todos_file, filtered)

    # --- Ideas ---
    def list_ideas(self) -> list[dict[str, Any]]:
        return self._read_list(self._ideas_file)

    def add_idea(self, title: str, content: str = "", tag: str = "general") -> dict[str, Any]:
        items = self.list_ideas()
        item = {
            "id": uuid.uuid4().hex[:10],
            "title": title.strip(),
            "content": content.strip(),
            "tag": tag.strip() or "general",
            "created_at": time.time(),
        }
        items.insert(0, item)
        self._write_list(self._ideas_file, items)
        return item

    def delete_idea(self, idea_id: str) -> None:
        items = self.list_ideas()
        filtered = [i for i in items if i.get("id") != idea_id]
        if len(filtered) == len(items):
            raise KeyError(f"Idea not found: {idea_id}")
        self._write_list(self._ideas_file, filtered)

    # --- Custom Charts ---
    def list_charts(self) -> list[dict[str, Any]]:
        return self._read_list(self._charts_file)

    def add_chart(
        self,
        title: str,
        chart_type: str,
        labels: list[str],
        values: list[float],
    ) -> dict[str, Any]:
        items = self.list_charts()
        item = {
            "id": uuid.uuid4().hex[:10],
            "title": title.strip(),
            "chart_type": chart_type,
            "labels": labels,
            "values": values,
            "created_at": time.time(),
        }
        items.insert(0, item)
        self._write_list(self._charts_file, items)
        return item

    def delete_chart(self, chart_id: str) -> None:
        items = self.list_charts()
        filtered = [i for i in items if i.get("id") != chart_id]
        if len(filtered) == len(items):
            raise KeyError(f"Chart not found: {chart_id}")
        self._write_list(self._charts_file, filtered)

    # --- Chat Sessions ---
    def list_sessions(self) -> list[dict[str, Any]]:
        return self._read_list(self._sessions_file)

    def create_session(
        self,
        title: str = "New Chat",
        project_id: str | None = None,
    ) -> dict[str, Any]:
        items = self.list_sessions()
        session = {
            "id": uuid.uuid4().hex[:10],
            "title": title.strip() or "New Chat",
            "project_id": project_id,
            "created_at": time.time(),
            "messages": [],
        }
        items.insert(0, session)
        self._write_list(self._sessions_file, items)
        return session

    def get_session(self, session_id: str) -> dict[str, Any]:
        for item in self.list_sessions():
            if item.get("id") == session_id:
                return item
        raise KeyError(f"Session not found: {session_id}")

    def append_session_message(self, session_id: str, entry: dict[str, Any]) -> dict[str, Any]:
        items = self.list_sessions()
        for item in items:
            if item.get("id") == session_id:
                msgs = list(item.get("messages", []))
                msgs.append(entry)
                item["messages"] = msgs
                if entry.get("kind") == "user" and item.get("title") in {"New Chat", "新对话"}:
                    item["title"] = str(entry.get("text", ""))[:32] or item["title"]
                self._write_list(self._sessions_file, items)
                return item
        raise KeyError(f"Session not found: {session_id}")

    def delete_session(self, session_id: str) -> None:
        items = self.list_sessions()
        filtered = [i for i in items if i.get("id") != session_id]
        if len(filtered) == len(items):
            raise KeyError(f"Session not found: {session_id}")
        self._write_list(self._sessions_file, filtered)

    # --- Projects ---
    def list_projects(self) -> list[dict[str, Any]]:
        return self._read_list(self._projects_file)

    def add_project(
        self,
        name: str,
        path: str,
        node_id: str = "local",
        description: str = "",
    ) -> dict[str, Any]:
        items = self.list_projects()
        proj = {
            "id": uuid.uuid4().hex[:10],
            "name": name.strip(),
            "path": path.strip(),
            "node_id": node_id.strip() or "local",
            "description": description.strip(),
            "created_at": time.time(),
        }
        items.insert(0, proj)
        self._write_list(self._projects_file, items)
        return proj

    def delete_project(self, project_id: str) -> None:
        items = self.list_projects()
        filtered = [i for i in items if i.get("id") != project_id]
        if len(filtered) == len(items):
            raise KeyError(f"Project not found: {project_id}")
        self._write_list(self._projects_file, filtered)

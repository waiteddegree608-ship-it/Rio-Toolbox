from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_FILE = DATA_DIR / "toolbox.json"

DEFAULT_DATA: Dict[str, Any] = {
    "calendar": {"single_events": [], "recurring_events": []},
    "tasks": {"daily": [], "temporary": [], "last_reset": None},
    "ai": {"settings": {}, "presets": [], "history": []},
    "fortune": {"history": []},
    "task_assistant": {"history": []}
}


def _ensure_store() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        DATA_FILE.write_text(json.dumps(DEFAULT_DATA, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_raw() -> Dict[str, Any]:
    _ensure_store()
    with DATA_FILE.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_raw(payload: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with DATA_FILE.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _today_str() -> str:
    return date.today().isoformat()


class DataStore:
    @staticmethod
    def get_data() -> Dict[str, Any]:
        data = _read_raw()
        # merge with defaults to avoid missing keys when file predates fields
        result = json.loads(json.dumps(DEFAULT_DATA))  # deep copy
        for key, value in data.items():
            result[key] = value
        return result

    @staticmethod
    def persist(data: Dict[str, Any]) -> None:
        _write_raw(data)

    # ---- calendar utilities ----
    @staticmethod
    def add_single_event(title: str, event_date: str) -> Dict[str, Any]:
        data = DataStore.get_data()
        record: Dict[str, Any] = {"id": str(uuid.uuid4()), "title": title, "date": event_date}
        data["calendar"]["single_events"].append(record)
        DataStore.persist(data)
        return record

    @staticmethod
    def add_recurring_event(title: str, start_date: str, end_date: str, weekday: int) -> Dict[str, Any]:
        data = DataStore.get_data()
        record: Dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "title": title,
            "start_date": start_date,
            "end_date": end_date,
            "weekday": weekday
        }
        data["calendar"]["recurring_events"].append(record)
        DataStore.persist(data)
        return record

    @staticmethod
    def list_single_events() -> List[Dict[str, Any]]:
        return DataStore.get_data()["calendar"]["single_events"]

    @staticmethod
    def list_recurring_events() -> List[Dict[str, Any]]:
        return DataStore.get_data()["calendar"]["recurring_events"]

    @staticmethod
    def clear_single_event(event_id: str) -> bool:
        data = DataStore.get_data()
        original = len(data["calendar"]["single_events"])
        data["calendar"]["single_events"] = [item for item in data["calendar"]["single_events"] if item["id"] != event_id]
        changed = len(data["calendar"]["single_events"]) != original
        if changed:
            DataStore.persist(data)
        return changed

    @staticmethod
    def clear_recurring_event(event_id: str) -> bool:
        data = DataStore.get_data()
        original = len(data["calendar"]["recurring_events"])
        data["calendar"]["recurring_events"] = [item for item in data["calendar"]["recurring_events"] if item["id"] != event_id]
        changed = len(data["calendar"]["recurring_events"]) != original
        if changed:
            DataStore.persist(data)
        return changed

    # ---- tasks utilities ----
    @staticmethod
    def _reset_daily_if_needed(data: Dict[str, Any]) -> None:
        last_reset = data["tasks"].get("last_reset")
        today = _today_str()
        if last_reset != today:
            for task in data["tasks"]["daily"]:
                task["completed"] = False
            data["tasks"]["last_reset"] = today
            DataStore.persist(data)

    @staticmethod
    def list_tasks() -> Dict[str, Any]:
        data = DataStore.get_data()
        DataStore._reset_daily_if_needed(data)
        return data["tasks"]

    @staticmethod
    def add_task(title: str, task_type: str) -> Dict[str, Any]:
        if task_type not in {"daily", "temporary"}:
            raise ValueError("Unsupported task type")
        data = DataStore.get_data()
        DataStore._reset_daily_if_needed(data)
        record: Dict[str, Any] = {"id": str(uuid.uuid4()), "title": title, "completed": False, "type": task_type}
        data["tasks"][task_type].append(record)
        DataStore.persist(data)
        return record

    @staticmethod
    def toggle_task(task_id: str) -> Optional[Dict[str, Any]]:
        data = DataStore.get_data()
        DataStore._reset_daily_if_needed(data)
        for task_group in ("daily", "temporary"):
            for task in data["tasks"][task_group]:
                if task["id"] == task_id:
                    task["completed"] = not task.get("completed", False)
                    DataStore.persist(data)
                    return task
        return None

    @staticmethod
    def delete_task(task_id: str) -> bool:
        data = DataStore.get_data()
        changed = False
        for task_group in ("daily", "temporary"):
            before = len(data["tasks"][task_group])
            data["tasks"][task_group] = [task for task in data["tasks"][task_group] if task["id"] != task_id]
            if len(data["tasks"][task_group]) != before:
                changed = True
        if changed:
            DataStore.persist(data)
        return changed

    # ---- AI utilities ----
    @staticmethod
    def get_ai_settings() -> Dict[str, Any]:
        data = DataStore.get_data()
        return data["ai"].get("settings", {})

    @staticmethod
    def update_ai_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
        data = DataStore.get_data()
        data["ai"]["settings"] = settings
        DataStore.persist(data)
        return settings

    @staticmethod
    def list_ai_presets() -> List[Dict[str, Any]]:
        data = DataStore.get_data()
        return data["ai"].get("presets", [])

    @staticmethod
    def add_ai_preset(preset: Dict[str, Any]) -> Dict[str, Any]:
        data = DataStore.get_data()
        record: Dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "name": preset.get("name", "未命名预设"),
            "description": preset.get("description", ""),
            "prompt": preset.get("prompt", ""),
            "character_card": preset.get("character_card"),
            "world_book": preset.get("world_book")
        }
        data["ai"].setdefault("presets", []).append(record)
        DataStore.persist(data)
        return record

    @staticmethod
    def delete_ai_preset(preset_id: str) -> bool:
        data = DataStore.get_data()
        presets = data["ai"].get("presets", [])
        before = len(presets)
        data["ai"]["presets"] = [item for item in presets if item.get("id") != preset_id]
        if len(data["ai"]["presets"]) != before:
            DataStore.persist(data)
            return True
        return False

    @staticmethod
    def append_ai_chat_log(entry: Dict[str, Any]) -> Dict[str, Any]:
        data = DataStore.get_data()
        history = data["ai"].setdefault("history", [])
        history.append(entry)
        max_entries = 100
        if len(history) > max_entries:
            data["ai"]["history"] = history[-max_entries:]
        DataStore.persist(data)
        return entry

    @staticmethod
    def list_ai_history() -> List[Dict[str, Any]]:
        data = DataStore.get_data()
        return data["ai"].get("history", [])

    @staticmethod
    def clear_ai_history() -> None:
        data = DataStore.get_data()
        data["ai"]["history"] = []
        DataStore.persist(data)

    # ---- fortune utilities ----
    @staticmethod
    def append_fortune_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
        data = DataStore.get_data()
        fortune = data.setdefault("fortune", {})
        history = fortune.setdefault("history", [])
        history.append(entry)
        max_entries = 365
        if len(history) > max_entries:
            fortune["history"] = history[-max_entries:]
        DataStore.persist(data)
        return entry

    @staticmethod
    def list_fortune_history(limit: Optional[int] = None) -> List[Dict[str, Any]]:
        data = DataStore.get_data()
        history = data.get("fortune", {}).get("history", [])
        if limit is None:
            return history
        return history[-limit:]

    @staticmethod
    def get_today_fortune() -> Optional[Dict[str, Any]]:
        history = DataStore.list_fortune_history()
        today = _today_str()
        for entry in reversed(history):
            if entry.get("date") == today:
                return entry
        return None

    # ---- task assistant utilities ----
    @staticmethod
    def append_task_assistant_log(entry: Dict[str, Any]) -> Dict[str, Any]:
        data = DataStore.get_data()
        history = data.setdefault("task_assistant", {}).setdefault("history", [])
        history.append(entry)
        # 保留所有历史记录，不设上限
        DataStore.persist(data)
        return entry

    @staticmethod
    def list_task_assistant_history(target_date: Optional[str] = None) -> List[Dict[str, Any]]:
        data = DataStore.get_data()
        history = data.get("task_assistant", {}).get("history", [])
        if target_date is None:
            return history
        # 按日期过滤
        return [entry for entry in history if entry.get("date") == target_date]

    @staticmethod
    def clear_task_assistant_history(target_date: Optional[str] = None) -> None:
        data = DataStore.get_data()
        if target_date is None:
            # 清空所有记录
            data.setdefault("task_assistant", {})["history"] = []
        else:
            # 清空指定日期的记录
            history = data.get("task_assistant", {}).get("history", [])
            data.setdefault("task_assistant", {})["history"] = [
                entry for entry in history if entry.get("date") != target_date
            ]
        DataStore.persist(data)


def within_range(target: date, start: date, end: date) -> bool:
    return start <= target <= end


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()

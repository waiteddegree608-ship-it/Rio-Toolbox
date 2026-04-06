from __future__ import annotations

import json
import logging
import random
import re
import uuid
import zlib
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union, cast

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import httpx
from pydantic import BaseModel, Field

from . import ocr_utils
from .storage import DataStore, parse_date

logger = logging.getLogger(__name__)

APP_TITLE = "Rio Toolbox Backend"
APP_DESCRIPTION = "Service layer powering the Rio Toolbox interface."
APP_VERSION = "0.1.0"

app = FastAPI(title=APP_TITLE, description=APP_DESCRIPTION, version=APP_VERSION)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"

if not FRONTEND_DIR.exists():  # Safety guard if the directory is missing.
    raise RuntimeError("Frontend directory is missing. Expected at: {0}".format(FRONTEND_DIR))

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8888", "http://localhost:8888"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


UPLOAD_CATEGORIES: Dict[str, Dict[str, Any]] = {
    "ai-images": {"folder": Path("ai/images"), "extensions": {".png", ".jpg", ".jpeg", ".webp"}},
    "ai-cards": {"folder": Path("ai/cards"), "extensions": {".png", ".jpg", ".jpeg", ".webp"}},
    "ai-worlds": {"folder": Path("ai/worlds"), "extensions": {".json"}}
}

for config in UPLOAD_CATEGORIES.values():
    target_folder = UPLOAD_DIR / config["folder"]
    target_folder.mkdir(parents=True, exist_ok=True)

OCR_INPUT_DIR = UPLOAD_DIR / "ocr" / "input"
OCR_OUTPUT_DIR = UPLOAD_DIR / "ocr" / "output"
OCR_INPUT_DIR.mkdir(parents=True, exist_ok=True)
OCR_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_OCR_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".pdf"}

MENU_ITEMS = [
    {"name": "老坛酸菜牛肉面", "category": "热面"},
    {"name": "香煎鸡腿便当", "category": "盖饭"},
    {"name": "麻婆豆腐套餐", "category": "川菜"},
    {"name": "肥牛石锅拌饭", "category": "韩式"},
    {"name": "脆皮炸鸡", "category": "小食"},
    {"name": "酸汤肥牛粉", "category": "粉类"},
    {"name": "黑椒牛柳意面", "category": "意面"},
    {"name": "广式煲仔饭", "category": "粤菜"},
    {"name": "香辣烤鱼", "category": "江湖菜"},
    {"name": "鲜虾云吞面", "category": "港式"},
    {"name": "番茄牛腩锅", "category": "火锅"},
    {"name": "照烧鳗鱼饭", "category": "日式"},
    {"name": "蒜香排骨烤饭", "category": "焗饭"},
    {"name": "椒香烤鱼拌饭", "category": "融合菜"},
    {"name": "泰式冬阴功汤", "category": "汤品"},
    {"name": "香菇滑鸡煲", "category": "砂锅"}
]

FORTUNE_DECK = [
    {"type": "大吉", "message": "今日气流顺畅，适合推进重要计划。保持真诚，你会迎来意想不到的回应。"},
    {"type": "吉", "message": "小步快跑也能抵达远方，循序渐进地完成安排，自会收获满意答复。"},
    {"type": "中吉", "message": "把握主线节奏，偶有波折也不必在意，耐心会为你带来好消息。"},
    {"type": "小吉", "message": "调整心态，让自己慢下来，细致处理眼前事务，幸运会悄然靠近。"},
    {"type": "末吉", "message": "别急着下定结论，再观察一下，适度妥协反而能拓宽方案。"},
    {"type": "凶", "message": "注意沟通语气与节奏，容易发生误会。先稳定情绪，再做决定。"},
    {"type": "小凶", "message": "谨慎行事，切忌逞强。暂缓争执，多听一听身边人的意见。"},
    {"type": "大凶", "message": "请把重心放在自我照顾上，减少冒险，等待风浪过去再起航。"}
]

FORTUNE_QUOTES_PATH = Path(__file__).resolve().parent.parent / "莉音运势签语集.md"
DEFAULT_FORTUNE_QUOTE = "亲爱的，无论签面如何，我都会在你身边陪着你，一起面对今天的挑战和惊喜。"


_FORTUNE_QUOTES_CACHE: Dict[str, Any] = {"mtime": None, "data": {}}


def _parse_fortune_quotes(path: Path) -> Dict[str, List[str]]:
    if not path.is_file():
        return {}
    try:
        raw_text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raw_text = path.read_text(encoding="utf-8", errors="ignore")
    quotes: Dict[str, List[str]] = {}
    current_key: Optional[str] = None
    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith(":") and not line.startswith("-"):
            current_key = line[:-1].strip()
            if current_key:
                quotes.setdefault(current_key, [])
            continue
        if line.startswith("-") and current_key:
            text = line.lstrip("- ")
            if text.startswith("\"") and text.endswith("\"") and len(text) >= 2:
                text = text[1:-1]
            quotes.setdefault(current_key, []).append(text)
    return quotes


def get_fortune_quotes() -> Dict[str, List[str]]:
    try:
        mtime = FORTUNE_QUOTES_PATH.stat().st_mtime
    except OSError:
        return {}
    cache_mtime = _FORTUNE_QUOTES_CACHE.get("mtime")
    if cache_mtime == mtime:
        data = _FORTUNE_QUOTES_CACHE.get("data")
        return cast(Dict[str, List[str]], data) if isinstance(data, dict) else {}
    quotes = _parse_fortune_quotes(FORTUNE_QUOTES_PATH)
    _FORTUNE_QUOTES_CACHE["mtime"] = mtime
    _FORTUNE_QUOTES_CACHE["data"] = quotes
    return quotes

LIYIN_IMAGE_SUBPATH = Path("assets") / "images" / "liyin"

DEFAULT_SYSTEM_PROMPT = (
    "你是调月莉音，一位温柔且富有想象力的聊天伙伴。"
    "请保持语气自然，耐心回应用户，必要时主动引导话题。"
)
PRESET_CONTEXT_LIMIT = 0
TEXT_FILE_EXTENSIONS = {".txt", ".md", ".json", ".yaml", ".yml"}
CARD_TEXT_KEYWORDS = {"chara", "character", "character_card", "metadata", "sillytavern"}


class CreateSingleEvent(BaseModel):
    title: str = Field(..., min_length=1, max_length=60)
    date: date


class CreateRecurringEvent(BaseModel):
    title: str = Field(..., min_length=1, max_length=60)
    start_date: date
    end_date: date
    weekday: int = Field(..., ge=1, le=7, description="1=周一, 7=周日")


class CreateTask(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    task_type: str = Field(..., description="daily 或 temporary")


class UpdateAISettings(BaseModel):
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    character_image: Optional[str] = None


class AIPresetPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    description: Optional[str] = None
    prompt: Optional[str] = None
    character_card: Optional[str] = None
    world_book: Optional[str] = None


class AIMessage(BaseModel):
    role: str = Field(..., pattern=r"^(system|user|assistant)$")
    content: str = Field(..., min_length=1)


class AIChatPayload(BaseModel):
    messages: List[AIMessage]
    preset_id: Optional[str] = None


def serve_page(file_name: str) -> FileResponse:
    page_path = FRONTEND_DIR / file_name
    if not page_path.exists():
        raise HTTPException(status_code=404, detail="Page not found.")
    return FileResponse(page_path)


def pick_liyin_image() -> Optional[str]:
    target_dir = FRONTEND_DIR / LIYIN_IMAGE_SUBPATH
    if not target_dir.exists():
        return None
    images = [item.name for item in target_dir.iterdir() if item.is_file() and item.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}]
    if not images:
        return None
    chosen = random.choice(images)
    return f"/assets/images/liyin/{chosen}"


def build_calendar_timeline(start_date: date, end_date: date) -> List[Dict[str, Any]]:
    today = date.today()
    timeline: List[Dict[str, Any]] = []

    for item in DataStore.list_single_events():
        event_date = parse_date(item["date"])
        if start_date <= event_date <= end_date:
            timeline.append({
                "id": item["id"],
                "title": item["title"],
                "date": event_date.isoformat(),
                "type": "single",
                "days_from_today": (event_date - today).days
            })

    for item in DataStore.list_recurring_events():
        start = parse_date(item["start_date"])
        end = parse_date(item["end_date"])
        weekday = item["weekday"]
        window_start = max(start_date, start)
        window_end = min(end_date, end)
        if window_start > window_end:
            continue
        first = window_start
        offset = (weekday - first.isoweekday()) % 7
        first += timedelta(days=offset)
        pointer = first
        while pointer <= window_end:
            timeline.append({
                "id": item["id"],
                "title": item["title"],
                "date": pointer.isoformat(),
                "type": "recurring",
                "weekday": weekday,
                "days_from_today": (pointer - today).days
            })
            pointer += timedelta(days=7)

    timeline.sort(key=lambda entry: (entry["date"], entry["title"]))
    return timeline


def slugify_filename(text: str, fallback: str = "translation") -> str:
    candidate = re.sub(r"\s+", "_", text.strip())
    candidate = re.sub(r"[\\/:*?\"<>|]", "_", candidate)
    candidate = candidate.strip("._")
    return candidate or fallback


def parse_translation_response(content: str) -> Dict[str, str]:
    payload: Dict[str, str] = {"title": "", "body": ""}
    if not content:
        return payload
    text = content.strip()
    if text.startswith("{"):
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                data_dict = cast(Dict[str, Any], data)
                payload["title"] = str(data_dict.get("title", ""))
                payload["body"] = str(data_dict.get("body", ""))
                return payload
        except json.JSONDecodeError:
            pass
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return payload
    first_line = lines[0]
    if ":" in first_line:
        label, value = first_line.split(":", 1)
        if label.lower().startswith(("title", "标题")):
            payload["title"] = value.strip()
        else:
            payload["title"] = first_line
    else:
        payload["title"] = first_line
    payload["body"] = "\n".join(lines[1:]).strip() or text
    return payload


def resolve_upload_path(url: Optional[str]) -> Optional[Path]:
    if not url:
        return None
    if not url.startswith("/uploads/"):
        return None
    relative = Path(url[len("/uploads/"):])
    candidate = (UPLOAD_DIR / relative).resolve()
    upload_root = UPLOAD_DIR.resolve()
    if not str(candidate).startswith(str(upload_root)):
        return None
    if not candidate.is_file():
        return None
    return candidate


def load_text_from_upload(url: Optional[str], max_chars: int = PRESET_CONTEXT_LIMIT) -> Optional[str]:
    path = resolve_upload_path(url)
    if not path:
        return None
    if path.suffix.lower() not in TEXT_FILE_EXTENSIONS:
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="ignore")
    if path.suffix.lower() == ".json":
        try:
            parsed = json.loads(text)
            text = json.dumps(parsed, ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            pass
    if max_chars and len(text) > max_chars:
        return text[:max_chars] + "\n...（内容已截断）"
    return text


def decode_card_blob(blob: bytes) -> Optional[str]:
    if not blob:
        return ""
    try:
        return blob.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return zlib.decompress(blob).decode("utf-8")
        except Exception:
            return None


def load_character_card_text(url: Optional[str]) -> Optional[str]:
    path = resolve_upload_path(url)
    if not path or path.suffix.lower() not in {".png", ".webp"}:
        return None
    try:
        data = path.read_bytes()
    except OSError:
        return None
    png_signature = b"\x89PNG\r\n\x1a\n"
    if not data.startswith(png_signature):
        return None
    offset = len(png_signature)
    length_data = len(data)
    while offset + 8 <= length_data:
        chunk_length = int.from_bytes(data[offset:offset + 4], "big", signed=False)
        offset += 4
        chunk_type = data[offset:offset + 4]
        offset += 4
        chunk_data = data[offset:offset + chunk_length]
        offset += chunk_length
        offset += 4  # skip CRC

        text_value: Optional[str] = None
        if chunk_type == b"tEXt":
            try:
                keyword_bytes, text_bytes = chunk_data.split(b"\x00", 1)
            except ValueError:
                continue
            keyword = keyword_bytes.decode("latin-1", errors="ignore").strip().lower()
            if keyword in CARD_TEXT_KEYWORDS:
                text_value = text_bytes.decode("utf-8", errors="ignore")
        elif chunk_type == b"zTXt":
            try:
                keyword_bytes, rest = chunk_data.split(b"\x00", 1)
            except ValueError:
                continue
            if not rest:
                continue
            keyword = keyword_bytes.decode("latin-1", errors="ignore").strip().lower()
            if keyword in CARD_TEXT_KEYWORDS:
                compression_method = rest[0]
                compressed = rest[1:]
                try:
                    if compression_method == 0:
                        text_value = zlib.decompress(compressed).decode("utf-8", errors="ignore")
                except Exception:
                    continue
        elif chunk_type == b"iTXt":
            pointer = 0
            null_pos = chunk_data.find(b"\x00", pointer)
            if null_pos == -1:
                continue
            keyword_bytes = chunk_data[pointer:null_pos]
            keyword = keyword_bytes.decode("latin-1", errors="ignore").strip().lower()
            pointer = null_pos + 1
            if pointer + 2 > len(chunk_data):
                continue
            compression_flag = chunk_data[pointer]
            pointer += 1
            compression_method = chunk_data[pointer]
            pointer += 1

            null_pos = chunk_data.find(b"\x00", pointer)
            if null_pos == -1:
                continue
            pointer = null_pos + 1  # skip language tag
            null_pos = chunk_data.find(b"\x00", pointer)
            if null_pos == -1:
                continue
            pointer = null_pos + 1  # skip translated keyword
            text_payload = chunk_data[pointer:]
            if keyword in CARD_TEXT_KEYWORDS:
                if compression_flag == 1 and compression_method == 0:
                    try:
                        text_payload = zlib.decompress(text_payload)
                    except Exception:
                        continue
                text_value = text_payload.decode("utf-8", errors="ignore")
        elif chunk_type == b"chara":
            text_value = decode_card_blob(chunk_data)

        if text_value:
            normalized = text_value.strip()
            if not normalized:
                continue
            try:
                parsed = json.loads(normalized)
                if isinstance(parsed, (dict, list)):
                    return json.dumps(parsed, ensure_ascii=False, indent=2)
            except json.JSONDecodeError:
                pass
            return normalized
    return None


def get_preset_by_id(preset_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not preset_id:
        return None
    presets = DataStore.list_ai_presets()
    for item in presets:
        if item.get("id") == preset_id:
            return item
    return None


def extract_structured_prompt(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    try:
        payload_any = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if not isinstance(payload_any, dict):
        return raw
    payload = cast(Dict[str, Any], payload_any)

    prompts_any = payload.get("prompts")
    if not isinstance(prompts_any, list):
        return raw
    prompts_list_any: List[Any] = cast(List[Any], prompts_any)
    prompt_entries: List[Dict[str, Any]] = []
    for raw_entry in prompts_list_any:
        if not isinstance(raw_entry, dict):
            continue
        entry = cast(Dict[str, Any], raw_entry)
        prompt_entries.append(entry)

    prompt_map: Dict[str, str] = {}
    for entry in prompt_entries:
        identifier = str(entry.get("identifier") or entry.get("name") or "").strip()
        if not identifier:
            continue
        content = entry.get("content")
        if not isinstance(content, str):
            continue
        prompt_map[identifier] = content.strip()

    ordered_sections: List[str] = []
    seen_ids: Set[str] = set()
    order_blocks_any = payload.get("prompt_order")
    if isinstance(order_blocks_any, list):
        order_blocks_list: List[Any] = cast(List[Any], order_blocks_any)
        order_blocks: List[Dict[str, Any]] = []
        for raw_block in order_blocks_list:
            if not isinstance(raw_block, dict):
                continue
            block = cast(Dict[str, Any], raw_block)
            order_blocks.append(block)
        for block in order_blocks:
            order_list_any = block.get("order")
            if not isinstance(order_list_any, list):
                continue
            order_list: List[Any] = cast(List[Any], order_list_any)
            order_items: List[Dict[str, Any]] = []
            for raw_item in order_list:
                if not isinstance(raw_item, dict):
                    continue
                item = cast(Dict[str, Any], raw_item)
                order_items.append(item)
            for item in order_items:
                if not item.get("enabled"):
                    continue
                identifier = str(item.get("identifier") or "").strip()
                if not identifier or identifier in seen_ids:
                    continue
                content = prompt_map.get(identifier, "")
                if content:
                    ordered_sections.append(content)
                    seen_ids.add(identifier)

    if not ordered_sections:
        for identifier, content in prompt_map.items():
            if content and identifier not in seen_ids:
                ordered_sections.append(content)
                seen_ids.add(identifier)

    for key in ("assistant_prefill", "assistant_impersonation"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            ordered_sections.append(value.strip())

    combined = "\n\n".join(section for section in ordered_sections if section)
    return combined.strip() or raw


THINKING_BLOCK_PATTERN = re.compile(r"<thinking>.*?(?:</thinking>|$)", re.IGNORECASE | re.DOTALL)


def sanitize_ai_reply(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return raw
    cleaned = THINKING_BLOCK_PATTERN.sub("", raw).strip()
    return cleaned or raw


def build_system_prompt(preset: Optional[Dict[str, Any]]) -> str:
    sections: List[str] = []
    if preset:
        prompt_text = str(preset.get("prompt", "")).strip()
        if prompt_text:
            sections.append(extract_structured_prompt(prompt_text))
        world_text = load_text_from_upload(preset.get("world_book"))
        if world_text:
            sections.append("【世界观设定】\n" + world_text)
        card_text = load_text_from_upload(preset.get("character_card"))
        if not card_text:
            card_text = load_character_card_text(preset.get("character_card"))
        if card_text:
            sections.append("【角色卡】\n" + card_text)
    combined = "\n\n".join(section for section in sections if section.strip())
    return combined.strip() or DEFAULT_SYSTEM_PROMPT


async def request_chat_completion(messages: List[Dict[str, str]], settings: Dict[str, Any]) -> str:
    api_base = settings.get("api_base")
    api_key = settings.get("api_key")
    model = settings.get("model")
    if not api_base or not api_key or not model:
        raise HTTPException(status_code=503, detail="请先在 AI 对话工作台配置 API 地址、密钥与模型。")

    endpoint = api_base.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0.7
    }
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:  # 增加超时到120秒
            response = await client.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text.strip()
        raise HTTPException(status_code=exc.response.status_code, detail=detail or "AI 接口返回错误") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="AI 接口连接失败，请稍后再试。") from exc

    data = response.json()
    try:
        message = data["choices"][0]["message"]
    except (KeyError, IndexError) as exc:
        raise HTTPException(status_code=502, detail="AI 接口未返回有效内容。") from exc

    message_dict: Dict[str, Any] = cast(Dict[str, Any], message) if isinstance(message, dict) else {}

    content = message_dict.get("content") if message_dict else None
    if isinstance(content, list):
        content_items: List[Any] = cast(List[Any], content)
        parts: List[str] = []
        for raw_item in content_items:
            if isinstance(raw_item, dict):
                item_dict = cast(Dict[str, Any], raw_item)
                if item_dict.get("type") == "text":
                    parts.append(str(item_dict.get("text", "")))
            elif isinstance(raw_item, str):
                parts.append(raw_item)
        content = "".join(parts)
    elif not isinstance(content, str):
        content = str(content) if content is not None else ""

    text = content.strip()
    if not text:
        reasoning_any = message_dict.get("reasoning") if message_dict else None
        if isinstance(reasoning_any, dict):
            reasoning = cast(Dict[str, Any], reasoning_any)
            reasoning_text = reasoning.get("output_text") or reasoning.get("content")
            if isinstance(reasoning_text, str):
                text = reasoning_text.strip()
    return text


def perform_ocr(path: Path) -> str:
    suffix = path.suffix.lower()
    try:
        if suffix == ".pdf":
            text = ocr_utils.extract_pdf_text(path)
            if not text.strip():
                text = ocr_utils.ocr_pdf(path)
        else:
            text = ocr_utils.ocr_image_path(path)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - surface as HTTP error for client clarity
        raise HTTPException(status_code=500, detail="OCR 处理失败，请稍后再试。") from exc

    cleaned = (text or "").strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="未在文件中识别到可翻译文本。")
    return cleaned


async def request_ai_translation(text: str) -> Dict[str, str]:
    settings = DataStore.get_ai_settings()
    api_base = settings.get("api_base")
    api_key = settings.get("api_key")
    model = settings.get("model")
    if not api_base or not api_key or not model:
        raise HTTPException(status_code=503, detail="请先在 AI 对话工作台配置 API 地址、密钥与模型。")

    endpoint = api_base.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    max_chars = 8000
    truncated_text = text if len(text) <= max_chars else text[:max_chars]
    system_prompt = (
        "你是一位专业的翻译，请将提供的 OCR 文本翻译为自然流畅的中文。请严格按照原文进行翻译，而不是只是概括内容。"
        "如果原文已经是中文，请润色并纠正错别字。"
        "请以 JSON 格式输出，形如 {\"title\": \"...\", \"body\": \"...\"}，"
        "title 应该是一句简洁的文档标题，body 为多段落正文，段落之间需要进行换行，不要出现json文件中全部正文都处于body一行。"
        "只能输出 JSON，谨慎避免额外说明。"
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": truncated_text}
    ]
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0.2
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="翻译服务调用失败，请稍后重试。") from exc

    data = response.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise HTTPException(status_code=502, detail="翻译结果解析失败。") from exc

    result = parse_translation_response(content)
    if not result.get("title"):
        result["title"] = "翻译结果"
    if not result.get("body"):
        result["body"] = truncated_text
    return result


async def process_document(path: Path, original_name: Optional[str] = None) -> Dict[str, Any]:
    ocr_text = perform_ocr(path)

    translation = await request_ai_translation(ocr_text)
    title_hint = (original_name or path.stem or "").strip()
    title = translation.get("title", "").strip() or title_hint or "翻译结果"
    translated_text = translation.get("body", "").strip() or ocr_text

    combined_text = f"{title}\n\n{translated_text}".strip()
    safe_title = slugify_filename(title)
    output_path = ocr_utils.write_output(combined_text, OCR_OUTPUT_DIR, safe_title)

    return {
        "title": title,
        "output_url": f"/uploads/ocr/output/{output_path.name}",
        "output_filename": output_path.name,
        "translated_text": translated_text,
        "original_text": ocr_text
    }

@app.post("/api/uploads/{category}")
async def api_upload_file(category: str, file: UploadFile = File(...)) -> Dict[str, Any]:
    config = UPLOAD_CATEGORIES.get(category)
    if not config:
        raise HTTPException(status_code=404, detail="不支持的上传类型")

    original_name = file.filename or "uploaded"
    suffix = Path(original_name).suffix.lower()
    if suffix not in config["extensions"]:
        raise HTTPException(status_code=422, detail="不支持的文件格式")

    target_dir = UPLOAD_DIR / config["folder"]
    target_dir.mkdir(parents=True, exist_ok=True)

    unique_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}{suffix}"
    target_path = target_dir / unique_name

    data = await file.read()
    target_path.write_bytes(data)

    relative_path = (config["folder"] / unique_name) if isinstance(config["folder"], Path) else Path(config["folder"]) / unique_name
    url = f"/uploads/{relative_path.as_posix()}"

    return {
        "url": url,
        "filename": original_name,
        "stored_as": unique_name
    }


@app.get("/", include_in_schema=False)
def get_root() -> FileResponse:
    return serve_page("index.html")


@app.get("/random-number", include_in_schema=False)
def get_random_number_page() -> FileResponse:
    return serve_page("random-number.html")


@app.get("/food-picker", include_in_schema=False)
def get_food_picker_page() -> FileResponse:
    return serve_page("food-picker.html")


@app.get("/calendar", include_in_schema=False)
def get_calendar_page() -> FileResponse:
    return serve_page("calendar.html")


@app.get("/tasks", include_in_schema=False)
def get_tasks_page() -> FileResponse:
    return serve_page("tasks.html")


@app.get("/fortune", include_in_schema=False)
def get_fortune_page() -> FileResponse:
    return serve_page("fortune.html")


@app.get("/ocr", include_in_schema=False)
def get_ocr_page() -> FileResponse:
    return serve_page("ocr.html")


@app.get("/ai-chat", include_in_schema=False)
def get_ai_chat_page() -> FileResponse:
    return serve_page("ai-chat.html")





@app.get("/api/random-number")
def api_random_number(min: int = 1, max: int = 100) -> Dict[str, Union[int, Dict[str, int]]]:
    if min > max:
        raise HTTPException(status_code=422, detail="Parameter 'min' cannot be greater than 'max'.")
    value = random.randint(min, max)
    return {"value": value, "range": {"min": min, "max": max}}


@app.get("/api/random-food")
def api_random_food() -> Dict[str, str]:
    if not MENU_ITEMS:
        raise HTTPException(status_code=500, detail="Food menu is unavailable.")
    choice = random.choice(MENU_ITEMS)
    return choice


@app.get("/api/calendar/overview")
def api_calendar_overview(start: Optional[str] = None, end: Optional[str] = None) -> Dict[str, Any]:
    today = date.today()
    start_date = parse_date(start) if start else today
    end_date = parse_date(end) if end else today + timedelta(days=30)
    if end_date < start_date:
        raise HTTPException(status_code=422, detail="结束日期需晚于开始日期")

    timeline = build_calendar_timeline(start_date, end_date)
    return {
        "range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
        "timeline": timeline,
        "single_events": DataStore.list_single_events(),
        "recurring_events": DataStore.list_recurring_events()
    }


@app.post("/api/calendar/events")
def api_add_single_event(payload: CreateSingleEvent) -> Dict[str, Any]:
    record = DataStore.add_single_event(payload.title, payload.date.isoformat())
    return record


@app.post("/api/calendar/recurring")
def api_add_recurring_event(payload: CreateRecurringEvent) -> Dict[str, Any]:
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=422, detail="结束日期需晚于开始日期")
    record = DataStore.add_recurring_event(
        payload.title,
        payload.start_date.isoformat(),
        payload.end_date.isoformat(),
        payload.weekday
    )
    return record


@app.delete("/api/calendar/events/{event_id}")
def api_delete_single_event(event_id: str) -> Dict[str, Any]:
    deleted = DataStore.clear_single_event(event_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="未找到对应日程")
    return {"status": "ok"}


@app.delete("/api/calendar/recurring/{event_id}")
def api_delete_recurring_event(event_id: str) -> Dict[str, Any]:
    deleted = DataStore.clear_recurring_event(event_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="未找到对应周期日程")
    return {"status": "ok"}


@app.get("/api/tasks")
def api_list_tasks() -> Dict[str, Any]:
    return DataStore.list_tasks()


@app.post("/api/tasks")
def api_add_task(payload: CreateTask) -> Dict[str, Any]:
    if payload.task_type not in {"daily", "temporary"}:
        raise HTTPException(status_code=422, detail="任务类型仅支持 daily 或 temporary")
    record = DataStore.add_task(payload.title, payload.task_type)
    return record


@app.post("/api/tasks/{task_id}/toggle")
def api_toggle_task(task_id: str) -> Dict[str, Any]:
    updated = DataStore.toggle_task(task_id)
    if not updated:
        raise HTTPException(status_code=404, detail="未找到任务")
    return updated


@app.delete("/api/tasks/{task_id}")
def api_delete_task(task_id: str) -> Dict[str, Any]:
    success = DataStore.delete_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="未找到任务")
    return {"status": "ok"}


@app.get("/api/tasks/assistant/history")
def api_get_task_assistant_history(date: Optional[str] = None) -> Dict[str, Any]:
    """获取任务助手的对话历史，支持按日期过滤"""
    target_date = date if date and date != "today" else datetime.now().date().isoformat()
    history = DataStore.list_task_assistant_history(target_date)
    return {"items": history, "date": target_date}


@app.post("/api/tasks/assistant/analyze")
async def api_analyze_tasks() -> Dict[str, Any]:
    """分析当天所有任务并给出优先级建议"""
    settings = DataStore.get_ai_settings()
    missing_fields = [key for key in ("api_base", "api_key", "model") if not settings.get(key)]
    if missing_fields:
        raise HTTPException(status_code=503, detail="请先在 AI 对话工作台配置 API 地址、密钥与模型。")
    
    # 获取当天所有任务
    tasks_data = DataStore.list_tasks()
    daily_tasks = [task for task in tasks_data.get("daily", []) if not task.get("completed")]
    temporary_tasks = [task for task in tasks_data.get("temporary", []) if not task.get("completed")]
    
    if not daily_tasks and not temporary_tasks:
        return {
            "reply": "今天暂无待办任务，尽情享受自由时光吧！",
            "timestamp": datetime.now().isoformat(),
            "task_count": 0
        }
    
    # 构造任务列表文本
    task_text_parts = ["今天的任务清单：\n"]
    if daily_tasks:
        task_text_parts.append("【每日任务】")
        for idx, task in enumerate(daily_tasks, 1):
            task_text_parts.append(f"{idx}. {task['title']}")
    if temporary_tasks:
        if daily_tasks:
            task_text_parts.append("")
        task_text_parts.append("【临时任务】")
        for idx, task in enumerate(temporary_tasks, 1):
            task_text_parts.append(f"{idx}. {task['title']}")
    task_text_parts.append("\n请分析优先级并给出合理的完成顺序建议和执行思路。")
    task_text = "\n".join(task_text_parts)
    
    # 调用 AI
    system_prompt = (
        "你是任务管理助手，擅长根据任务内容判断优先级和依赖关系。"
        "请分析用户的每日任务和临时任务，给出合理的完成顺序建议和执行思路。"
        "回复要简洁实用，直接给出建议，不要过于冗长。"
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task_text}
    ]
    
    try:
        logger.info(f"开始调用AI分析任务，任务数量: {len(daily_tasks) + len(temporary_tasks)}")
        logger.info(f"AI配置 - API Base: {settings.get('api_base')}, Model: {settings.get('model')}")
        reply_text = await request_chat_completion(messages, settings)
        logger.info(f"AI分析完成，回复长度: {len(reply_text)}")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"任务分析失败: {str(exc)}", exc_info=True)
        raise HTTPException(status_code=502, detail="任务分析请求失败，请稍后再试。") from exc
    
    reply = sanitize_ai_reply(reply_text) or "暂时无法生成建议，请稍后再试。"
    
    # 记录到历史
    today = datetime.now().date().isoformat()
    log_entry: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "date": today,
        "timestamp": datetime.now().isoformat(),
        "type": "analyze",
        "user_message": task_text,
        "assistant_reply": reply,
        "task_count": len(daily_tasks) + len(temporary_tasks)
    }
    DataStore.append_task_assistant_log(log_entry)
    
    return {
        "reply": reply,
        "timestamp": datetime.now().isoformat(),
        "task_count": len(daily_tasks) + len(temporary_tasks)
    }


@app.post("/api/tasks/assistant/chat")
async def api_task_assistant_chat(payload: AIChatPayload) -> Dict[str, Any]:
    """任务助手对话接口"""
    settings = DataStore.get_ai_settings()
    missing_fields = [key for key in ("api_base", "api_key", "model") if not settings.get(key)]
    if missing_fields:
        raise HTTPException(status_code=503, detail="请先在 AI 对话工作台配置 API 地址、密钥与模型。")
    
    system_prompt = (
        "你是任务管理助手，擅长根据任务内容判断优先级和依赖关系。"
        "请根据用户的问题提供实用的建议，帮助用户更好地完成任务。"
    )
    
    outgoing: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for message in payload.messages:
        outgoing.append(message.model_dump())
    
    try:
        reply_text = await request_chat_completion(outgoing, settings)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="任务助手对话请求失败，请稍后再试。") from exc
    
    reply = sanitize_ai_reply(reply_text) or "(暂无回复)"
    last_message = payload.messages[-1] if payload.messages else None
    
    # 记录到历史
    today = datetime.now().date().isoformat()
    log_entry: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "date": today,
        "timestamp": datetime.now().isoformat(),
        "type": "chat",
        "user_message": last_message.content if last_message else "",
        "assistant_reply": reply
    }
    DataStore.append_task_assistant_log(log_entry)
    
    return {
        "reply": reply,
        "echo": last_message.model_dump() if last_message else None,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/fortune")
def api_get_fortune_status() -> Dict[str, Any]:
    entry = DataStore.get_today_fortune()
    history = DataStore.list_fortune_history(limit=30)
    return {
        "entry": entry,
        "history": history
    }


@app.post("/api/fortune")
def api_draw_fortune() -> Dict[str, Any]:
    existing = DataStore.get_today_fortune()
    if existing:
        return {
            "entry": existing,
            "locked": True,
            "already_drawn": True
        }

    fortune_source = random.choice(FORTUNE_DECK)
    fortune = {
        "type": fortune_source.get("type", "未知签"),
        "message": fortune_source.get("message", "")
    }
    image = pick_liyin_image()
    quotes_map = get_fortune_quotes()
    quotes = quotes_map.get(fortune["type"], [])
    quote = random.choice(quotes) if quotes else DEFAULT_FORTUNE_QUOTE
    timestamp = datetime.now().isoformat()
    entry: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "date": date.today().isoformat(),
        "fortune": fortune,
        "image": image,
        "quote": quote,
        "timestamp": timestamp
    }
    DataStore.append_fortune_entry(entry)
    return {
        "entry": entry,
        "locked": True,
        "already_drawn": False
    }


@app.get("/api/ai/settings")
def api_get_ai_settings() -> Dict[str, Any]:
    return DataStore.get_ai_settings()


@app.post("/api/ai/settings")
def api_update_ai_settings(payload: UpdateAISettings) -> Dict[str, Any]:
    sanitized = {key: value for key, value in payload.model_dump().items() if value is not None}
    return DataStore.update_ai_settings(sanitized)


@app.get("/api/ai/presets")
def api_list_ai_presets() -> List[Dict[str, Any]]:
    return DataStore.list_ai_presets()


@app.post("/api/ai/presets")
def api_add_ai_preset(payload: AIPresetPayload) -> Dict[str, Any]:
    record = DataStore.add_ai_preset(payload.model_dump())
    return record


@app.delete("/api/ai/presets/{preset_id}")
def api_delete_ai_preset(preset_id: str) -> Dict[str, Any]:
    success = DataStore.delete_ai_preset(preset_id)
    if not success:
        raise HTTPException(status_code=404, detail="未找到聊天预设")
    return {"status": "ok"}


@app.get("/api/ai/history")
def api_get_ai_history() -> Dict[str, Any]:
    return {"items": DataStore.list_ai_history()}


@app.delete("/api/ai/history")
def api_clear_ai_history() -> Dict[str, Any]:
    DataStore.clear_ai_history()
    return {"status": "ok"}


@app.post("/api/ai/chat")
async def api_ai_chat(payload: AIChatPayload) -> Dict[str, Any]:
    settings = DataStore.get_ai_settings()
    missing_fields = [key for key in ("api_base", "api_key", "model") if not settings.get(key)]
    if missing_fields:
        reply = "AI 接口尚未配置，请先在设置面板中填写 API 地址、密钥与模型。"
        last_message = payload.messages[-1] if payload.messages else None
        log_entry: Dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "preset_id": payload.preset_id,
            "messages": [message.model_dump() for message in payload.messages],
            "reply": reply,
            "system_prompt": DEFAULT_SYSTEM_PROMPT
        }
        DataStore.append_ai_chat_log(log_entry)
        return {
            "reply": reply,
            "echo": last_message.model_dump() if last_message else None,
            "timestamp": datetime.now().isoformat()
        }

    preset = get_preset_by_id(payload.preset_id)
    system_prompt = build_system_prompt(preset)
    outgoing: List[Dict[str, str]] = []
    if system_prompt:
        outgoing.append({"role": "system", "content": system_prompt})
    for message in payload.messages:
        outgoing.append(message.model_dump())

    try:
        reply_text = await request_chat_completion(outgoing, settings)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="AI 对话请求失败，请稍后再试。") from exc

    reply = sanitize_ai_reply(reply_text) or "(暂无回复)"
    last_message = payload.messages[-1] if payload.messages else None
    log_entry = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "preset_id": payload.preset_id,
        "preset_name": preset.get("name") if preset else None,
        "system_prompt": system_prompt,
        "messages": [message.model_dump() for message in payload.messages],
        "model_messages": outgoing,
        "reply": reply,
        "raw_reply": reply_text
    }
    DataStore.append_ai_chat_log(log_entry)

    return {
        "reply": reply,
        "echo": last_message.model_dump() if last_message else None,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/ocr/translate")
async def api_ocr_translate(file: UploadFile = File(...)) -> Dict[str, Any]:
    filename = file.filename or "uploaded"
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_OCR_EXTENSIONS:
        raise HTTPException(status_code=422, detail="目前仅支持图片或 PDF：PNG、JPG、JPEG、WEBP、BMP、TIFF、PDF。")

    unique_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}{suffix}"
    source_path = OCR_INPUT_DIR / unique_name
    data = await file.read()
    source_path.write_bytes(data)

    result = await process_document(source_path, filename)
    return result


@app.post("/api/ocr/process-pending")
async def api_ocr_process_pending() -> Dict[str, Any]:
    processed: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    skipped: List[str] = []

    for path in sorted(OCR_INPUT_DIR.glob("*")):
        if not path.is_file() or path.suffix.lower() not in ALLOWED_OCR_EXTENSIONS:
            continue
        marker = path.with_suffix(path.suffix + ".done")
        if marker.exists():
            skipped.append(path.name)
            continue
        try:
            result = await process_document(path, path.name)
            processed.append({
                "input": path.name,
                "output": result["output_filename"],
                "title": result["title"]
            })
            marker.write_text(result["output_filename"], encoding="utf-8")
        except HTTPException as exc:
            errors.append({
                "input": path.name,
                "status": exc.status_code,
                "detail": exc.detail
            })
        except Exception as exc:
            errors.append({
                "input": path.name,
                "status": 500,
                "detail": str(exc)
            })

    return {
        "processed": processed,
        "errors": errors,
        "skipped": skipped
    }

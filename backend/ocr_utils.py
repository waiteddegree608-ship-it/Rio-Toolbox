from __future__ import annotations

import os
import platform
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Generator, List, Optional, cast

import pypdfium2 as pdfium  # type: ignore[import]
from PIL import Image

try:
    import pytesseract  # type: ignore[import]
    from pytesseract import TesseractError, TesseractNotFoundError  # type: ignore[import]
except ModuleNotFoundError:  # pragma: no cover
    pytesseract = None  # type: ignore[assignment]
    TesseractError = TesseractNotFoundError = RuntimeError  # type: ignore[assignment]
    _image_to_string: Optional[Callable[..., str]] = None
else:  # pragma: no cover - typing fallback
    pytesseract = cast(Any, pytesseract)
    _image_to_string = cast(Callable[..., str], pytesseract.image_to_string)


if pytesseract is not None:
    default_path = Path("C:/Program Files/Tesseract-OCR/tesseract.exe")
    if platform.system() == "Windows" and default_path.exists():
        pytesseract.pytesseract.tesseract_cmd = str(default_path)
    custom_cmd = os.environ.get("TESSERACT_CMD")
    if custom_cmd:
        pytesseract.pytesseract.tesseract_cmd = custom_cmd


def ocr_image(image: Image.Image) -> str:
    if _image_to_string is None:
        raise RuntimeError("未检测到 Tesseract OCR 引擎，请确认已安装 pytesseract 与 Tesseract。")
    try:
        text = _image_to_string(image, lang="chi_sim+eng")
        if text.strip():
            return text
        return _image_to_string(image, lang="eng")
    except TesseractNotFoundError as exc:  # pragma: no cover - runtime guard
        raise RuntimeError("未检测到 Tesseract 可执行文件，请确认已正确安装。") from exc
    except TesseractError as exc:
        raise RuntimeError("Tesseract OCR 处理失败，请检查语言包是否完整。") from exc


def ocr_image_path(image_path: Path) -> str:
    with Image.open(image_path) as img:
        return ocr_image(img)


def pdf_pages(pdf_path: Path, dpi: int = 200) -> Generator[Image.Image, None, None]:
    scale = float(dpi) / 72.0
    document: Any = pdfium.PdfDocument(str(pdf_path))  # type: ignore[attr-defined]
    try:
        page_count = int(len(document))
        for index in range(page_count):
            page: Any = document.get_page(index)  # type: ignore[attr-defined]
            try:
                pil_image_any = page.render_to(  # type: ignore[attr-defined]
                    pdfium.BitmapConv.pil_image,  # type: ignore[attr-defined]
                    scale=scale,
                )
            finally:
                page.close()
            pil_image = cast(Image.Image, pil_image_any)
            if pil_image.mode != "RGB":
                pil_image = pil_image.convert("RGB")
            yield pil_image
    finally:
        document.close()  # type: ignore[attr-defined]


def ocr_pdf(pdf_path: Path, dpi: int = 200) -> str:
    texts: List[str] = []
    for page_image in pdf_pages(pdf_path, dpi=dpi):
        page_text = ocr_image(page_image)
        if page_text:
            texts.append(page_text)
    return "\n\n".join(texts)


def extract_pdf_text(pdf_path: Path) -> str:
    document: Any = pdfium.PdfDocument(str(pdf_path))  # type: ignore[attr-defined]
    try:
        page_count = int(len(document))
        texts: List[str] = []
        for index in range(page_count):
            page: Any = document.get_page(index)  # type: ignore[attr-defined]
            try:
                text_page = page.get_textpage()  # type: ignore[attr-defined]
                try:
                    content = text_page.get_text_range()  # type: ignore[attr-defined]
                finally:
                    text_page.close()
            finally:
                page.close()
            text_value = str(content).strip() if content else ""
            if text_value:
                texts.append(text_value)
        return "\n\n".join(texts)
    finally:
        document.close()  # type: ignore[attr-defined]


def write_output(text: str, output_dir: Path, stem: str, suffix: str = ".txt") -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    file_name = f"{stem}_{timestamp}{suffix}"
    target = output_dir / file_name
    target.write_text(text, encoding="utf-8")
    return target
"""llm_wiki/ingest.py —— 摄入管线

扫描 KNOWLEDGE_DIR（rag/knowledge）下的 *.md：
    1. 按文件 hash 判断是否变更（manifest.json 增量，未变更跳过）
    2. 变更的文件交给 WikiCompiler 编译成 wiki 页面
    3. 页面写入 WIKI_DIR/<源文档名>/，更新 manifest.json 与 index.md

用法：
    from llm_wiki.ingest import ingest
    result = ingest(rebuild=False)   # {"compiled": n, "skipped": n, "failed": [...]}
"""
import hashlib
import json
import re
import time
from pathlib import Path
from typing import List

from llm_wiki.compiler import WikiCompiler
from llm_wiki.config import KNOWLEDGE_DIR, WIKI_DIR

MANIFEST_FILE = WIKI_DIR / "manifest.json"
INDEX_FILE = WIKI_DIR / "index.md"


def _file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _slugify(name: str) -> str:
    """标题/文件名 → 安全 slug（保留中文与字母数字，其余转下划线）。"""
    s = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", name, flags=re.UNICODE)
    return s.strip("_") or "page"


def list_sources() -> List[Path]:
    """rag/knowledge 下的 md 文件（只收 .md，符合 llm_wiki 定位）。"""
    if not KNOWLEDGE_DIR.is_dir():
        return []
    return sorted(
        p for p in KNOWLEDGE_DIR.iterdir()
        if p.is_file() and p.suffix.lower() == ".md"
    )


def load_manifest() -> dict:
    if MANIFEST_FILE.exists():
        return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    return {}


def save_manifest(manifest: dict):
    WIKI_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_FILE.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _write_pages(source_stem: str, pages: List[dict]) -> List[str]:
    """把页面列表写入 WIKI_DIR/<source_stem>/，先清理旧页面，返回相对路径列表。"""
    out_dir = WIKI_DIR / source_stem
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.md"):
        old.unlink()

    page_files = []
    for i, p in enumerate(pages):
        slug = _slugify(p["title"]) or f"page_{i}"
        fname = f"{i:02d}-{slug}.md"
        front_matter = (
            "---\n"
            f"title: {p['title']}\n"
            f"source: {source_stem}\n"
            f"tags: [{', '.join(p['tags'])}]\n"
            "---\n\n"
        )
        body = f"# {p['title']}\n\n{p['summary']}\n\n{p['content']}\n"
        (out_dir / fname).write_text(front_matter + body, encoding="utf-8")
        page_files.append(f"{source_stem}/{fname}")
    return page_files


def _write_index(manifest: dict):
    """生成 index.md：wiki 总览，按源文档分组列出页面链接。"""
    lines = ["# LLM Wiki 索引\n", "来源：rag/knowledge/*.md（由 llm_wiki 编译）\n"]
    for source, info in manifest.items():
        lines.append(f"\n## {source}\n")
        for pf in info["pages"]:
            title = Path(pf).stem.split("-", 1)[-1]
            rel = pf.replace("\\", "/")
            lines.append(f"- [{title}]({rel})")
    INDEX_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ingest(rebuild: bool = False) -> dict:
    """摄入 rag/knowledge/*.md。

    rebuild=True 时忽略 manifest 全量重编；否则按文件 hash 增量（未变更跳过）。
    """
    manifest = {} if rebuild else load_manifest()
    compiler = WikiCompiler()
    result = {"compiled": 0, "skipped": 0, "failed": []}

    for src in list_sources():
        h = _file_hash(src)
        stem = src.stem
        if not rebuild and manifest.get(stem, {}).get("hash") == h:
            result["skipped"] += 1
            continue

        text = src.read_text(encoding="utf-8")
        try:
            pages = compiler.compile(stem, text)
            if not pages:
                raise RuntimeError("编译结果为空（模型可能未按要求返回 JSON）")
            page_files = _write_pages(stem, pages)
            manifest[stem] = {
                "hash": h,
                "pages": page_files,
                "compiled_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            result["compiled"] += 1
        except Exception as e:  # noqa: BLE001 —— 单个文件失败不阻断整体
            result["failed"].append({"file": str(src), "error": str(e)})

    save_manifest(manifest)
    _write_index(manifest)
    return result

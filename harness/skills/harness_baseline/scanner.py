"""Scan baseline / target HTML 抽取 sidebar 结构.

v0.2 改进 (基于 Periscope dogfood retro 2026-05-23):
- top_level_only: 识别 sub-list / submenu，子项进 children 不平级
- _clean_label: 剥末尾装饰符 (▸ ▾ ►) / new 后缀 / 折叠空格
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse


@dataclass
class SidebarItem:
    id: str = ""
    label: str = ""
    href: str = ""
    metrics: list[str] = field(default_factory=list)
    table_headers: list[str] = field(default_factory=list)
    children: list["SidebarItem"] = field(default_factory=list)


@dataclass
class ScanResult:
    source: str
    sidebar: list[SidebarItem]
    raw_titles: list[str] = field(default_factory=list)
    raw_table_headers: list[str] = field(default_factory=list)


DEFAULT_SIDEBAR_CANDIDATES = [
    ".el-menu",
    "nav.sidebar",
    "[class*=sidebar]",
    ".side-nav",
    ".main-nav",
    "nav",
    "[role=navigation]",
    "#sidebar",
]

PERISCOPE_TAB_CANDIDATES = [
    ".tabs",
    "[class*=tab-list]",
    "ul.tabs",
]


def scan_baseline(
    source: str,
    sidebar_selector: Optional[str] = None,
    top_level_only: bool = False,
) -> ScanResult:
    """Scan reference implementation. URL or local HTML path.

    Args:
        source: URL 或本地 HTML 路径
        sidebar_selector: CSS selector，None 时自动检测
        top_level_only: v0.2 只抽顶层 sidebar 项，sub-list 项进 children
    """
    parsed = urlparse(source)
    if parsed.scheme in ("http", "https"):
        return _scan_url(source, sidebar_selector, top_level_only)
    return _scan_local_html(source, sidebar_selector, top_level_only)


def scan_target(
    source: str,
    sidebar_selector: Optional[str] = None,
    top_level_only: bool = False,
) -> ScanResult:
    return scan_baseline(source, sidebar_selector, top_level_only)


def _scan_local_html(
    path_str: str,
    sidebar_selector: Optional[str],
    top_level_only: bool,
) -> ScanResult:
    try:
        from bs4 import BeautifulSoup  # type: ignore
    except ImportError as e:
        raise ImportError(
            "harness-baseline requires beautifulsoup4. "
            "Install: pip install beautifulsoup4"
        ) from e

    path = Path(path_str)
    if not path.exists():
        raise FileNotFoundError(f"target html not found: {path}")
    html = path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")

    candidates = (
        [sidebar_selector]
        if sidebar_selector
        else DEFAULT_SIDEBAR_CANDIDATES + PERISCOPE_TAB_CANDIDATES
    )
    nav = None
    for sel in candidates:
        if not sel:
            continue
        nav = soup.select_one(sel)
        if nav is not None:
            break

    sidebar_items: list[SidebarItem] = []
    if nav is not None:
        sidebar_items = _extract_tree(nav, top_level_only=top_level_only)
    else:
        for a in soup.select("a[data-tab]"):
            label = _clean_label(a.get_text(strip=True))
            if not label or len(label) > 80:
                continue
            sidebar_items.append(
                SidebarItem(
                    id=a.get("data-tab", "") or "",
                    label=label,
                    href=a.get("href", "") or "",
                )
            )

    raw_titles = [
        e.get_text(strip=True)
        for e in soup.select("h1, h2, h3, h4, .title, .chart-title, .el-card__header")
        if e.get_text(strip=True) and len(e.get_text(strip=True)) < 150
    ][:50]
    raw_table_headers = [
        e.get_text(strip=True)
        for e in soup.select("table th, .el-table__header th")
        if e.get_text(strip=True) and len(e.get_text(strip=True)) < 60
    ][:80]

    return ScanResult(
        source=str(path),
        sidebar=sidebar_items,
        raw_titles=raw_titles,
        raw_table_headers=raw_table_headers,
    )


def _scan_url(url: str, sidebar_selector: Optional[str], top_level_only: bool) -> ScanResult:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError as e:
        raise ImportError(
            "URL mode requires playwright. "
            "Install: pip install 'harness-core[playwright]' "
            "and run: playwright install chromium"
        ) from e

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 900})
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(1000)

        candidates = (
            [sidebar_selector] if sidebar_selector else DEFAULT_SIDEBAR_CANDIDATES
        )

        nav_data = page.evaluate(
            """(candidates) => {
                let nav = null;
                for (const sel of candidates) {
                    if (!sel) continue;
                    nav = document.querySelector(sel);
                    if (nav) break;
                }
                if (!nav) return null;
                const items = [];
                nav.querySelectorAll('a').forEach(el => {
                    const text = (el.textContent || '').replace(/\\s+/g, ' ').replace(/new\\d*/g, '').trim();
                    if (!text || text.length > 80) return;
                    items.push({ text, href: el.getAttribute('href') || '' });
                });
                return { items };
            }""",
            candidates,
        )

        raw_titles = page.evaluate(
            """() => [...document.querySelectorAll('h1, h2, h3, h4, .title, .chart-title, .el-card__header')]
                .map(e => (e.textContent || '').replace(/\\s+/g, ' ').trim())
                .filter(t => t && t.length < 150).slice(0, 50)"""
        )
        raw_ths = page.evaluate(
            """() => [...document.querySelectorAll('table th, .el-table__header th')]
                .map(e => (e.textContent || '').replace(/\\s+/g, ' ').trim())
                .filter(t => t && t.length < 60).slice(0, 80)"""
        )

        browser.close()

    sidebar_items: list[SidebarItem] = []
    if nav_data:
        for it in nav_data["items"]:
            sidebar_items.append(
                SidebarItem(label=_clean_label(it["text"]), href=it.get("href", "") or "")
            )

    return ScanResult(
        source=url,
        sidebar=sidebar_items,
        raw_titles=raw_titles or [],
        raw_table_headers=raw_ths or [],
    )


def _is_inside_sublist(el) -> bool:
    """v0.2: 判断 el 是否在 sub-list / submenu 区域内."""
    parent = el.parent
    while parent is not None and getattr(parent, "name", None):
        cls = parent.get("class") if hasattr(parent, "get") else None
        if cls:
            cls_str = " ".join(cls) if isinstance(cls, list) else str(cls)
            if any(k in cls_str for k in ("sub-list", "submenu")):
                return True
        parent = parent.parent
    return False


def _extract_tree(nav, top_level_only: bool = False) -> list[SidebarItem]:
    """v0.2: 从 nav 元素抽取 sidebar items.

    若 top_level_only=True：sub-list 内的 a 收为最近顶层项的 children；
    否则保持 v0.1 行为（平级展开）以保兼容.
    """
    items: list[SidebarItem] = []
    seen_labels: set[str] = set()

    if top_level_only:
        sub_list_anchors: dict[str, list[SidebarItem]] = {}
        for a in nav.find_all("a"):
            label = _clean_label(a.get_text(strip=True))
            if not label or len(label) > 80:
                continue
            href = a.get("href", "") or ""
            data_tab = a.get("data-tab", "") or ""
            inside_sub = _is_inside_sublist(a)
            if inside_sub:
                if data_tab and data_tab in sub_list_anchors:
                    if label not in {c.label for c in sub_list_anchors[data_tab]}:
                        sub_list_anchors[data_tab].append(SidebarItem(label=label, href=href))
                continue
            if label in seen_labels:
                continue
            seen_labels.add(label)
            item = SidebarItem(id=data_tab, label=label, href=href)
            items.append(item)
            if data_tab:
                sub_list_anchors[data_tab] = item.children
    else:
        for el in nav.find_all(["a", "li"]):
            label = _clean_label(el.get_text(strip=True))
            if not label or len(label) > 80:
                continue
            if label in seen_labels:
                continue
            seen_labels.add(label)
            items.append(
                SidebarItem(
                    label=label,
                    href=el.get("href", "") if el.name == "a" else "",
                )
            )
    return items


def _clean_label(text: str) -> str:
    """v0.2: 清理 label（剥 toggle 字符 / new 后缀 / 折叠空格）."""
    if not text:
        return ""
    import re
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"new\d*$", "", text).strip()
    text = text.rstrip("▸▾►▼▲ ")
    return text

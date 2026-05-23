"""Scan baseline / target HTML 抽取 sidebar 结构.

MVP: 静态 HTML 解析（BeautifulSoup）.
后续: URL 模式 via playwright（可选 dep）.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse


@dataclass
class SidebarItem:
    """Sidebar 中的一项（leaf 或 group）."""
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


# 常见 sidebar selector 候选（按优先级）
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

# Periscope 风格：自定义 tab nav
PERISCOPE_TAB_CANDIDATES = [
    ".tabs",
    "[class*=tab-list]",
    "ul.tabs",
]


def scan_baseline(
    source: str,
    sidebar_selector: Optional[str] = None,
) -> ScanResult:
    """Scan reference implementation. URL or local HTML path."""
    parsed = urlparse(source)
    if parsed.scheme in ("http", "https"):
        return _scan_url(source, sidebar_selector)
    return _scan_local_html(source, sidebar_selector)


def scan_target(
    source: str,
    sidebar_selector: Optional[str] = None,
) -> ScanResult:
    """Same as scan_baseline; just semantic alias for 'current implementation'."""
    return scan_baseline(source, sidebar_selector)


def _scan_local_html(path_str: str, sidebar_selector: Optional[str]) -> ScanResult:
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
    used_selector = None
    for sel in candidates:
        if not sel:
            continue
        nav = soup.select_one(sel)
        if nav is not None:
            used_selector = sel
            break

    sidebar_items: list[SidebarItem] = []
    if nav is not None:
        sidebar_items = _extract_tree(nav)
    else:
        # Fallback: 扫所有 [data-tab] 链接（Periscope 风格）
        for a in soup.select("a[data-tab]"):
            label = a.get_text(strip=True)
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


def _scan_url(url: str, sidebar_selector: Optional[str]) -> ScanResult:
    """URL 模式 - 用 playwright 抓动态 SPA。可选依赖."""
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
            [sidebar_selector]
            if sidebar_selector
            else DEFAULT_SIDEBAR_CANDIDATES
        )

        nav_data = page.evaluate(
            """(candidates) => {
                let nav = null;
                let used = null;
                for (const sel of candidates) {
                    if (!sel) continue;
                    nav = document.querySelector(sel);
                    if (nav) { used = sel; break; }
                }
                if (!nav) return null;
                const items = [];
                nav.querySelectorAll('a, li').forEach(el => {
                    const text = (el.textContent || '').replace(/\\s+/g, ' ').replace(/new\\d*/g, '').trim();
                    if (!text || text.length > 80) return;
                    items.push({ text, href: el.getAttribute('href') || '' });
                });
                return { used, items };
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
                SidebarItem(
                    label=it["text"],
                    href=it.get("href", "") or "",
                )
            )

    return ScanResult(
        source=url,
        sidebar=sidebar_items,
        raw_titles=raw_titles or [],
        raw_table_headers=raw_ths or [],
    )


def _extract_tree(nav) -> list[SidebarItem]:
    """从 BeautifulSoup nav 元素抽出 sidebar items（一层展平 MVP）."""
    items: list[SidebarItem] = []
    seen_labels: set[str] = set()
    for el in nav.find_all(["a", "li"]):
        label = el.get_text(strip=True)
        if not label or len(label) > 80:
            continue
        # 去重（li 包 a 时只算一次）
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

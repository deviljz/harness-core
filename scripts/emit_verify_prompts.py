"""Emit each fixture's review prompt to a file for external dispatch."""
from pathlib import Path
import json
from harness.verify.runner import _load_fixture, _build_prompt, _load_review_template

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tmp_verify_prompts"
OUT.mkdir(exist_ok=True)

fixtures = []
for d in (ROOT / "tests/fixtures/regression").iterdir():
    if d.is_dir():
        fixtures.append(("regression", d))
for d in (ROOT / "tests/fixtures/template_project").iterdir():
    if d.is_dir() and d.name.startswith("case_"):
        fixtures.append(("template", d))

template = _load_review_template()
manifest = []
for suite, fdir in sorted(fixtures, key=lambda x: x[1].name):
    fx = _load_fixture(fdir)
    prompt = _build_prompt(fx, template)
    out_path = OUT / f"{fdir.name}.prompt.txt"
    out_path.write_text(prompt, encoding="utf-8")
    manifest.append({
        "name": fdir.name,
        "suite": suite,
        "prompt_path": str(out_path),
        "expected": fx.expected,
    })

(OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"wrote {len(manifest)} prompts to {OUT}")

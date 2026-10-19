"""Build reports/labN-*.pdf from reports/labN-checklist.md and PNGs in reports/screens/лабN/.

Usage:  python reports/build_report.py 3          (or 4, or 3 4)
        python reports/build_report.py 3 --check  # only list missing screenshots / empty texts
Needs:  pip install reportlab pillow   (fonts: macOS Arial / Courier New from /System/Library/Fonts/Supplemental)
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCREENS_ROOT = HERE / "screens"
REPO = "https://github.com/MarcoGr11/DevOps"
STUDENT = "MarcoGr"
PT_PER_PX = 0.25  # ~ widest Retina terminal shot (2100 px) across the A4 text width

LABS = {
    "3": {
        "pdf": "lab3-kubernetes.pdf",
        "title": "Лабораторна робота №3. Розгортання власного застосунку в Kubernetes",
        "intro": (
            "У namespace `coworking-booking` розгорнуто систему бронювання коворкінгу: api (Django REST, 2 репліки), "
            "worker (2 репліки) і PostgreSQL з томом PVC, налаштування в ConfigMap, паролі в Secret, доступ ззовні "
            "через Ingress `booking.local`. Середовище: minikube, Kubernetes v1.37.0 (kubectl v1.37.1). "
            "Образи: `ghcr.io/marcogr11/devops-api:1.0.0` і `:1.1.0` (у 1.1.0 змінюється поле `version` "
            "у відповіді `/api/health/`), worker — `ghcr.io/marcogr11/devops-worker:1.0.0`."
        ),
        "conclusion": (
            "Застосунок розгорнуто в minikube з маніфестів, а значення з ConfigMap і Secret потрапили в контейнер "
            "api (хеші паролів у Secret і в поді збігаються). Показано самовідновлення після видалення пода, "
            "масштабування до 4 реплік із розподілом запитів, rolling update на 1.1.0 без жодної помилки серед 708 "
            "запитів і відкат на 1.0.0. На прикладі неіснуючого тегу 9.9.9 розібрано діагностику через get pods, "
            "describe, events, logs і exec: старі поди продовжували обслуговувати запити, поки помилку не виправили."
        ),
    },
    "4": {
        "pdf": "lab4-helm.pdf",
        "title": "Лабораторна робота №4. Пакування застосунку в Helm-чарт",
        "intro": (
            "Маніфести лаби №3 перенесено в Helm-чарт `chart/` (booking 0.1.0, appVersion 1.0.0): образи, "
            "репліки, ресурси, ConfigMap, Secret та Ingress-хост винесено у `values.yaml`, окремі значення для "
            "середовищ — у `values-dev.yaml` і `values-prod.yaml`. До чарта додано pre-upgrade hook "
            "(Job перевірки БД) і `helm test`. Середовище: minikube, Kubernetes v1.37.0, Helm v3.22.0; "
            "реліз `booking` у namespace `coworking-booking`."
        ),
        "conclusion": (
            "Чарт рендериться для dev і prod без встановлення, значення перекриваються в порядку "
            "values.yaml < -f < --set, а реліз пройшов повний цикл: install, два upgrade, history, rollback, "
            "test і uninstall. Набір об'єктів у чарті той самий, що в лабі №3, але з kubectl кожен файл "
            "застосовувався окремо, значення для середовищ доводилось правити вручну, а історія велась лише для "
            "одного Deployment. Helm керує всім застосунком як одним релізом: кожна ревізія зберігається в "
            "Secret кластера, rollback повертає всі об'єкти разом, а uninstall прибирає їх однією командою."
        ),
    },
}

ITEM_RE = re.compile(r"^### (\S+\.png) — (.+)$")
FIELDS = {"Що робимо": "what", "Що робилось": "what", "Підпис": "caption", "Що видно": "why", "Пояснення": "why"}
FIELD_RE = re.compile(r"^\*\*(.+?):\*\*\s*(.*)$")


def parse(md_path):
    """Return [(section, [item, ...])]; item = {png, title, what, caption, why}. Code blocks and other fields are skipped."""
    sections, item, field, in_code = [], None, None, False
    for line in md_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if line.startswith("## "):
            sections.append((line[3:].strip(), []))
            item = field = None
        elif m := ITEM_RE.match(line):
            item = {"png": m[1], "title": m[2].strip(), "what": "", "caption": "", "why": ""}
            sections[-1][1].append(item)
            field = None
        elif item is None:
            continue
        elif m := FIELD_RE.match(line):
            field = FIELDS.get(m[1])
            if field:
                item[field] = m[2].strip()
        elif line.startswith(("---", ">")) or not line.strip():
            field = None if line.startswith(("---", ">")) else field
        elif field:
            item[field] += " " + line.strip()
    return [(s, items) for s, items in sections if items]


def build(lab, check_only):
    meta = LABS[lab]
    screens = SCREENS_ROOT / f"лаб{lab}"
    sections = parse(HERE / f"lab{lab}-checklist.md")
    items = [it for _, its in sections for it in its]
    missing = [it["png"] for it in items if not (screens / it["png"]).is_file()]
    empty = [it["png"] for it in items if not it["why"].strip()]
    print(f"lab {lab}: {len(items)} screenshots expected, {len(missing)} missing, {len(empty)} without 'Що видно'")
    for p in missing:
        print(f"  missing: {screens.relative_to(HERE.parent) / p}")
    for p in empty:
        print(f"  no text: {p}")
    if check_only or missing or empty:
        return not (missing or empty)

    from io import BytesIO
    from xml.sax.saxutils import escape

    from PIL import Image as PILImage

    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer

    fonts = Path("/System/Library/Fonts/Supplemental")
    pdfmetrics.registerFont(TTFont("Body", str(fonts / "Arial.ttf")))
    pdfmetrics.registerFont(TTFont("Bold", str(fonts / "Arial Bold.ttf")))
    pdfmetrics.registerFont(TTFont("Mono", str(fonts / "Courier New.ttf")))

    body = ParagraphStyle("body", fontName="Body", fontSize=10, leading=13, spaceAfter=3)
    h1 = ParagraphStyle("h1", fontName="Bold", fontSize=13, leading=16, spaceBefore=6, spaceAfter=4)
    h2 = ParagraphStyle("h2", fontName="Bold", fontSize=11, leading=14, spaceBefore=8, spaceAfter=2)
    caption = ParagraphStyle("cap", parent=body, fontSize=8.5, leading=11, alignment=TA_CENTER,
                             textColor="#555555", spaceBefore=2)
    title = ParagraphStyle("title", parent=h1, fontSize=15, leading=19, spaceBefore=0)
    meta_style = ParagraphStyle("meta", parent=body, textColor="#333333")

    def split(im):
        """Cut at the blank pixel row closest to the middle, so no text line is sliced."""
        mid = im.height // 2
        for d in range(mid):
            for y in (mid - d, mid + d):
                lo, hi = im.crop((0, y, im.width, y + 1)).convert("L").getextrema()
                if hi - lo < 10:
                    return [im.crop((0, 0, im.width, y)), im.crop((0, y, im.width, im.height))]
        return [im]

    def p(text, style=body):
        return Paragraph(re.sub(r"`([^`]+)`", r'<font name="Mono">\1</font>', escape(text)), style)

    doc = SimpleDocTemplate(str(HERE / meta["pdf"]), pagesize=A4, leftMargin=1.3 * cm, rightMargin=1.3 * cm,
                            topMargin=1.2 * cm, bottomMargin=1.2 * cm, title=meta["title"], author=STUDENT)
    max_w, max_h = doc.width, doc.height * 0.8

    story = [p(meta["title"], title),
             p(f"Дисципліна: «Технології DevOps» · Студент: {STUDENT}", meta_style),
             Paragraph(f'Репозиторій: <link href="{REPO}" color="blue">{REPO}</link>', meta_style),
             Spacer(1, 4)]
    if meta["intro"]:
        story.append(p(meta["intro"]))

    n = 0
    for section, its in sections:
        head = [p(section, h1)]  # kept with the first item so a heading never ends a page
        for it in its:
            n += 1
            parts = [PILImage.open(screens / it["png"]).convert("RGB")]
            # same pt-per-px for every screenshot, so terminal text has one size
            scale = min(PT_PER_PX, max_w / parts[0].width)
            if parts[0].height * scale > doc.height / 2:  # tall: cut in two between terminal lines to fill pages
                parts = split(parts[0])
            imgs = []
            for part in parts:
                buf = BytesIO()
                part.save(buf, "PNG")
                imgs.append(Image(buf, part.width * scale, part.height * scale))
            cap = p(f"Рис. {n}. {it['caption'] or it['title']}", caption)
            story.append(KeepTogether(head + [p(it["title"], h2), p(it["what"]), imgs[0]] + ([cap] if len(imgs) == 1 else [])))
            if len(imgs) > 1:
                story.append(KeepTogether([imgs[1], cap]))
            story.append(p(it["why"]))  # may flow to the next page instead of pushing the whole item there
            head = []
    story += [p("Висновок", h1), p(meta["conclusion"])]
    doc.build(story)
    print(f"  written: reports/{meta['pdf']} ({n} screenshots)")
    return True


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--check"]
    if not args or any(a not in LABS for a in args):
        sys.exit(__doc__)
    ok = all([build(lab, "--check" in sys.argv) for lab in args])
    sys.exit(0 if ok else 1)

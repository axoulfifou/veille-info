import os
import re
import time
import glob
import pathlib
import datetime as dt
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from dateutil import parser as dateparser

import requests
import feedparser
from bs4 import BeautifulSoup

# ------------------------------------
# Config générale
# ------------------------------------
PARIS = ZoneInfo("Europe/Paris")
NOW = dt.datetime.now(PARIS)
DATE = NOW.date()

RECENT_HOURS = 36
MAX_TOTAL_ITEMS = 9
MAX_PER_CATEGORY = 3

# Flux par catégories (ajuste comme tu veux)
FEEDS = {
    "Réseau": [
        "https://blog.cloudflare.com/rss/",
        "https://www.juniper.net/us/en/insights/blogs/rss.xml",
    ],
    "Système/Linux": [
        "https://lwn.net/headlines/newrss",
        "https://www.phoronix.com/rss.php",
    ],
    "Python/Dev": [
        "https://blog.python.org/feeds/posts/default?alt=rss",
        "https://pypi.org/rss/updates.xml",
    ],
    "Bases de données": [
        "https://www.postgresql.org/news.rss",
        "https://dev.mysql.com/feeds/news-and-events.xml",
    ],
    "Virtualisation": [
        "https://virtuallyghetto.com/feed",
        "https://www.virtualizationhowto.com/feed/",
    ],
    "Cybersécurité": [
        "https://www.bleepingcomputer.com/feed/",
        "https://www.cisa.gov/cybersecurity-advisories/all.xml",
    ],
    "DevOps": [
        "https://kubernetes.io/feed.xml",
        "https://www.docker.com/blog/feed/",
        "https://github.blog/feed/",
    ],
}

# Ordre d'affichage des sections
ORDER = [
    "Cybersécurité",
    "DevOps",
    "Réseau",
    "Système/Linux",
    "Python/Dev",
    "Bases de données",
    "Virtualisation",
]

# ------------------------------------
# Utilitaires
# ------------------------------------
FR_DAYS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
FR_MONTHS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre"
]

def fr_date(d: dt.date) -> str:
    wd = FR_DAYS[d.weekday()]
    m = FR_MONTHS[d.month - 1]
    return f"{wd} {d.day:02d} {m} {d.year}"

def strip_html(s: str) -> str:
    if not s:
        return ""
    soup = BeautifulSoup(s, "html.parser")
    txt = soup.get_text(" ")
    return re.sub(r"\s+", " ", txt).strip()

def entry_dt(e):
    # essaie plusieurs champs (RSS variés)
    for key in ("published", "updated", "created"):
        val = getattr(e, key, None)
        if val:
            try:
                return dateparser.parse(val).astimezone(PARIS)
            except Exception:
                pass
    for key in ("published_parsed", "updated_parsed"):
        val = getattr(e, key, None)
        if val:
            try:
                return dt.datetime.fromtimestamp(time.mktime(val), PARIS)
            except Exception:
                pass
    return None

def recent_enough(d) -> bool:
    if not d:
        return False
    delta = NOW - d
    return -2 * 3600 <= delta.total_seconds() <= RECENT_HOURS * 3600

def get_media(entry):
    # récupère 1 miniature si dispo
    media_url = None
    if getattr(entry, "media_thumbnail", None):
        try:
            media_url = entry.media_thumbnail[0].get("url")
        except Exception:
            pass
    if not media_url and getattr(entry, "media_content", None):
        try:
            media_url = entry.media_content[0].get("url")
        except Exception:
            pass
    return media_url

# ------------------------------------
# Collecte & sélection
# ------------------------------------
def collect():
    items = []
    for cat, urls in FEEDS.items():
        for url in urls:
            try:
                feed = feedparser.parse(url)
                source = strip_html(getattr(feed.feed, "title", "")) or urlparse(url).netloc
                for e in feed.entries[:30]:
                    pub = entry_dt(e)
                    if not recent_enough(pub):
                        continue
                    title = strip_html(getattr(e, "title", ""))
                    if not title:
                        continue
                    summary = strip_html(getattr(e, "summary", ""))
                    if len(summary) > 380:
                        summary = summary[:377].rstrip() + "…"
                    items.append({
                        "category": cat,
                        "title": title,
                        "link": getattr(e, "link", None),
                        "summary": summary,
                        "published": pub.isoformat() if pub else None,
                        "source": source,
                        "media": get_media(e),
                    })
            except Exception:
                # ignore erreurs de flux et continue
                continue
    return items

def pick(items):
    # bucket par catégorie
    buckets = {}
    for it in items:
        buckets.setdefault(it["category"], []).append(it)
    # tri par fraîcheur et limite par catégorie
    for cat in buckets:
        buckets[cat].sort(key=lambda x: x.get("published", ""), reverse=True)
        buckets[cat] = buckets[cat][:MAX_PER_CATEGORY]
    # aplatis en respectant l'ordre
    picked = []
    for cat in ORDER:
        picked.extend(buckets.get(cat, []))
    return picked[:MAX_TOTAL_ITEMS]

def make_tldr(items):
    out = []
    for it in items[:7]:
        host = urlparse(it["link"]).netloc if it.get("link") else it.get("source", "source")
        out.append(f"{it['title']} ({host})")
    return out

# ------------------------------------
# Rendu Markdown
# ------------------------------------
def md_escape(text: str) -> str:
    # évite le bold accidentel
    return text.replace("**", "\\*\\*")

def render_md(items) -> str:
    lines = []
    lines.append(f"# Veille IT — {fr_date(DATE)}\n")

    # TL;DR
    lines.append("## TL;DR")
    for bullet in make_tldr(items):
        lines.append(f"- {md_escape(bullet)}")
    lines.append("")

    # Sections
    sections = {k: [] for k in ORDER}
    for it in items:
        sections[it["category"]].append(it)

    for name, arr in sections.items():
        if not arr:
            continue
        lines.append(f"## {name}")
        for it in arr:
            title = md_escape(it["title"])
            link = it.get("link") or ""
            summary = md_escape(it["summary"]) if it.get("summary") else ""
            host = urlparse(link).netloc if link else it.get("source", "")
            if link:
                lines.append(f"- **[{title}]({link})** — {summary} *(Source: {host})*")
            else:
                lines.append(f"- **{title}** — {summary} *(Source: {host})*")
            if it.get("media"):
                lines.append(f"  \n  ![]({it['media']})")
        lines.append("")

    # À surveiller / À faire
    lines.append("## À surveiller")
    lines.append("- Prochaines versions, CVE et RFC en discussion (ajustez selon vos sources internes).\n")

    lines.append("## À faire")
    lines.append("- Mettre à jour les dépendances critiques identifiées.")
    lines.append("- Planifier un patching si CVE majeure publiée.")
    lines.append("- Partager 1 insight en réunion d’équipe.\n")

    return "\n".join(lines)

# ------------------------------------
# Écriture fichiers
# ------------------------------------
def ensure_dirs(path: pathlib.Path):
    path.parent.mkdir(parents=True, exist_ok=True)

def write_daily(md_text: str) -> pathlib.Path:
    path = pathlib.Path("veille") / f"{DATE.year}" / f"{DATE.month:02d}" / f"{DATE.day:02d}.md"
    ensure_dirs(path)
    path.write_text(md_text, encoding="utf-8")
    return path

def rebuild_readme():
    files = sorted(glob.glob("veille/*/*/*.md"), reverse=True)
    lines = [
        "# Veille IT — Archive\n",
        "Brief quotidien (réseau, systèmes/Linux, Python, bases de données, Proxmox/Hyper-V, cybersécurité, DevOps).\n",
        "## Dernières entrées\n",
    ]
    for f in files[:60]:  # derniers ~2 mois
        p = pathlib.Path(f)
        y, m, d = p.parts[1], p.parts[2], p.stem
        date_label = f"{d}/{m}/{y}"
        lines.append(f"- [{date_label}]({f})")
    pathlib.Path("README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

def rebuild_index_md():
    # identique au README pour GitHub Pages
    src = pathlib.Path("README.md").read_text(encoding="utf-8") if pathlib.Path("README.md").exists() else "# Veille IT\n"
    pathlib.Path("index.md").write_text(src, encoding="utf-8")

# ------------------------------------
# Entrée principale
# ------------------------------------
def main():
    items = pick(collect())
    if not items:
        md = f"# Veille IT — {fr_date(DATE)}\n\n*Aucune actualité dans la fenêtre de {RECENT_HOURS} h avec les flux configurés.*\n"
    else:
        md = render_md(items)
    path = write_daily(md)
    rebuild_readme()
    rebuild_index_md()
    print(f"✅ Généré : {path}")

if __name__ == "__main__":
    main()

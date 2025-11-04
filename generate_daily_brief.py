import os
if link:
lines.append(f"- **[{title}]({link})** — {summary} *(Source: {host})*")
else:
lines.append(f"- **{title}** — {summary} *(Source: {host})*")
if it.get('media'):
lines.append(f" \n ![]({it['media']})")
lines.append("")


# À surveiller / À faire
lines.append("## À surveiller")
lines.append("- Prochaines versions, CVE et RFC en discussion (ajustez selon vos sources internes).\n")


lines.append("## À faire")
lines.append("- Mettre à jour les dépendances critiques identifiées.")
lines.append("- Planifier un patching si CVE majeure publiée.")
lines.append("- Partager 1 insight en réunion d’équipe.\n")


return "\n".join(lines)


# -------------------------
# Écriture fichiers
# -------------------------


def ensure_dirs(path: pathlib.Path):
path.parent.mkdir(parents=True, exist_ok=True)




def write_daily(md_text: str) -> pathlib.Path:
path = pathlib.Path('veille') / f"{DATE.year}" / f"{DATE.month:02d}" / f"{DATE.day:02d}.md"
ensure_dirs(path)
path.write_text(md_text, encoding='utf-8')
return path




def rebuild_readme():
files = sorted(glob.glob('veille/*/*/*.md'), reverse=True)
lines = [
"# Veille IT — Archive\n",
"Brief quotidien (réseau, systèmes/Linux, Python, bases de données, Proxmox/Hyper‑V, cybersécurité, DevOps).\n",
"## Dernières entrées\n",
]
for f in files[:60]: # derniers ~2 mois
p = pathlib.Path(f)
y, m, d = p.parts[1], p.parts[2], p.stem
date_label = f"{d}/{m}/{y}"
lines.append(f"- [{date_label}]({f})")
pathlib.Path('README.md').write_text("\n".join(lines) + "\n", encoding='utf-8')




def rebuild_index_md():
# identique au README pour GitHub Pages
src = pathlib.Path('README.md').read_text(encoding='utf-8') if pathlib.Path('README.md').exists() else "# Veille IT\n"
pathlib.Path('index.md').write_text(src, encoding='utf-8')




def main():
items = pick(collect())
if not items:
# Evite des commits vides : on écrit quand même un fichier minimal
md = f"# Veille IT — {fr_date(DATE)}\n\n*Aucune actualité dans la fenêtre de {RECENT_HOURS} h avec les flux configurés.*\n"
else:
md = render_md(items)
path = write_daily(md)
rebuild_readme()
rebuild_index_md()
print(f"✅ Généré : {path}")


if __name__ == '__main__':
main()

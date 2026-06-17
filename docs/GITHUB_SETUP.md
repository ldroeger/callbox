# Callbox auf GitHub veröffentlichen

## Einmalige Einrichtung

### 1. GitHub-Repository erstellen

1. Gehe zu [github.com/new](https://github.com/new)
2. Repository Name: `callbox`
3. Sichtbarkeit: **Public** (damit der One-Line-Installer funktioniert)
4. KEIN README, KEIN .gitignore hinzufügen
5. **„Create repository"** klicken

### 2. Projekt hochladen

```bash
cd /opt/callbox   # oder wo dein Projekt liegt

git init
git add .
git commit -m "Initial release: Callbox v2.0"
git branch -M main
git remote add origin https://github.com/DEIN_USERNAME/callbox.git
git push -u origin main
```

### 3. install.sh anpassen

Ersetze in `install.sh` und `scripts/update.sh`:
```
ldroeger  →  dein_github_benutzername
```

Dann nochmal pushen:
```bash
git add install.sh scripts/update.sh README.md
git commit -m "Set correct GitHub username"
git push
```

### 4. One-Line-Installer testen

```bash
curl -fsSL https://raw.githubusercontent.com/DEIN_USERNAME/callbox/main/install.sh | sudo bash
```

---

## Empfohlene GitHub-Einstellungen

### Repository Topics hinzufügen
- `raspberry-pi`
- `gsm`
- `lte`
- `sim7600`
- `docker`
- `fastapi`
- `react`
- `home-automation`

### Releases erstellen
```bash
git tag -a v2.0.0 -m "Release v2.0.0"
git push origin v2.0.0
```
Dann auf GitHub → „Create release from tag"

### README-Badge hinzufügen
```markdown
[![CI](https://github.com/DEIN_USERNAME/callbox/actions/workflows/ci.yml/badge.svg)](...)
```

---

## Sicherheitshinweis

Die `.env`-Datei enthält dein Admin-Passwort und wird durch `.gitignore` **nicht** in Git eingecheckt. Prüfe vor dem ersten Push:

```bash
git status
# .env darf NICHT in der Liste erscheinen
```

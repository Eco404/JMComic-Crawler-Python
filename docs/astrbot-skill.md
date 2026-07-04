# AstrBot Skill

This repository includes an AstrBot-compatible Skill at:

```text
astrbot/skills/jmcomic-downloader
```

AstrBot supports Skills as folders containing `SKILL.md`. You can upload a zip
from the WebUI, or place the folder under AstrBot's `data/skills/`.

## Package the Skill

From this repository root:

```bash
cd astrbot/skills
zip -r jmcomic-downloader.zip jmcomic-downloader
```

Upload `jmcomic-downloader.zip` in AstrBot WebUI: `Plugins` -> `Skills`.

## Environment

In the AstrBot container, configure:

```text
JMCOMIC_SERVICE_URL=http://jmcomic-service:8000
```

Both AstrBot and `jmcomic-service` must be on the same user-defined Docker bridge network.
When they are on the same network, Docker DNS lets AstrBot resolve the service name `jmcomic-service`, so the URL is:

```text
http://jmcomic-service:8000
```

Do not use `localhost` inside AstrBot; from inside the AstrBot container, `localhost` points back to AstrBot itself.

If AstrBot is started by another Compose project, create a shared external network and attach both projects to it, for example:

```bash
docker network create astrbot-net
```

Then configure both Compose files with:

```yaml
networks:
  astrbot-net:
    external: true
```

and attach the relevant services to `astrbot-net`.

## Example User Request

```text
下载 JM 123
```

For a photo/chapter ID:

```text
下载 JM 章节 p456
```
## File sending

The Skill should send downloaded results through AstrBot's file-sending interface.

The default service output is PDF. For a normal single-PDF request, AstrBot should send the PDF file directly. If a request produces multiple PDFs, or the user asks for zip/raw/original files, AstrBot should send the returned zip file.

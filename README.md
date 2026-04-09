# LinkedIn Lead Magnet Autopilot

This project runs a daily LinkedIn content improvement loop:

- generate a lead magnet + post
- store drafts and metrics in Notion
- capture a 6-7 second scrolling screen recording of the Notion lead magnet page
- add an automated text layer on top of the video
- publish automatically via Blotato
- pull daily performance from Apify
- run a Karpathy-style ratchet analysis to improve future prompts

## 1) What this system does

1. Generate one lead magnet + one LinkedIn post for a topic.
2. Save draft metadata in Notion.
3. Sync post metrics from Apify.
4. Analyze winners/losers and write next prompt guidance.

## 2) Project structure

```text
.
|- src/linkedin_leadmagnet/
|  |- main.py
|  |- config.py
|  |- models.py
|  |- llm.py
|  |- generator.py
|  |- notion.py
|  |- apify_client.py
|  |- blotato.py
|  |- video.py
|  |- research.py
|  `- pipeline.py
|- .github/workflows/daily_linkedin_autopilot.yml
|- knowledge/lead_magnet_school.md
|- apify_input.json
|- .env.example
`- requirements.txt
```

## 3) Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Fill `.env` with your credentials.

Install Playwright browser once for local runs:

```bash
python -m playwright install chromium
```

## 4) Notion database bootstrap

Share your parent Notion page with your integration first.

```bash
python -m src.linkedin_leadmagnet.main bootstrap-notion-db --title "LinkedIn Lead Magnet Tracker"
```

Copy the output `database_id` into `.env` as `NOTION_DATABASE_ID`.

## 5) Local run commands

Generate:

```bash
python -m src.linkedin_leadmagnet.main generate --topic "B2B SaaS onboarding checklist"
```

Publish automatically (capture Notion scroll video + text layer + Blotato post):

```bash
python -m src.linkedin_leadmagnet.main publish --experiment-id 2026-04-09-c4031533
```

Attach published post URL manually (only if needed):

```bash
python -m src.linkedin_leadmagnet.main attach-post-url --experiment-id 2026-04-09-c4031533 --post-url "https://www.linkedin.com/feed/update/urn:li:activity:0000000000000000000/"
```

Sync metrics:

```bash
python -m src.linkedin_leadmagnet.main sync-metrics --apify-input apify_input.json
```

Apify run-sync behavior is configured via env:

- `APIFY_RUN_TIMEOUT_SECONDS` (default `280`)
- `APIFY_DATASET_LIMIT` (default `100`)
- `APIFY_DATASET_CLEAN` (`true/false`)
- `APIFY_DATASET_FORMAT` (default `json`)

Run research:

```bash
python -m src.linkedin_leadmagnet.main research
```

Full daily run:

```bash
python -m src.linkedin_leadmagnet.main daily-run --topic "Financial reporting automation for SMB CFOs" --apify-input apify_input.json
```

Full daily run with auto-publish:

```bash
python -m src.linkedin_leadmagnet.main daily-run --topic "Financial reporting automation for SMB CFOs" --apify-input apify_input.json --auto-publish
```

Important for video capture:

1. The Notion page must be publicly reachable by URL.
2. `NOTION_PAGE_URL_TEMPLATE` is used to build the capture URL from Notion page id.
3. Default is `https://www.notion.so/{page_id_nodash}`.

## 6) GitHub Actions daily automation

Daily workflow file:

- `.github/workflows/daily_linkedin_autopilot.yml`

Schedule:

- every day at `06:05 UTC` (`09:05 Europe/Istanbul`)

Workflow behavior:

1. Install dependencies.
2. Install Playwright Chromium.
3. Run `daily-run --auto-publish`.
4. Generate Notion page scroll video, add text layer, publish via Blotato.
5. Commit changed files under `data/` back to the repository.

Required GitHub repository secrets:

- `GEMINI_API_KEY`
- `NOTION_TOKEN`
- `NOTION_PARENT_PAGE_ID`
- `NOTION_DATABASE_ID`
- `BLOTATO_API_KEY`
- `APIFY_TOKEN`
- `APIFY_ACTOR_ID`

Optional GitHub repository secrets:

- `BLOTATO_ACCOUNT_ID`
- `BLOTATO_LINKEDIN_PAGE_ID`

Optional manual run topic input:

- `topic` (via `workflow_dispatch`)

## 7) Environment variables

See `.env.example`.

## 8) Karpathy-style adaptation note

Karpathy's original `autoresearch` loop optimizes model code through repeated experiments.
This project applies the same ratchet principle to LinkedIn content:

- generate variants
- score with objective metrics
- keep winners and improve next prompts

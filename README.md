# LinkedIn Lead Magnet Autopilot

This project runs a daily LinkedIn content improvement loop:

- generate a lead magnet + post
- store drafts and metrics in Notion
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

Attach published post URL:

```bash
python -m src.linkedin_leadmagnet.main attach-post-url --experiment-id 2026-04-09-c4031533 --post-url "https://www.linkedin.com/feed/update/urn:li:activity:0000000000000000000/"
```

Sync metrics:

```bash
python -m src.linkedin_leadmagnet.main sync-metrics --apify-input apify_input.json
```

Run research:

```bash
python -m src.linkedin_leadmagnet.main research
```

Full daily run:

```bash
python -m src.linkedin_leadmagnet.main daily-run --topic "Financial reporting automation for SMB CFOs" --apify-input apify_input.json
```

## 6) GitHub Actions daily automation

Daily workflow file:

- `.github/workflows/daily_linkedin_autopilot.yml`

Schedule:

- every day at `06:05 UTC` (`09:05 Europe/Istanbul`)

Workflow behavior:

1. Install dependencies.
2. Run `daily-run`.
3. Commit changed files under `data/` back to the repository.

Required GitHub repository secrets:

- `GEMINI_API_KEY`
- `NOTION_TOKEN`
- `NOTION_PARENT_PAGE_ID`
- `NOTION_DATABASE_ID`
- `APIFY_TOKEN`
- `APIFY_ACTOR_ID`

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

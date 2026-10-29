# miabajic.dev

Personal site of Mia Bajić, including the Behind the Commit podcast pages.

All content lives in `data/` (YAML + transcripts). `generate.py` renders it with the Jinja2
templates in `templates/` into `site/`, which GitHub Actions publishes on every push to `main`
(and rebuilds weekly, so upcoming talks move to past ones). Don't edit HTML by hand:
edit YAML → `uv run python generate.py` → check → commit.

```
uv run python generate.py           # build into site/ and list remaining TODOs
uv run python generate.py --strict  # fail if any TODO is left
python3 -m http.server -d site      # preview at http://localhost:8000
```

- `data/profile.yaml`: facts about Mia (homepage, /speaking/, llms.txt, Person JSON-LD)
- `data/talks.yaml`: talks, one entry per distinct talk with all deliveries
- `data/episodes.yaml`, `data/guests.yaml`, `data/podcast.yaml`: podcast
- `data/transcripts/<episode-slug>.vtt`: episode transcripts (optional)
- `static/`: CSS and images, copied as-is

Any YAML value starting with `TODO` is treated as missing: it isn't rendered, and the build lists it.

## Add a talk

New title: add an entry to `data/talks.yaml` with `slug`, `title`, `abstract`, `tags` and one
`deliveries` item. Same talk at another event: add a delivery to the existing entry. A delivery has
`event`, `date` (YYYY-MM-DD), `city`, `country`, `type` (talk, keynote or panel) and optional
`slides_url`, `video_url`, `code_url`. A future date is shown as upcoming.

## Add an episode

1. Add the guest to `data/guests.yaml` (`name`, `bio`, `website`) if new.
2. Add the episode at the top of `data/episodes.yaml`: `slug`, `number`, `title`, `date`,
   `youtube_id`, `rss_url`, `duration_seconds`, `guests`, `topic` (completes "Mia Bajić talks
   with <guests> about <topic>."), `summary`, `chapters`, `links`.
3. Put the transcript at `data/transcripts/<slug>.vtt`. Misheard names can be corrected with
   `transcript_fixes: [[wrong, right], ...]` instead of editing the file.

Episode thumbnails are loaded from YouTube (`i.ytimg.com`) unless `thumbnail:` points to a file in
`static/`. If a video is made private or re-uploaded, its thumbnail breaks until that is updated.

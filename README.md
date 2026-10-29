# miabajic.dev

Personal site of Mia Bajić, including the Behind the Commit podcast pages.

All content lives in `data/` (YAML + transcripts). `generate.py` renders it with the Jinja2
templates in `templates/` into `site/`, which GitHub Actions publishes on every push to `main`.
Don't edit HTML by hand.

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

"""Build miabajic.dev from data/*.yaml into site/.

    uv run python generate.py            # build into site/
    uv run python generate.py --strict   # also fail if any TODO is left in the data

YAML in data/ is the single source of truth; nothing in site/ is edited by hand.
Values starting with "TODO" are treated as missing: they are not rendered and are
listed at the end of the build.
"""

import argparse
import datetime as dt
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from markupsafe import Markup

ROOT = Path(__file__).parent
DATA = ROOT / "data"
OUT = ROOT / "site"
BASE_URL = "https://miabajic.dev"

# Previously published episode URLs; each gets a redirect page to its new location.
LEGACY_EPISODE_URLS = ["fastapi-sebastian-ramirez", "cpython-release-management"]


# --------------------------------------------------------------------------- data


def load_yaml(name):
    with open(DATA / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def strip_todos(value, path, todos):
    """Replace "TODO..." strings with None, recording where they were."""
    if isinstance(value, str) and value.strip().startswith("TODO"):
        todos.append(f"{path}: {value.strip()}")
        return None
    if isinstance(value, dict):
        return {k: strip_todos(v, f"{path}.{k}", todos) for k, v in value.items()}
    if isinstance(value, list):
        return [strip_todos(v, f"{path}[{i}]", todos) for i, v in enumerate(value)]
    return value


# Optional keys get a None/empty default so templates can test them under StrictUndefined.
OPTIONAL = {
    "guest": {"website": None, "socials": []},
    "episode": {"recorded_at": None, "thumbnail": None, "rss_url": None, "chapters": [], "links": [], "transcript_fixes": []},
    "talk": {"abstract": None, "tags": []},
    "delivery": {"city": None, "country": None, "slides_url": None, "video_url": None, "code_url": None},
}


def with_defaults(kind, obj):
    for key, default in OPTIONAL[kind].items():
        if obj.get(key) is None:
            obj[key] = default
    return obj


def as_date(value):
    return value if isinstance(value, dt.date) else dt.date.fromisoformat(str(value))


@dataclass
class TranscriptEntry:
    timestamp: str
    text: str


def parse_vtt(path, fixes=(), cues_per_entry=5):
    """Parse a WebVTT file into readable paragraphs of a few cues each."""
    cues = []
    start, lines = None, []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if "-->" in line:
            if start is not None and lines:
                cues.append((start, " ".join(lines)))
            start, lines = line.split("-->")[0].strip(), []
        elif line and line != "WEBVTT" and start is not None and not line.isdigit():
            lines.append(line)
    if start is not None and lines:
        cues.append((start, " ".join(lines)))

    entries = []
    for i in range(0, len(cues), cues_per_entry):
        group = cues[i : i + cues_per_entry]
        text = re.sub(r"\s+", " ", " ".join(t for _, t in group)).strip()
        for wrong, right in fixes:
            text = text.replace(wrong, right)
        entries.append(TranscriptEntry(format_vtt_time(group[0][0]), text))
    return entries


def format_vtt_time(ts):
    h, m, s = ts.split(".")[0].split(":")
    return f"{int(h)}:{m}:{s}" if int(h) else f"{m}:{s}"


def chapter_seconds(t):
    seconds = 0
    for part in str(t).split(":"):
        seconds = seconds * 60 + int(part)
    return seconds


def iso_duration(seconds):
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return "PT" + (f"{h}H" if h else "") + f"{m}M{s}S"


def human_duration(seconds):
    return f"{round(int(seconds) / 60)} min"


def join_names(names):
    names = list(names)
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


@dataclass
class Site:
    profile: dict
    podcast: dict
    episodes: list
    guests: dict
    talks: list
    deliveries: list
    today: dt.date
    todos: list = field(default_factory=list)

    @property
    def upcoming(self):
        return sorted((d for d in self.deliveries if d["date"] >= self.today), key=lambda d: d["date"])

    @property
    def past(self):
        return [d for d in self.deliveries if d["date"] < self.today]


def load_site(today):
    todos = []
    profile = strip_todos(load_yaml("profile.yaml"), "profile", todos)
    podcast = strip_todos(load_yaml("podcast.yaml"), "podcast", todos)
    guests = {g["name"]: with_defaults("guest", strip_todos(g, f"guests[{g['name']}]", todos)) for g in load_yaml("guests.yaml")}

    episodes = []
    for raw in load_yaml("episodes.yaml"):
        ep = with_defaults("episode", strip_todos(raw, f"episodes[{raw['slug']}]", todos))
        ep["date"] = as_date(ep["date"])
        missing = [name for name in ep["guests"] if name not in guests]
        if missing:
            sys.exit(f"episode {ep['slug']}: guests not in guests.yaml: {missing}")
        ep["guest_objs"] = [guests[name] for name in ep["guests"]]
        ep["guest_names"] = join_names(ep["guests"])
        # Guest names always appear in the link text, even when the title only has first names.
        named = all(name in ep["title"] for name in ep["guests"])
        ep["link_text"] = ep["title"] if named else f"{ep['title']} (with {ep['guest_names']})"
        ep["lede"] = f"Mia Bajić talks with {ep['guest_names']} about {ep['topic']}."
        ep["url"] = f"/podcast/{ep['slug']}/"
        ep["youtube_url"] = f"https://www.youtube.com/watch?v={ep['youtube_id']}"
        ep["thumbnail_url"] = (
            f"/{ep['thumbnail']}" if ep["thumbnail"] else f"https://i.ytimg.com/vi/{ep['youtube_id']}/hqdefault.jpg"
        )
        for ch in ep["chapters"]:
            ch["seconds"] = chapter_seconds(ch["time"])
        vtt = DATA / "transcripts" / f"{ep['slug']}.vtt"
        ep["transcript"] = parse_vtt(vtt, ep["transcript_fixes"]) if vtt.exists() else None
        if not vtt.exists():
            todos.append(f"episodes[{ep['slug']}]: no transcript (data/transcripts/{ep['slug']}.vtt)")
        episodes.append(ep)
    episodes.sort(key=lambda e: e["date"], reverse=True)

    talks, deliveries = [], []
    for raw in load_yaml("talks.yaml")["talks"]:
        talk = with_defaults("talk", strip_todos(raw, f"talks[{raw['slug']}]", todos))
        talk["has_page"] = bool(talk.get("title"))
        talk["url"] = f"/talks/{talk['slug']}/" if talk["has_page"] else None
        talk["display_title"] = talk.get("title") or "Title to be announced"
        for d in talk["deliveries"]:
            with_defaults("delivery", d)
            d["date"] = as_date(d["date"])
            d["talk"] = talk
            d["upcoming"] = d["date"] >= today
            deliveries.append(d)
        talk["deliveries"].sort(key=lambda d: d["date"], reverse=True)
        talk["latest"] = talk["deliveries"][0]["date"]
        talks.append(talk)
    deliveries.sort(key=lambda d: d["date"], reverse=True)
    talks.sort(key=lambda t: t["latest"], reverse=True)

    return Site(profile, podcast, episodes, guests, talks, deliveries, today, todos)


# --------------------------------------------------------------------------- JSON-LD


def person_ld(site, full=True):
    p = site.profile
    ld = {"@type": "Person", "@id": f"{BASE_URL}/#person", "name": p["name"], "url": BASE_URL + "/"}
    if not full:
        return ld
    ld.update(
        {
            "givenName": p["given_name"],
            "familyName": p["family_name"],
            "jobTitle": p["job_title"],
            "description": p["headline"],
            "image": f"{BASE_URL}/{p['image']}",
            "worksFor": {"@type": "Organization", "name": p["employer"], "url": p["employer_url"]},
            "memberOf": [
                {"@type": "Organization", "name": o["name"], "url": o["url"], "description": o["role"]}
                for o in p["organizations"]
            ],
            "homeLocation": {
                "@type": "Place",
                "name": p["location"],
                "address": {"@type": "PostalAddress", "addressLocality": p["location"], "addressCountry": p["location_country"]},
            },
            "knowsAbout": p["knows_about"],
            "sameAs": [link["url"] for link in public_links(p)]
            + [site.podcast["youtube"], site.podcast["spotify"], site.podcast["apple"]],
        }
    )
    if p.get("email"):
        ld["email"] = f"mailto:{p['email']}"
    return ld


def series_ld(site, full=True):
    pc = site.podcast
    ld = {"@type": "PodcastSeries", "@id": f"{BASE_URL}/podcast/#series", "name": pc["name"], "url": f"{BASE_URL}/podcast/"}
    if full:
        ld.update(
            {
                "description": pc["description"],
                "inLanguage": pc["language"],
                "image": f"{BASE_URL}/{pc['image']}",
                "webFeed": pc["rss"],
                "author": {"@id": f"{BASE_URL}/#person"},
                "actor": {"@id": f"{BASE_URL}/#person"},
                "sameAs": [pc["youtube"], pc["spotify"], pc["apple"]],
            }
        )
    return ld


def episode_ld(site, ep):
    ld = {
        "@type": "PodcastEpisode",
        "@id": f"{BASE_URL}{ep['url']}#episode",
        "url": BASE_URL + ep["url"],
        "name": ep["title"],
        "episodeNumber": ep["number"],
        "datePublished": ep["date"].isoformat(),
        "description": ep["lede"] + " " + ep["summary"],
        "timeRequired": iso_duration(ep["duration_seconds"]),
        "partOfSeries": series_ld(site, full=False),
        "actor": [{"@id": f"{BASE_URL}/#person"}],
        "contributor": [{"@type": "Person", "name": g["name"], **({"url": g["website"]} if g.get("website") else {})} for g in ep["guest_objs"]],
        "associatedMedia": {
            "@type": "VideoObject",
            "name": ep["title"],
            "description": ep["lede"],
            "contentUrl": ep["youtube_url"],
            "embedUrl": f"https://www.youtube-nocookie.com/embed/{ep['youtube_id']}",
            "thumbnailUrl": f"https://i.ytimg.com/vi/{ep['youtube_id']}/hqdefault.jpg",
            "uploadDate": ep["date"].isoformat(),
            "duration": iso_duration(ep["duration_seconds"]),
        },
    }
    if ep.get("rss_url"):
        ld["sameAs"] = [ep["rss_url"]]
    return ld


def event_ld(site, d):
    talk = d["talk"]
    ld = {
        "@type": "Event",
        "name": f"{talk['display_title']} ({d['event']})",
        "startDate": d["date"].isoformat(),
        "eventStatus": "https://schema.org/EventScheduled",
        "location": {"@type": "Place", "name": d["event"]},
        "performer": {"@id": f"{BASE_URL}/#person"},
        "superEvent": {"@type": "Event", "name": d["event"]},
    }
    if d.get("city"):
        ld["location"]["address"] = {
            "@type": "PostalAddress",
            "addressLocality": d["city"],
            **({"addressCountry": d["country"]} if d.get("country") else {}),
        }
    if talk.get("abstract"):
        ld["description"] = talk["abstract"]
    if d.get("video_url"):
        ld["recordedIn"] = {"@type": "CreativeWork", "url": d["video_url"]}
    if talk.get("url"):
        ld["url"] = BASE_URL + talk["url"]
    return ld


def json_ld(*nodes):
    doc = {"@context": "https://schema.org", "@graph": list(nodes)}
    text = json.dumps(doc, ensure_ascii=False, indent=2)
    # Never let data close the <script> element.
    return Markup(text.replace("</", "<\\/"))


def public_links(profile):
    return [link for link in profile["links"] if link.get("public", True) and link.get("url")]


# --------------------------------------------------------------------------- rendering


def make_env(site):
    env = Environment(
        loader=FileSystemLoader(ROOT / "templates"),
        autoescape=select_autoescape(["html", "xml"]),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["date_long"] = lambda d: f"{d.day} {d:%B %Y}"
    env.filters["date_short"] = lambda d: f"{d:%d %b %Y}"
    env.filters["duration"] = human_duration
    env.globals.update(
        site=site,
        profile=site.profile,
        podcast=site.podcast,
        links=public_links(site.profile),
        base_url=BASE_URL,
        year=site.today.year,
    )
    return env


@dataclass
class Page:
    path: str  # URL path, e.g. "/talks/"
    template: str
    title: str
    description: str
    ld: list
    context: dict = field(default_factory=dict)
    og_type: str = "website"
    image: str | None = None
    in_sitemap: bool = True
    lastmod: dt.date | None = None


def build_pages(site):
    p = site.profile
    person = person_ld(site)
    pages = [
        Page(
            "/",
            "index.html",
            f"{p['name']}: {p['headline']}",
            p["meta_description"],
            [person, {"@type": "WebSite", "@id": f"{BASE_URL}/#website", "url": BASE_URL + "/", "name": p["name"], "about": {"@id": f"{BASE_URL}/#person"}}],
            {"latest_episodes": site.episodes[:3], "upcoming": site.upcoming, "recent": site.past[:5]},
            og_type="profile",
        ),
        Page(
            "/speaking/",
            "speaking.html",
            f"Speaking: {p['name']}",
            f"{p['name']} speaks about {join_names([t.lower() for t in p['topics']])}. {p['availability']}",
            [person],
            {"upcoming": site.upcoming, "keynotes": [d for d in site.past if d["type"] == "keynote"], "talk_count": len(site.past)},
        ),
        Page(
            "/talks/",
            "talks.html",
            f"Talks by {p['name']}",
            f"All conference talks, keynotes and panels by {p['name']}, newest first, with slides and video recordings.",
            [person],
            {"deliveries": site.deliveries},
            lastmod=max(d["date"] for d in site.past) if site.past else None,
        ),
        Page(
            "/podcast/",
            "podcast.html",
            f"{site.podcast['name']}: podcast hosted by {p['name']}",
            site.podcast["meta_description"],
            [person, series_ld(site)],
            {"episodes": site.episodes},
            lastmod=site.episodes[0]["date"] if site.episodes else None,
        ),
    ]
    for talk in site.talks:
        if not talk["has_page"]:
            continue
        events = ", ".join(f"{d['event']}" for d in talk["deliveries"])
        pages.append(
            Page(
                talk["url"],
                "talk.html",
                f"{talk['title']}: talk by {p['name']}",
                talk.get("abstract") or f"Talk by {p['name']}, given at {events}. Slides and video recordings.",
                [person] + [event_ld(site, d) for d in talk["deliveries"]],
                {"talk": talk},
                lastmod=talk["latest"] if talk["latest"] <= site.today else None,
            )
        )
    for ep in site.episodes:
        pages.append(
            Page(
                ep["url"],
                "episode.html",
                f"{ep['title']} | {site.podcast['name']}",
                ep["lede"],
                [person, series_ld(site, full=False), episode_ld(site, ep)],
                {"ep": ep},
                og_type="video.episode",
                image=ep["thumbnail_url"],
                lastmod=ep["date"],
            )
        )
    pages.append(Page("/404.html", "404.html", "Page not found", "Page not found.", [person], in_sitemap=False))
    return pages


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def output_file(url_path):
    rel = url_path.lstrip("/")
    return OUT / (rel if rel.endswith(".html") else rel + "index.html")


def absolute(url):
    return url if url.startswith("http") else BASE_URL + url


def render_site(site):
    env = make_env(site)
    pages = build_pages(site)
    for page in pages:
        html = env.get_template(page.template).render(
            page=page,
            canonical=BASE_URL + page.path,
            og_image=absolute(page.image or "/" + site.profile["image"]),
            ld=json_ld(*page.ld),
            **page.context,
        )
        write(output_file(page.path), html)

    for slug in LEGACY_EPISODE_URLS:
        target = f"/podcast/{slug}/"
        write(OUT / "episodes" / f"{slug}.html", env.get_template("redirect.html").render(target=target, canonical=BASE_URL + target))

    write(OUT / "sitemap.xml", env.get_template("sitemap.xml").render(pages=[pg for pg in pages if pg.in_sitemap]))
    write(OUT / "robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {BASE_URL}/sitemap.xml\n")
    write(OUT / "llms.txt", env.get_template("llms.txt").render(talks=[t for t in site.talks if t["has_page"]], episodes=site.episodes, upcoming=site.upcoming))
    return pages


def copy_static():
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ROOT / "static", OUT / "static")
    shutil.copy(ROOT / "CNAME", OUT / "CNAME")
    (OUT / ".nojekyll").touch()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--strict", action="store_true", help="exit with an error if any TODO is left in data/")
    parser.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today(), help="date used to split upcoming and past talks")
    args = parser.parse_args()

    site = load_site(args.today)
    copy_static()
    pages = render_site(site)
    print(f"Built {len(pages)} pages into {OUT.relative_to(ROOT)}/")
    if site.todos:
        print(f"\n{len(site.todos)} TODOs in data/ (not rendered):")
        for todo in site.todos:
            print(f"  - {todo}")
        if args.strict:
            sys.exit(1)


if __name__ == "__main__":
    main()

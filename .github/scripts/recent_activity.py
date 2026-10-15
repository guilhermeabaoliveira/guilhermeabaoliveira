"""Render a rolling 31-day contribution chart from GitHub's public calendar."""

import argparse
from datetime import date, datetime, timedelta, timezone
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.request import Request, urlopen


class ContributionCalendar(HTMLParser):
    def __init__(self):
        super().__init__()
        self.dates = {}
        self.counts = {}
        self.tooltip = None
        self.text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "td" and "data-date" in attrs:
            self.dates[attrs["id"]] = date.fromisoformat(attrs["data-date"])
        if tag == "tool-tip" and attrs.get("for", "").startswith("contribution-day-"):
            self.tooltip = attrs["for"]
            self.text = []

    def handle_data(self, data):
        if self.tooltip:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag == "tool-tip" and self.tooltip:
            label = "".join(self.text).strip()
            match = re.match(r"^(No|[\d,]+) contributions? on ", label)
            if not match:
                raise ValueError(f"Unrecognized calendar label: {label}")
            self.counts[self.tooltip] = (
                0 if match[1] == "No" else int(match[1].replace(",", ""))
            )
            self.tooltip = None


def fetch_days(username, end):
    start = end - timedelta(days=30)
    days = {}
    for year in sorted({start.year, end.year}):
        url = (
            f"https://github.com/users/{username}/contributions"
            f"?from={year}-01-01&to={year}-12-31"
        )
        request = Request(url, headers={
            "User-Agent": "GitHub-Profile-Activity",
            "Accept-Language": "en-US",
        })
        with urlopen(request, timeout=30) as response:
            parser = ContributionCalendar()
            parser.feed(response.read().decode("utf-8"))
        for key, day in parser.dates.items():
            if start <= day <= end and key in parser.counts:
                days[day] = parser.counts[key]
    expected = [start + timedelta(days=i) for i in range(31)]
    missing = [day.isoformat() for day in expected if day not in days]
    if missing:
        raise ValueError(f"Missing contribution data: {', '.join(missing)}")
    return [(day, days[day]) for day in expected]


def render(days):
    total = sum(count for _, count in days)
    maximum = max(1, max(count for _, count in days))
    period = f"{days[0][0]:%d/%m/%Y} — {days[-1][0]:%d/%m/%Y}"
    description = "; ".join(f"{day}: {count}" for day, count in days)
    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="850" height="230" '
        'viewBox="0 0 850 230" role="img" aria-labelledby="title desc">',
        '<title id="title">Contribuições nos últimos 31 dias</title>',
        f'<desc id="desc">{escape(period)}. {total} contribuições. '
        f'{escape(description)}</desc>',
        '<rect x=".5" y=".5" width="849" height="229" rx="8" '
        'fill="#0f1724" stroke="#1f6feb"/>',
        '<g font-family="Segoe UI,Arial,sans-serif">',
        '<text x="26" y="33" fill="#58a6ff" font-size="18" '
        'font-weight="600">Atividade nos últimos 31 dias</text>',
        f'<text x="26" y="57" fill="#c9d1d9" font-size="13">'
        f'{escape(period)} · {total} contribuições</text>',
    ]
    for fraction in (0, .5, 1):
        y = 180 - fraction * 100
        svg.append(f'<path d="M50 {y}H820" stroke="#243249"/>')
    for i, (day, count) in enumerate(days):
        x = 52 + i * 24.7
        height = 100 * count / maximum
        svg.append(
            f'<rect x="{x:.1f}" y="{180-height:.1f}" width="16" '
            f'height="{max(height, 2):.1f}" rx="2" '
            f'fill="{"#58a6ff" if count else "#243249"}">'
            f'<title>{day:%d/%m/%Y}: {count} contribuições</title></rect>'
        )
        if i in (0, 7, 14, 21, 30):
            svg.append(f'<text x="{x+8:.1f}" y="205" text-anchor="middle" '
                       f'fill="#c9d1d9" font-size="12">{day:%d/%m}</text>')
    svg.extend(['</g>', '</svg>'])
    return "\n".join(svg) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", default="guilhermeabaoliveira")
    parser.add_argument("--date", type=date.fromisoformat)
    parser.add_argument("--output", type=Path, default=Path("dist/recent-activity.svg"))
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9-]{1,39}", args.username):
        parser.error("Invalid GitHub username")
    end = args.date or datetime.now(timezone(timedelta(hours=-3))).date()
    days = fetch_days(args.username, end)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(days), encoding="utf-8")
    print(f"Rendered {len(days)} days, {sum(count for _, count in days)} contributions")


if __name__ == "__main__":
    main()

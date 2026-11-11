#!/usr/bin/env python3
"""Refresh data/contributions.json and data/repos.json from the GitHub API.

Runs inside the scheduled GitHub Action (GH_TOKEN = the built-in GITHUB_TOKEN)
or on your machine:  GH_TOKEN=$(gh auth token) python scripts/fetch_data.py

Standard library only, so the Action needs no pip install for this step.
"""
import json
import os
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

USERNAME = os.environ.get("GH_USER", "deoreparth700-design")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
DATA = Path(__file__).resolve().parent.parent / "data"

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def call(url, payload=None):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode() if payload else None,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "readme-cards",
            **({"Content-Type": "application/json"} if payload else {}),
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def contributions(end):
    # GitHub allows at most one year per query: 365 days ending today.
    start = end - timedelta(days=364)
    body = call(
        "https://api.github.com/graphql",
        {"query": QUERY, "variables": {
            "login": USERNAME,
            "from": f"{start.isoformat()}T00:00:00Z",
            "to": f"{end.isoformat()}T23:59:59Z",
        }},
    )
    if "errors" in body:
        raise RuntimeError(body["errors"])
    cal = body["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = [
        [d["date"], d["contributionCount"]]
        for week in cal["weeks"] for d in week["contributionDays"]
        if start.isoformat() <= d["date"] <= end.isoformat()
    ]
    return {
        "username": USERNAME,
        "end": end.isoformat(),
        "total": sum(c for _, c in days),
        "days": days,
    }


def repos(end):
    rows = call(f"https://api.github.com/users/{USERNAME}/repos?per_page=100&type=owner&sort=pushed")
    return {
        "end": end.isoformat(),
        "repos": [
            {
                "name": r["name"],
                "description": r["description"],
                "language": r["language"],
                "stars": r["stargazers_count"],
                "forks": r["forks_count"],
                "pushed_at": r["pushed_at"],
                "fork": r["fork"],
                "url": r["html_url"],
            }
            for r in rows
        ],
    }


def main():
    if not TOKEN:
        sys.exit("Set GH_TOKEN (or GITHUB_TOKEN) to a token that can read public data.")
    end = date.today()
    DATA.mkdir(exist_ok=True)
    (DATA / "contributions.json").write_text(json.dumps(contributions(end), separators=(",", ":")))
    (DATA / "repos.json").write_text(json.dumps(repos(end), indent=1))
    print(f"Wrote data/contributions.json and data/repos.json for {USERNAME} ({end})")


if __name__ == "__main__":
    main()

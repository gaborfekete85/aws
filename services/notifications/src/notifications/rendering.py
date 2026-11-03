"""Templated emails: every template has an HTML part, a text part and a subject.

Jinja2 with autoescaping for HTML: Event titles and Important information are
user input. Templates live in ``notifications/templates/<name>.{subject,html,txt}``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

TEMPLATES = Path(__file__).parent / "templates"
DISPLAY_TZ = ZoneInfo("Europe/Zurich")


@dataclass(frozen=True)
class Email:
    subject: str
    html: str
    text: str


def format_when(value: str | None) -> str:
    if not value:
        return ""
    moment = datetime.fromisoformat(value).astimezone(DISPLAY_TZ)
    return moment.strftime("%A %-d %B %Y, %H:%M")


def format_money(cents: int | None, currency: str | None) -> str:
    if not cents:
        return "Free"
    return f"{currency or ''} {cents / 100:,.2f}".strip()


@cache
def environment() -> Environment:
    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(enabled_extensions=("html",), default_for_string=False),
        undefined=StrictUndefined,  # a missing variable is a bug, not an empty string
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["when"] = format_when
    env.filters["money"] = format_money
    return env


def render(name: str, context: dict[str, Any]) -> Email:
    env = environment()
    subject = env.get_template(f"{name}.subject").render(context).strip()
    return Email(
        subject=" ".join(subject.split()),  # one line, no header injection
        html=env.get_template(f"{name}.html").render(context),
        text=env.get_template(f"{name}.txt").render(context),
    )

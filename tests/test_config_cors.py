"""Day 18 — tests for Settings.cors_origins (app/config.py)."""
from app.config import Settings


def test_wildcard_default_stays_wildcard():
    s = Settings(ALLOWED_ORIGINS="*")
    assert s.cors_origins == ["*"]


def test_single_origin_parsed_as_list():
    s = Settings(ALLOWED_ORIGINS="https://ai020-dashboard.onrender.com")
    assert s.cors_origins == ["https://ai020-dashboard.onrender.com"]


def test_multiple_comma_separated_origins_trimmed():
    s = Settings(ALLOWED_ORIGINS="https://a.example.com, https://b.example.com ,https://c.example.com")
    assert s.cors_origins == [
        "https://a.example.com",
        "https://b.example.com",
        "https://c.example.com",
    ]


def test_blank_entries_dropped():
    s = Settings(ALLOWED_ORIGINS="https://a.example.com,,  ,https://b.example.com")
    assert s.cors_origins == ["https://a.example.com", "https://b.example.com"]

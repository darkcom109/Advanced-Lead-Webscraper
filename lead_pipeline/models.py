from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Market:
    label: str
    search_location: str
    gl: str
    priority: str


@dataclass(frozen=True)
class SearchJob:
    industry: str
    market: Market
    signal: str
    query: str


@dataclass
class SearchCandidate:
    company_url: str
    source_url: str
    domain: str
    title: str
    snippet: str
    industry: str
    market: str
    signal: str
    query: str
    score: int
    source_rank: int


@dataclass
class EmailHit:
    email: str
    source_url: str
    source_type: str


@dataclass
class DecisionMakerHit:
    name: str
    title: str
    source_url: str
    source_type: str
    confidence: int

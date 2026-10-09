"""Reject malformed studies and references that cannot be traced to supplied evidence."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Evidence(Record):
    source: Literal["transcript", "frame", "ocr", "caption"]
    t: float | None = Field(default=None, ge=0)
    quote: str | None = Field(default=None, max_length=300)

    @field_validator("source", mode="before")
    @classmethod
    def canonical_source(cls, value):
        # Qwen2-VL sometimes pluralizes this label. Evidence checks still apply.
        return "frame" if value == "frames" else value


class Observation(Record):
    aspect: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=1500)
    evidence: list[Evidence] = Field(min_length=1, max_length=8)


class Segment(Record):
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    text: str


class Frame(Record):
    t: float = Field(ge=0)
    file: str | None = None
    ocr: str = ""


class Study(Record):
    title: str = Field(min_length=1, max_length=200)
    duration_s: float = Field(gt=0, le=600)
    topics: list[str] = Field(max_length=20)
    creative_tags: list[str] = Field(max_length=20)
    transcript: list[Segment]
    frames: list[Frame] = Field(min_length=1)
    observations: list[Observation] = Field(min_length=1, max_length=30)
    hypotheses: list[str] = Field(max_length=10)


def validate_study(value, post):
    study = Study.model_validate(value)
    for seg in study.transcript:
        if not seg.start <= seg.end <= study.duration_s + 0.5:
            raise ValueError("Transcript timestamp is outside the video.")
    for frame in study.frames:
        if frame.t > study.duration_s or (
            frame.file and ("/" in frame.file or "\\" in frame.file or frame.file.startswith("."))
        ):
            raise ValueError("Invalid frame reference.")
    for obs in study.observations:
        for evidence in obs.evidence:
            if evidence.t is not None and evidence.t > study.duration_s:
                raise ValueError("Evidence timestamp is outside the video.")
            quote = evidence.quote or ""
            if evidence.source == "transcript":
                if (
                    not quote
                    or evidence.t is None
                    or not any(
                        seg.start <= evidence.t <= seg.end and quote in seg.text
                        for seg in study.transcript
                    )
                ):
                    raise ValueError("A transcript quote does not match its source segment.")
            elif evidence.source == "caption":
                if not quote or quote not in post.get("caption", ""):
                    raise ValueError("A caption quote does not match its source.")
            else:
                frames = [frame for frame in study.frames if frame.t == evidence.t]
                if not frames:
                    raise ValueError("Visual evidence must refer to a sampled frame.")
                if evidence.source == "ocr" and (not quote or quote not in frames[0].ocr):
                    raise ValueError("An on-screen quote does not match OCR evidence.")
                if evidence.source == "frame" and quote:
                    if quote not in frames[0].ocr:
                        raise ValueError("Visual observations cannot invent a text quote; use OCR.")
                    # Classify exact on-screen quotations by their verified text source.
                    evidence.source = "ocr"
    return study.model_dump()


class Profile(Record):
    audience: str = Field(default="", max_length=500)
    objective: str = Field(default="", max_length=500)
    format: str = Field(default="", max_length=300)
    voice: str = Field(default="", max_length=500)


class Reference(Record):
    id: str
    reason: str = Field(min_length=1, max_length=1000)


class Brief(Record):
    title: str = Field(min_length=1, max_length=200)
    hooks: list[str] = Field(min_length=3, max_length=3)
    beats: list[str] = Field(min_length=1, max_length=12)
    visuals: list[str] = Field(min_length=1, max_length=12)
    references: list[Reference] = Field(min_length=1, max_length=5)

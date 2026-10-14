"""Turn PDFs, pasted notes and YouTube videos into chunks."""
import io
import re
from typing import Optional

from . import config


class IngestError(ValueError):
    pass


def extract_pdf_text(data: bytes) -> str:
    from pypdf import PdfReader
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [(p.extract_text() or "") for p in reader.pages]
    except Exception as exc:
        raise IngestError(f"Could not read the PDF: {exc}")
    text = clean_text("\n".join(pages))
    if len(text.split()) < 20:
        raise IngestError("No readable text found in the PDF (is it a scanned image?).")
    return text


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, size: int = config.CHUNK_WORDS,
               overlap: int = config.CHUNK_OVERLAP) -> list:
    """Split into chunks of about `size` words, overlapping by `overlap` words."""
    words = text.split()
    if not words:
        return []
    step = max(1, size - overlap)
    chunks = []
    for start in range(0, len(words), step):
        piece = words[start:start + size]
        chunks.append({"text": " ".join(piece)})
        if start + size >= len(words):
            break
    if len(chunks) > 1 and len(chunks[-1]["text"].split()) < 20:
        chunks.pop()   # tail too short to be useful on its own
    return chunks


_YT_ID = re.compile(r"(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{11})")


def parse_youtube_id(url: str) -> Optional[str]:
    m = _YT_ID.search(url)
    if m:
        return m.group(1)
    return url if re.fullmatch(r"[A-Za-z0-9_-]{11}", url.strip()) else None



def fetch_youtube_segments(video_id: str) -> list:
    """Fetch YouTube transcript and return normalized segments."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        fetched = YouTubeTranscriptApi().fetch(
            video_id,
            languages=["en", "hi"]
        )

        segments = []
        for item in fetched:
            # Compatible with newer transcript snippets
            if hasattr(item, "text"):
                text = item.text
                start = item.start
                duration = item.duration
            else:
                # Compatible with dictionary-style transcript items
                text = item.get("text", "")
                start = item.get("start", 0)
                duration = item.get("duration", 0)

            if text and text.strip():
                segments.append({
                    "text": text,
                    "start": float(start),
                    "duration": float(duration)
                })

        if not segments:
            raise IngestError(
                "Transcript is empty. Try another video or upload its transcript."
            )

        return segments

    except IngestError:
        raise
    except Exception as exc:
        error = str(exc)
        if "403" in error or "Forbidden" in error or "blocked" in error.lower():
            raise IngestError(
                "YouTube is blocking transcript requests from the backend server. "
                "This is a hosting/network restriction, not a chunking error. "
                "Try another video or use the transcript-text fallback."
            )
        raise IngestError(f"Could not fetch the transcript: {error}")



def chunk_segments(segments: list, size: int = config.CHUNK_WORDS) -> list:
    """Group transcript lines into chunks and keep the start/end second of each."""
    chunks, buf, words, start, end = [], [], 0, None, 0.0
    for seg in segments:
        txt = clean_text(seg["text"].replace("\n", " "))
        if not txt:
            continue
        if start is None:
            start = float(seg["start"])
        buf.append(txt)
        words += len(txt.split())
        end = float(seg["start"]) + float(seg.get("duration", 0))
        if words >= size:
            chunks.append({"text": " ".join(buf), "start_sec": start, "end_sec": end})
            buf, words, start = [], 0, None
    if buf:
        if chunks and words < 20:
            chunks[-1]["text"] += " " + " ".join(buf)
            chunks[-1]["end_sec"] = end
        else:
            chunks.append({"text": " ".join(buf), "start_sec": start, "end_sec": end})
    return chunks

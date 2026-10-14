"""Turn PDFs, pasted notes and YouTube videos into chunks."""
import io
import os
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


def _transcript_api():
    """YouTubeTranscriptApi; goes through a proxy when one is set (needed on Render)."""
    from youtube_transcript_api import YouTubeTranscriptApi
    user, pwd = os.getenv("WEBSHARE_PROXY_USER"), os.getenv("WEBSHARE_PROXY_PASS")
    url = os.getenv("YT_PROXY_URL")
    if user and pwd:
        from youtube_transcript_api.proxies import WebshareProxyConfig
        return YouTubeTranscriptApi(proxy_config=WebshareProxyConfig(
            proxy_username=user, proxy_password=pwd))
    if url:
        from youtube_transcript_api.proxies import GenericProxyConfig
        return YouTubeTranscriptApi(proxy_config=GenericProxyConfig(http_url=url, https_url=url))
    return YouTubeTranscriptApi()


def fetch_youtube_segments(video_id: str) -> list:
    """List of {text, start, duration}. Works with old and new youtube-transcript-api."""
    from youtube_transcript_api import YouTubeTranscriptApi
    try:
        try:
            fetched = _transcript_api().fetch(video_id, languages=["en", "hi"])
            return [{"text": s.text, "start": s.start, "duration": s.duration} for s in fetched]
        except AttributeError:
            return YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "hi"])
    except Exception as exc:
        reason = (str(exc).strip().splitlines() or [""])[0][:160]
        raise IngestError(
            "Could not fetch the transcript automatically (YouTube often blocks cloud servers). "
            "Copy the video's transcript and add it in the Notes tab instead. " + reason)



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

"""Turn PDFs, pasted notes and YouTube videos into chunks."""
import io
import os
import time
import requests
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
    """Fetch YouTube captions through Supadata."""
    api_key = os.getenv("SUPADATA_API_KEY")

    if not api_key:
        raise IngestError(
            "SUPADATA_API_KEY is missing from the backend environment."
        )

    video_url = f"https://www.youtube.com/watch?v={video_id}"
    endpoint = "https://api.supadata.ai/v1/transcript"
    headers = {"x-api-key": api_key}

    try:
        response = requests.get(
            endpoint,
            headers=headers,
            params={
                "url": video_url,
                "lang": "en",
                "mode": "native",
                "text": "false",
            },
            timeout=60,
        )

        if response.status_code not in (200, 202):
            raise IngestError(
                f"Supadata transcript request failed "
                f"({response.status_code}): {response.text[:500]}"
            )

        data = response.json()

        # Large transcripts can return a job ID.
        if response.status_code == 202 or "jobId" in data:
            job_id = data.get("jobId")
            if not job_id:
                raise IngestError(
                    "Supadata returned an async response without a job ID."
                )

            for _ in range(30):
                time.sleep(2)
                result = requests.get(
                    f"{endpoint}/{job_id}",
                    headers=headers,
                    timeout=30,
                )

                if result.status_code != 200:
                    raise IngestError(
                        f"Transcript job check failed "
                        f"({result.status_code}): {result.text[:300]}"
                    )

                data = result.json()
                status = data.get("status")

                if status == "completed":
                    break

                if status == "failed":
                    raise IngestError(
                        f"Supadata transcript job failed: "
                        f"{data.get('error', 'unknown error')}"
                    )
            else:
                raise IngestError(
                    "Transcript is taking too long. Please try again."
                )

        content = data.get("content", [])

        if isinstance(content, str):
            content = [{"text": content, "offset": 0, "duration": 0}]

        segments = []
        for item in content:
            text = str(item.get("text", "")).strip()
            if not text:
                continue

            # Supadata offsets/durations are in milliseconds.
            start = float(item.get("offset", 0)) / 1000
            duration = float(item.get("duration", 0)) / 1000

            segments.append({
                "text": text,
                "start": start,
                "duration": duration,
            })

        if not segments:
            raise IngestError(
                "Supadata returned no transcript segments. "
                "The video may not have accessible captions."
            )

        return segments

    except IngestError:
        raise
    except requests.RequestException as exc:
        raise IngestError(
            f"Could not connect to Supadata: {exc}"
        )
    except (ValueError, TypeError, KeyError) as exc:
        raise IngestError(
            f"Could not parse the Supadata transcript response: {exc}"
        )




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

"""Document understanding pipeline (Section: attachments → text → understanding).

Given an attachment's bytes (from email, etc.), this:

1. extracts text (PDF/Word/plain) or flags images/scanned PDFs for the vision model,
2. asks the local model (via the environment-aware router) for a concise summary and structured
   facts (dates, parties, reference numbers, document type),
3. stores the file on disk and a :class:`Document` row for later retrieval.

Extracted text is UNTRUSTED external content: it is fenced before being shown to the model and is
never treated as instructions (content-trust / Section 35).
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlmodel import Session

from app.agent.content_trust import fence_untrusted
from app.agent.llm.base import LLMRequest, TaskType
from app.autonomy.router import get_router
from app.core.config import Settings, get_settings
from app.core.models import Document
from app.documents.extract import DocKind, extract_text


@dataclass
class DocumentAnalysis:
    filename: str
    content_type: str
    kind: DocKind
    file_hash: str
    extracted_text: str
    summary: str
    doc_type: str | None = None
    important_dates: list[dict[str, Any]] = field(default_factory=list)
    parties: list[str] = field(default_factory=list)
    reference_numbers: dict[str, Any] = field(default_factory=dict)
    needs_vision: bool = False
    stored_document_id: str | None = None
    storage_ref: str | None = None


def _run_sync(coro):
    """Run an async coroutine from sync code, whether or not a loop is already running."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # Inside the autonomy loop: run on a worker thread with its own event loop.
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", name or "attachment.bin")[:120]


class DocumentProcessor:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._router = get_router(self._settings)

    def analyze(
        self,
        data: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
        *,
        source: str | None = None,
        persist: bool = True,
    ) -> DocumentAnalysis:
        file_hash = hashlib.sha256(data).hexdigest()
        extracted = extract_text(data, filename, content_type)

        # Summarize what we understood. Images/scanned PDFs have no local text: describe the intent
        # and rely on a multimodal model where available.
        if extracted.needs_vision or not extracted.text:
            prompt = (
                f"An email attachment named '{filename}' ({content_type}) could not be read as "
                f"text locally (kind={extracted.kind.value}). Summarize what this document likely "
                "is and what action it may require."
            )
        else:
            prompt = (
                "Summarize the following document for the user in 2-3 sentences and note any "
                "deadlines or required actions.\n\n" + fence_untrusted(extracted.text[:6000])
            )
        summary = _run_sync(
            self._router.complete(LLMRequest(prompt=prompt, task_type=TaskType.document))
        ).text.strip()

        doc_type, dates, parties, refs = self._extract_structured(extracted.text, filename)

        storage_ref: str | None = None
        stored_id: str | None = None
        if persist:
            storage_ref = self._store_file(data, file_hash, filename)
            stored_id = self._store_document(
                filename=filename,
                file_hash=file_hash,
                source=source,
                doc_type=doc_type,
                extracted_text=extracted.text,
                summary=summary,
                dates=dates,
                parties=parties,
                refs=refs,
                storage_ref=storage_ref,
            )

        return DocumentAnalysis(
            filename=filename,
            content_type=content_type,
            kind=extracted.kind,
            file_hash=file_hash,
            extracted_text=extracted.text,
            summary=summary,
            doc_type=doc_type,
            important_dates=dates,
            parties=parties,
            reference_numbers=refs,
            needs_vision=extracted.needs_vision,
            stored_document_id=stored_id,
            storage_ref=storage_ref,
        )

    def _extract_structured(
        self, text: str, filename: str
    ) -> tuple[str | None, list[dict[str, Any]], list[str], dict[str, Any]]:
        if not text:
            return (None, [], [], {})
        prompt = (
            "Extract as JSON with keys doc_type (string), dates (list of {label,date}), parties "
            "(list of strings), reference_numbers (object). Document text follows.\n\n"
            + fence_untrusted(text[:6000])
        )
        raw = _run_sync(
            self._router.complete(LLMRequest(prompt=prompt, task_type=TaskType.extraction))
        ).text
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return (None, [], [], {})
        return (
            parsed.get("doc_type"),
            parsed.get("dates", []) or [],
            parsed.get("parties", []) or [],
            parsed.get("reference_numbers", {}) or {},
        )

    def _store_file(self, data: bytes, file_hash: str, filename: str) -> str:
        docs_dir = Path(self._settings.documents_dir)
        docs_dir.mkdir(parents=True, exist_ok=True)
        path = docs_dir / f"{file_hash[:12]}_{_safe_name(filename)}"
        path.write_bytes(data)
        return str(path)

    def _store_document(
        self,
        *,
        filename: str,
        file_hash: str,
        source: str | None,
        doc_type: str | None,
        extracted_text: str,
        summary: str,
        dates: list[dict[str, Any]],
        parties: list[str],
        refs: dict[str, Any],
        storage_ref: str,
    ) -> str:
        document = Document(
            filename=filename,
            file_hash=file_hash,
            source=source,
            doc_type=doc_type,
            extracted_text=extracted_text or None,
            summary=summary or None,
            important_dates=dates,
            parties=parties,
            reference_numbers=refs,
            storage_ref=storage_ref,
        )
        self._session.add(document)
        self._session.commit()
        self._session.refresh(document)
        return document.id

"""Bulk inbox cleanup: scan senders over a date range and classify bulk/promotional vs keep.

Detection is a HYBRID: fast header/keyword heuristics first, with an LLM tiebreaker only for the
senders the heuristics cannot confidently place. Senders whose mail looks transactional (invoices,
orders, receipts, bills, statements, payments, bookings) are always PROTECTED — never proposed for
deletion — so important records are preserved. Subjects are UNTRUSTED external content and are
fenced before being shown to the model; they are never treated as instructions.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from app.agent.content_trust import fence_untrusted
from app.agent.llm.base import LLMRequest, TaskType
from app.agent.llm.sync import run_sync
from app.autonomy.router import LLMRouter
from app.core.config import get_settings
from app.integrations.email.imap import HeaderInfo, ImapEmailClient

CATEGORY_SPAM = "spam"
CATEGORY_ADVERTISING = "advertising"
CATEGORY_KEEP = "keep"

_PROMO_KEYWORDS = (
    "sale", "% off", "discount", "coupon", "deal", "offer", "newsletter", "unsubscribe",
    "promo", "limited time", "save now", "shop now", "webinar", "black friday", "cyber monday",
    "flash sale", "clearance", "new arrivals", "exclusive", "subscribe", "sign up", "rewards",
)
_PROTECT_KEYWORDS = (
    "invoice", "order", "receipt", "bill", "statement", "payment", "confirmation", "confirmed",
    "shipped", "delivery", "tracking", "tax", "refund", "policy", "contract", "booking",
    "reservation", "ticket", "itinerary", "renewal", "purchase", "account statement",
)
_SPAM_KEYWORDS = (
    "you won", "winner", "claim your", "prize", "act now", "risk-free", "viagra", "get rich",
    "congratulations", "free gift", "click here", "verify your account", "urgent action",
)


@dataclass
class SenderGroup:
    sender: str
    sender_name: str
    count: int
    sample_subjects: list[str]
    latest_at: datetime | None
    category: str
    reason: str


def scan_senders(
    *,
    since: datetime,
    before: datetime,
    on_group: Callable[[SenderGroup], None] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[SenderGroup]:
    """Fetch headers in [since, before), group by sender, and classify each sender.

    ``on_group``/``on_progress`` let a long-running background job stream partial results while the
    scan is still in flight (fetching headers can take longer than a mobile request timeout).
    """
    client = ImapEmailClient()
    headers = client.fetch_headers(since=since, before=before)

    groups: dict[str, list[HeaderInfo]] = defaultdict(list)
    for h in headers:
        if h.sender:
            groups[h.sender].append(h)

    total = len(groups)
    if on_progress:
        on_progress(0, total)

    router: LLMRouter | None = None
    result: list[SenderGroup] = []
    for idx, (sender, items) in enumerate(groups.items(), start=1):
        subjects = [i.subject for i in items if i.subject]
        sample = subjects[:3]
        name = next((i.sender_name for i in items if i.sender_name), "")
        latest = max((i.received_at for i in items), default=None)
        bulk = any(i.list_unsubscribe or i.precedence in {"bulk", "list", "junk"} for i in items)
        text = " ".join(subjects).lower()
        protected = any(k in text for k in _PROTECT_KEYWORDS)
        promo = any(k in text for k in _PROMO_KEYWORDS)
        spammy = any(k in text for k in _SPAM_KEYWORDS)

        if protected:
            category, reason = CATEGORY_KEEP, "Looks transactional (invoice/order/bill) — protected."
        elif spammy:
            category, reason = CATEGORY_SPAM, "Matches spam/scam language."
        elif promo and bulk:
            category, reason = CATEGORY_ADVERTISING, "Bulk sender with promotional subjects."
        elif promo or bulk:
            router = router or LLMRouter(get_settings())
            category, reason = _llm_classify(router, name, sender, sample)
        else:
            category, reason = CATEGORY_KEEP, "No bulk/promotional signals detected."

        group = SenderGroup(sender, name, len(items), sample, latest, category, reason)
        result.append(group)
        if on_group:
            on_group(group)
        if on_progress:
            on_progress(idx, total)

    order = {CATEGORY_SPAM: 0, CATEGORY_ADVERTISING: 1, CATEGORY_KEEP: 2}
    result.sort(key=lambda g: (order.get(g.category, 3), -g.count))
    return result


def _llm_classify(router: LLMRouter, name: str, sender: str, subjects: list[str]) -> tuple[str, str]:
    """Ask the fast model to place an ambiguous sender. Fails safe to 'keep'."""
    listing = "\n".join(f"- {s}" for s in subjects) or "(no subjects)"
    prompt = (
        "Classify an email SENDER for inbox cleanup. Answer with a single word: 'advertising' "
        "(marketing/promotions/newsletters), 'spam' (junk/scam), or 'keep' (anything transactional "
        "or personally important such as invoices, orders, bills, receipts, or real "
        "correspondence). When unsure, answer 'keep'.\n\n"
        f"Sender: {name} <{sender}>\nRecent subjects:\n" + fence_untrusted(listing[:2000])
    )
    try:
        resp = run_sync(router.complete(LLMRequest(prompt=prompt, task_type=TaskType.classification)))
        word = (resp.text or "").strip().strip("\"'.").lower()
    except Exception:
        word = "keep"
    if word.startswith("spam"):
        return CATEGORY_SPAM, "Model classified the sender as spam."
    if word.startswith("advertis") or word.startswith("promo") or "market" in word:
        return CATEGORY_ADVERTISING, "Model classified the sender as advertising."
    return CATEGORY_KEEP, "Model was unsure or classified it as important — protected."

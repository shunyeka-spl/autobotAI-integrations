"""Microsoft Teams webhook URLs and payloads.

Office 365 Incoming Webhooks (``*.webhook.office.com/webhookb2/.../IncomingWebhook/...``)
accept a MessageCard. Teams Workflows replaced that connector. Their trigger
URL is a Power Automate HTTP endpoint and the default "Post to a channel when
a webhook request is received" flow only renders an Adaptive Card envelope.
"""

import html
import re
from typing import Optional
from urllib.parse import parse_qs, urlparse

import requests

# Unanchored on purpose: matches the historical check, which allowed a query string.
_LEGACY_WEBHOOK = re.compile(
    r"https://[\w\-.]+/webhookb2/[\w\d\-@]+/IncomingWebhook/[\w\d\-@]+/[\w\d\-@]+"
)

_WORKFLOW_HOST_SUFFIXES = (
    ".logic.azure.com",
    ".environment.api.powerplatform.com",
)

_WORKFLOW_PATH = re.compile(
    r"^(?:/powerautomate/automations(?:/[\w.\-]+)*)?"
    r"/workflows/[\w\-]+/triggers/[\w\-]+/paths/invoke/?$",
    re.IGNORECASE,
)

_TAG_BREAK = re.compile(r"(?i)<br\s*/?>|</p>|</div>|</li>|</tr>")
_TAG_LIST = re.compile(r"(?i)<li[^>]*>")
_TAG_BOLD = re.compile(r"(?i)</?(?:b|strong)>")
_TAG_ITALIC = re.compile(r"(?i)</?(?:i|em)>")
_TAG_LINK = re.compile(
    r"(?i)<a\s+[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
    re.DOTALL,
)
_TAG_ANY = re.compile(r"<[^>]+>")


def classify_teams_webhook(url: Optional[str]) -> Optional[str]:
    """Return ``connector``, ``workflow``, or ``None`` when the URL is not a Teams webhook."""
    if not url or not isinstance(url, str):
        return None
    cleaned = url.strip()
    if _LEGACY_WEBHOOK.match(cleaned):
        return "connector"
    if _is_workflow_webhook(cleaned):
        return "workflow"
    return None


def _is_workflow_webhook(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    if not any(host.endswith(suffix) for suffix in _WORKFLOW_HOST_SUFFIXES):
        return False
    if not _WORKFLOW_PATH.match(parsed.path or ""):
        return False
    return bool(parse_qs(parsed.query).get("sig"))


def to_workflow_message(payload: dict) -> dict:
    """Turn a pymsteams MessageCard payload into the Workflows Adaptive Card body."""
    body = []
    title = _text(payload.get("title"))
    if title:
        body.append(
            {
                "type": "TextBlock",
                "text": title,
                "weight": "Bolder",
                "size": "Medium",
                "wrap": True,
            }
        )
    text = _text(payload.get("text"))
    if text:
        body.append({"type": "TextBlock", "text": text, "wrap": True})

    actions = _open_url_actions(payload.get("potentialAction"))
    for section in payload.get("sections") or []:
        if not isinstance(section, dict):
            continue
        for key, weight in (
            ("title", "Bolder"),
            ("activityTitle", "Bolder"),
            ("activitySubtitle", None),
            ("activityText", None),
            ("text", None),
        ):
            value = _text(section.get(key))
            if not value:
                continue
            block = {"type": "TextBlock", "text": value, "wrap": True}
            if weight:
                block["weight"] = weight
            if key == "activitySubtitle":
                block["isSubtle"] = True
            body.append(block)
        facts = [
            {
                "title": str(fact.get("name", "")),
                "value": str(fact.get("value", "")),
            }
            for fact in (section.get("facts") or [])
            if isinstance(fact, dict)
        ]
        if facts:
            body.append({"type": "FactSet", "facts": facts})
        for image in section.get("images") or []:
            if isinstance(image, dict) and image.get("image"):
                body.append({"type": "Image", "url": image["image"]})
        actions.extend(_open_url_actions(section.get("potentialAction")))

    if not body:
        fallback = _text(payload.get("summary")) or "Notification"
        body.append({"type": "TextBlock", "text": fallback, "wrap": True})

    card = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.2",
        "body": body,
    }
    if actions:
        card["actions"] = actions
    return {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "contentUrl": None,
                "content": card,
            }
        ],
    }


def payload_has_content(payload: dict) -> bool:
    if not payload:
        return False
    if any(payload.get(key) for key in ("title", "text", "summary")):
        return True
    if payload.get("potentialAction"):
        return True
    return bool(payload.get("sections"))


def post_workflow_message(url: str, card_payload: dict, timeout: int = 60):
    from pymsteams import TeamsWebhookException

    try:
        response = requests.post(
            url.strip(),
            json=to_workflow_message(card_payload),
            headers={"Content-Type": "application/json"},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise TeamsWebhookException(
            f"Unable to reach the Teams workflow webhook: {exc.__class__.__name__}"
        ) from exc
    if 200 <= response.status_code < 300:
        return response
    detail = (response.text or "").strip().replace("\n", " ")[:300]
    message = f"Teams workflow webhook returned {response.status_code}"
    if detail:
        message = f"{message}: {detail}"
    raise TeamsWebhookException(message)


class WorkflowConnectorCard:
    """pymsteams-compatible client that posts an Adaptive Card to a Workflows URL.

    Action code calls ``title``, ``text``, ``addSection``, ``addLinkButton``, and
    ``send`` on the injected client. Those methods still build a MessageCard
    payload; ``send`` translates it, because a Workflows trigger drops MessageCards.
    """

    def __init__(self, hookurl, **kwargs):
        import pymsteams

        self._card = pymsteams.connectorcard(hookurl.strip(), **kwargs)

    def __getattr__(self, item):
        return getattr(self._card, item)

    def send(self):
        if not payload_has_content(self._card.payload):
            raise Exception("Summary or Text is required.")
        post_workflow_message(
            self._card.hookurl,
            self._card.payload,
            timeout=self._card.http_timeout,
        )
        return True


def _text(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if "<" not in text or ">" not in text:
        return text
    text = _TAG_LINK.sub(r"[\2](\1)", text)
    text = _TAG_LIST.sub("\n- ", text)
    text = _TAG_BREAK.sub("\n", text)
    text = _TAG_BOLD.sub("**", text)
    text = _TAG_ITALIC.sub("*", text)
    text = _TAG_ANY.sub("", text)
    return html.unescape(text).strip()


def _open_url_actions(actions) -> list:
    opened = []
    for action in actions or []:
        if not isinstance(action, dict):
            continue
        name = action.get("name") or "Open"
        kind = action.get("@type")
        if kind == "ViewAction":
            for target in action.get("target") or []:
                if isinstance(target, str) and target:
                    opened.append(
                        {"type": "Action.OpenUrl", "title": name, "url": target}
                    )
        elif kind == "OpenUri":
            for target in action.get("targets") or []:
                uri = target.get("uri") if isinstance(target, dict) else None
                if uri:
                    opened.append(
                        {"type": "Action.OpenUrl", "title": name, "url": uri}
                    )
    return opened

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Arctic Shift comments -> one UTF-8 txt corpus per period.

Each kept comment or parent post becomes plain text. A half-year, month,
or flair is one file, with a blank line between texts. Timestamps, depth
and flair stay in the sibling .index.txt so they do not enter AntConc.

Examples
--------
  python3 shift_corpus.py --subreddit politics --after 2022-05-01 --before 2022-10-31 --half --only-period 2022-05-01_2022-10-31 --max 200 --out corpus
  python3 shift_corpus.py --from-json query.json --out corpus_rerun
"""

from __future__ import annotations

from tls_setup import configure_ca
_CA_SOURCE = configure_ca()  # inherited by collector subprocess; verification stays on

import argparse
import csv
import hashlib
import http.client
import json
import socket
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API = "https://arctic-shift.photon-reddit.com/api/comments/search"
POST_API = "https://arctic-shift.photon-reddit.com/api/posts/ids"
UA = "ShiftCorpus-Research/1.0 (academic corpus collection)"
REMOVED = {"[deleted]", "[removed]", "[deleted by user]"}
BOTS = {
    "automoderator",
    "politicsmoderatorbot",
    "repostsleuthbot",
    "savevideo",
    "remindmebot",
    "wikitextbot",
    "totesmessenger",
    "snapshillbot",
    "helperbot",
    "visualmod",
    "qualityvote",
    "duplicate_moderator",
    "bot-bouncer",
    "decronym",
    "transcribersofreddit",
    "commonmisspellingbot",
    "linkfixerbot",
    "vredditdownloader",
    "gifendore",
    "tweettranscriberbot",
}
FUNCTION_WORDS = {
    "the", "a", "an", "of", "to", "and", "in", "on", "for", "with", "at", "by", "from", "or", "as",
    "is", "are", "was", "were", "be", "been", "being", "it", "this", "that", "these", "those",
    "i", "you", "we", "they", "he", "she", "not", "no", "nor", "but", "if", "so", "than", "then",
    "too", "very", "just", "about", "into", "over", "after", "before", "out", "up", "down",
    "can", "could", "would", "should", "will", "may", "might", "must", "do", "did", "does",
    "have", "has", "had", "its", "their", "his", "her", "our", "your", "my", "me", "them", "us",
    "there", "here", "what", "which", "who", "whom", "when", "where", "why", "how",
}


class ApiError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def exclusive_before(date_str: str) -> str:
    day = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return (day + timedelta(days=1)).strftime("%Y-%m-%d")


def utc_parts(unix_seconds: int) -> dict[str, str]:
    dt = datetime.fromtimestamp(int(unix_seconds), timezone.utc)
    date = dt.strftime("%Y-%m-%d")
    clock = dt.strftime("%H:%M:%S")
    return {
        "iso": f"{date}T{clock}Z",
        "date": date,
        "time": clock,
        "stamp": dt.strftime("%Y%m%d_%H%M%S"),
    }


def strip_controls(text: str) -> str:
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)


def xml_escape(text: str) -> str:
    cleaned = strip_controls(text)
    return (
        cleaned.replace("&", "&" + "amp;")
        .replace("<", "&" + "lt;")
        .replace(">", "&" + "gt;")
        .replace('"', "&" + "quot;")
    )


def prepare_body(body: str, flatten: bool) -> str:
    text = strip_controls(body.replace("\r\n", "\n").replace("\r", "\n"))
    text = text.replace("<", "\uFF1C").replace(">", "\uFF1E")
    if flatten:
        return re.sub(r"\s+", " ", text).strip()
    return text.strip()


def is_removed(body: str) -> bool:
    return body.strip().lower() in REMOVED


def safe_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "_", value)
    return cleaned or "comment"


def word_count(text: str) -> int:
    return len([part for part in text.split() if part])


def normalize_subreddits(raw: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for chunk in raw:
        for piece in re.split(r"[,;\s]+", chunk.strip()):
            name = re.sub(r"^/?r/", "", piece.strip(), flags=re.I)
            if not name:
                continue
            if not re.fullmatch(r"[A-Za-z0-9_]{2,50}", name):
                raise SystemExit(f"版块名无效: {name}")
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(name)
    if len(out) > 20:
        raise SystemExit("一次最多 20 个版块。")
    return out


def normalize_link(raw: str) -> str:
    text = raw.strip()
    if not text:
        return ""
    match = re.search(r"comments/([A-Za-z0-9]+)", text, flags=re.I)
    if match:
        return match.group(1)
    return re.sub(r"^t3_", "", text, flags=re.I)


def normalize_parent(raw: str) -> str:
    text = raw.strip()
    if not text:
        return ""
    match = re.search(r"/comments/[A-Za-z0-9]+/[^/]*/([A-Za-z0-9]+)", text, flags=re.I)
    if match:
        return match.group(1)
    return text



def comment_url(link_id: str, subreddit: str, cid: str, permalink: str) -> str:
    post = link_id[3:] if link_id.startswith("t3_") else link_id
    if post and subreddit and cid:
        return f"https://www.reddit.com/r/{subreddit}/comments/{post}/_/{cid}/"
    if "/t3_" in permalink:
        return ""
    if permalink.startswith("http"):
        return permalink
    if permalink.startswith("/"):
        return "https://www.reddit.com" + permalink
    return ""


def slim(raw: dict) -> dict | None:
    body = raw.get("body")
    created = raw.get("created_utc")
    cid = raw.get("id")
    if not isinstance(body, str) or not isinstance(cid, str):
        return None
    try:
        unix = int(created)
    except (TypeError, ValueError):
        return None
    permalink = comment_url(
        raw.get("link_id") if isinstance(raw.get("link_id"), str) else "",
        raw.get("subreddit") if isinstance(raw.get("subreddit"), str) else "",
        cid,
        raw.get("permalink") if isinstance(raw.get("permalink"), str) else "",
    )
    score = raw.get("score")
    try:
        score_n = int(score)
    except (TypeError, ValueError):
        score_n = 0
    return {
        "id": cid,
        "author": raw.get("author") if isinstance(raw.get("author"), str) else "",
        "body": body,
        "createdUtc": unix,
        "subreddit": raw.get("subreddit") if isinstance(raw.get("subreddit"), str) else "",
        "score": score_n,
        "linkId": raw.get("link_id") if isinstance(raw.get("link_id"), str) else "",
        "parentId": raw.get("parent_id") if isinstance(raw.get("parent_id"), str) else "",
        "permalink": permalink,
        "linkTitle": raw.get("link_title") if isinstance(raw.get("link_title"), str) else "",
        "linkFlair": "",
        "over18": raw.get("over_18") is True,
        "kind": "comment",
        "title": "",
        "selftext": "",
        "depth": None,
        "group": "",
    }


def friendly(message: str, status: int | None) -> str:
    low = message.lower()
    if status == 429 or "rate" in low:
        return "Arctic Shift 限流了。等一会儿再跑，或把 --delay 调大。"
    if "timed out" in low or "timeout" in low:
        return "查询超时。缩小日期范围，或换一个没那么活跃的版块。正文关键词在大版上经常超时。"
    if status == 400 and "body" in low:
        return "正文关键词必须同时指定版块、作者、帖子或父评论。不能全站搜正文。"
    return message or "Arctic Shift 请求失败"


# A TLS connection may succeed while the peer resets the socket as the response
# body is being read. Those are transient transport failures, not empty samples.
TRANSIENT_TRANSPORT_ERRORS = (
    urllib.error.URLError,
    TimeoutError,
    ConnectionError,
    http.client.IncompleteRead,
    http.client.HTTPException,
    socket.timeout,
    json.JSONDecodeError,
)


def retry_pause(attempt: int, rate_limit_delay: float = 0.0) -> None:
    """Bounded exponential retry with small deterministic jitter-free delays."""
    time.sleep(max(rate_limit_delay, min(12.0, 1.2 * 2 ** attempt)))


def fetch_page(params: list[tuple[str, str]], delay_on_limit: float) -> list[dict]:
    url = API + "?" + urllib.parse.urlencode(params)
    last = "Arctic Shift 没有返回结果"
    for attempt in range(5):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                payload = json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(detail)
                message = str(parsed.get("error") or detail)
            except json.JSONDecodeError:
                message = detail or f"HTTP {exc.code}"
            message = friendly(message, exc.code)
            retry = exc.code in {408, 422, 429, 500, 502, 503, 504} and attempt < 4
            if not retry:
                raise ApiError(message, exc.code) from exc
            last = message
            retry_pause(attempt, delay_on_limit if exc.code == 429 else 0.0)
            continue
        except TRANSIENT_TRANSPORT_ERRORS as exc:
            # Preserve the underlying cause: DNS, SSL, proxy, timeouts, or invalid JSON.
            last = f"Arctic Shift 请求失败 ({type(exc).__name__}): {exc}"
            print(f"  API attempt {attempt + 1}/5: {last}", file=sys.stderr)
            if attempt < 4:
                retry_pause(attempt)
                continue
            raise ApiError(last) from exc
        if not isinstance(payload, dict):
            raise ApiError("返回格式无法识别")
        if payload.get("error"):
            message = friendly(str(payload["error"]), None)
            if "超时" in message or attempt == 4:
                raise ApiError(message)
            last = message
            retry_pause(attempt)
            continue
        data = payload.get("data")
        if not isinstance(data, list):
            raise ApiError("返回里没有评论列表")
        rows = []
        for item in data:
            if isinstance(item, dict):
                comment = slim(item)
                if comment:
                    rows.append(comment)
        return rows
    raise ApiError(last)


def keep_comment(comment: dict, args: argparse.Namespace) -> bool:
    body = comment["body"]
    if not body.strip():
        return False
    if args.exclude_deleted and is_removed(body):
        return False
    if args.exclude_automod and comment["author"].lower() == "automoderator":
        return False
    if args.exclude_nsfw and comment["over18"]:
        return False
    if args.min_score is not None and comment["score"] < args.min_score:
        return False
    if args.local:
        hay = comment["body"] if args.case_sensitive else comment["body"].lower()
        needle = args.local if args.case_sensitive else args.local.lower()
        if needle not in hay:
            return False
    if args.min_words and countable_words(body) < args.min_words:
        return False
    if args.english and not looks_english(body):
        return False
    if args.exclude_bots and comment["author"].strip().lower() in BOTS:
        return False
    return True


def countable_words(body: str) -> int:
    cleaned = re.sub(r"https?://\S+", " ", body, flags=re.I)
    return len([part for part in cleaned.split() if re.search(r"[A-Za-z0-9]", part)])


def looks_english(body: str) -> bool:
    compact = re.sub(r"\s+", "", body)
    if not compact:
        return False
    letters = len(re.findall(r"[A-Za-z]", body))
    if len(compact) < 12:
        return letters > 0 and re.search(r"[\u3400-\u9fff]", body) is None
    if letters / len(compact) < 0.55:
        return False
    words = re.findall(r"[a-z']+", body.lower())
    if len(words) >= 8 and not any(word in FUNCTION_WORDS for word in words):
        return False
    return True


def text_fingerprint(body: str) -> tuple[str, str | None]:
    exact = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", re.sub(r"https?://\S+", " ", body.lower()))).strip()
    prefix = exact[:120] if len(exact) >= 80 else None
    return exact, prefix


def is_near_duplicate(body: str, dup_exact: set[str], dup_prefix: set[str]) -> bool:
    exact, prefix = text_fingerprint(body)
    if (len(exact) >= 24 and exact in dup_exact) or (prefix and prefix in dup_prefix):
        return True
    if len(exact) >= 24:
        dup_exact.add(exact)
    if prefix:
        dup_prefix.add(prefix)
    return False


def seen_duplicate(exact: str, prefix: str | None, dup_exact: set[str], dup_prefix: set[str]) -> bool:
    if len(exact) >= 24 and exact in dup_exact:
        return True
    return bool(prefix and prefix in dup_prefix)


def remember_duplicate(exact: str, prefix: str | None, dup_exact: set[str], dup_prefix: set[str]) -> None:
    if len(exact) >= 24:
        dup_exact.add(exact)
    if prefix:
        dup_prefix.add(prefix)


def build_params(args: argparse.Namespace, subreddit: str, cursor: int | None) -> list[tuple[str, str]]:
    after = args.after
    before = exclusive_before(args.before) if args.before else ""
    if cursor is not None:
        if args.sort == "asc":
            after = str(cursor)
        else:
            before = str(cursor)
    params: list[tuple[str, str]] = [
        ("limit", str(args.page_size)),
        ("sort", args.sort),
    ]
    if args.body:
        params.append(("body", args.body))
    if subreddit:
        params.append(("subreddit", subreddit))
    if args.author:
        params.append(("author", args.author))
    if args.link_id:
        params.append(("link_id", args.link_id))
    if args.parent_id:
        params.append(("parent_id", args.parent_id))
    elif args.top_level:
        params.append(("parent_id", ""))
    if after:
        params.append(("after", after))
    if before:
        params.append(("before", before))
    return params


def collect(args: argparse.Namespace) -> tuple[list[dict], dict]:
    subs = args.subreddits or [""]
    rows: list[dict] = []
    seen: set[str] = set()
    dup_exact: set[str] = set()
    dup_prefix: set[str] = set()
    scanned = 0
    pages = 0
    stalled = 0
    warning = None
    error = None
    for sub_index, subreddit in enumerate(subs):
        cursor: int | None = None
        while len(rows) < args.max:
            if pages >= args.max_pages:
                warning = "达到 --max-pages 上限，结果可能不完整。"
                break
            if pages:
                time.sleep(args.delay)
            try:
                batch = fetch_page(build_params(args, subreddit, cursor), max(args.delay, 1))
            except ApiError as exc:
                error = str(exc)
                break
            pages += 1
            if not batch:
                break
            novel = 0
            for comment in batch:
                scanned += 1
                if comment["id"] in seen:
                    continue
                seen.add(comment["id"])
                novel += 1
                if keep_comment(comment, args) and not (args.near_dup and is_near_duplicate(comment["body"], dup_exact, dup_prefix)):
                    rows.append(comment)
                    if len(rows) >= args.max:
                        break
            utcs = [c["createdUtc"] for c in batch]
            boundary = max(utcs) if args.sort == "asc" else min(utcs)
            short = len(batch) < args.page_size
            print(
                f"pages={pages} kept={len(rows)} scanned={scanned} sub={subreddit or '-'}",
                file=sys.stderr,
            )
            if short:
                break
            if novel == 0:
                stalled += 1
                cursor = boundary + 1 if args.sort == "asc" else boundary - 1
                if stalled >= 2:
                    warning = "分页没有新评论，已停止。"
                    break
            else:
                stalled = 0
                cursor = boundary
            if len({*utcs}) == 1:
                warning = "某一秒内的评论超过一页，同一秒靠后的评论可能被时间游标漏掉。"
        stop = bool(error) or (warning is not None and ("上限" in warning or "没有新评论" in warning))
        if stop or len(rows) >= args.max:
            break
    return rows, {
        "scanned": scanned,
        "pages": pages,
        "warning": warning,
        "error": error,
    }


def ordered(rows: list[dict], chronological: bool) -> list[dict]:
    if not chronological:
        return list(rows)
    return sorted(rows, key=lambda row: (row["createdUtc"], row["id"]))


def file_name_for(comment: dict) -> str:
    parts = utc_parts(comment["createdUtc"])
    return f"{parts['stamp']}__{safe_id(comment['id'])}.txt"


def meta_attrs(comment: dict, parts: dict[str, str]) -> str:
    return " ".join(
        [
            f'id="{xml_escape(comment["id"])}"',
            f'timestamp="{parts["iso"]}"',
            f'date="{parts["date"]}"',
            f'time="{parts["time"]}"',
            f'unix="{comment["createdUtc"]}"',
            f'author="{xml_escape(comment["author"])}"',
            f'subreddit="{xml_escape(comment["subreddit"])}"',
            f'score="{comment["score"]}"',
            f'link_id="{xml_escape(comment["linkId"])}"',
            f'parent_id="{xml_escape(comment["parentId"])}"',
        ]
    )


def add_months(day: datetime, months: int) -> datetime:
    index = day.month - 1 + months
    year = day.year + index // 12
    month = index % 12 + 1
    if month == 12:
        following = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        following = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    last = (following - timedelta(days=1)).day
    return datetime(year, month, min(day.day, last), tzinfo=timezone.utc)


def half_years(after: str, before: str) -> list[tuple[str, str, str]]:
    """Six-month windows stepping forward from `after`, last one clipped to `before`."""
    if not after or not before or after > before:
        return []
    cursor = datetime.strptime(after, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(before, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    bins: list[tuple[str, str, str]] = []
    for _ in range(80):
        if cursor > end:
            break
        nxt = add_months(cursor, 6)
        bin_end = min(nxt - timedelta(days=1), end)
        start_s = cursor.strftime("%Y-%m-%d")
        end_s = bin_end.strftime("%Y-%m-%d")
        bins.append((f"{start_s}_{end_s}", start_s, end_s))
        cursor = nxt
    return bins


def period_windows(after: str, before: str, days: int) -> list[tuple[str, str, str]]:
    """`days`-long windows from `after`. Zero or negative falls back to six-month windows."""
    if days <= 0:
        return half_years(after, before)
    if not after or not before or after > before:
        return []
    cursor = datetime.strptime(after, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(before, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    bins: list[tuple[str, str, str]] = []
    for _ in range(5000):
        if cursor > end:
            break
        bin_end = min(cursor + timedelta(days=days - 1), end)
        start_s = cursor.strftime("%Y-%m-%d")
        end_s = bin_end.strftime("%Y-%m-%d")
        bins.append((f"{start_s}_{end_s}", start_s, end_s))
        cursor = bin_end + timedelta(days=1)
    return bins


def half_id_from_day(day: str, after: str, before: str) -> str:
    if after and day:
        end = before if before and before >= after else (day if day > after else after)
        bins = half_years(after, end)
        for period_id, start, stop in bins:
            if start <= day <= stop:
                return period_id
        if bins and day < bins[0][1]:
            return bins[0][0]
        if bins and day > bins[-1][2]:
            return bins[-1][0]
    return "未知半年"


def bare(value: str) -> str:
    return re.sub(r"^t[13]_", "", value or "", count=1, flags=re.I)


def assign_depth(rows: list[dict]) -> None:
    by_id = {row["id"]: row for row in rows if row.get("kind") != "post"}
    visiting: set[str] = set()

    def depth_of(row: dict):
        if row.get("kind") == "post":
            return 0
        if row.get("depth") is not None:
            return row["depth"]
        parent = row.get("parentId") or ""
        parent_bare = bare(parent)
        if (not parent) or parent.startswith("t3_") or parent_bare == bare(row.get("linkId") or ""):
            row["depth"] = 1
            return 1
        parent_row = by_id.get(parent_bare)
        if parent_row is None or row["id"] in visiting:
            return None
        visiting.add(row["id"])
        parent_depth = depth_of(parent_row)
        visiting.discard(row["id"])
        row["depth"] = None if parent_depth is None else parent_depth + 1
        return row["depth"]

    for row in rows:
        if row.get("kind") != "post":
            row["depth"] = depth_of(row)


def slim_post(raw: dict) -> dict | None:
    cid = raw.get("id")
    created = raw.get("created_utc")
    if not isinstance(cid, str):
        return None
    try:
        unix = int(created)
    except (TypeError, ValueError):
        return None
    title = raw.get("title") if isinstance(raw.get("title"), str) else ""
    selftext = raw.get("selftext") if isinstance(raw.get("selftext"), str) else ""
    if is_removed(selftext):
        selftext = ""
    body = "\n\n".join(part for part in (title.strip(), selftext.strip()) if part)
    if not body:
        return None
    subreddit = raw.get("subreddit") if isinstance(raw.get("subreddit"), str) else ""
    permalink = raw.get("permalink") if isinstance(raw.get("permalink"), str) else ""
    if permalink.startswith("http"):
        url = permalink
    elif permalink.startswith("/"):
        url = "https://www.reddit.com" + permalink
    elif subreddit:
        url = f"https://www.reddit.com/r/{subreddit}/comments/{cid}/"
    else:
        url = ""
    score = raw.get("score")
    try:
        score_n = int(score)
    except (TypeError, ValueError):
        score_n = 0
    flair = raw.get("link_flair_text") if isinstance(raw.get("link_flair_text"), str) else ""
    return {
        "id": cid,
        "kind": "post",
        "author": raw.get("author") if isinstance(raw.get("author"), str) else "",
        "body": body,
        "title": title,
        "selftext": selftext,
        "createdUtc": unix,
        "subreddit": subreddit,
        "score": score_n,
        "linkId": cid,
        "parentId": "",
        "permalink": url,
        "linkTitle": title,
        "linkFlair": flair,
        "over18": raw.get("over_18") is True,
        "depth": 0,
        "group": "",
    }


def fetch_post_batch(ids: list[str], delay_on_limit: float) -> list[dict]:
    url = POST_API + "?ids=" + ",".join(ids)
    last = "Arctic Shift 没有返回帖子"
    for attempt in range(5):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                payload = json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            message = friendly(detail[:180], exc.code)
            if exc.code not in {408, 422, 429, 500, 502, 503, 504} or attempt == 4:
                raise ApiError(message, exc.code) from exc
            last = message
            retry_pause(attempt, delay_on_limit if exc.code == 429 else 0.0)
            continue
        except TRANSIENT_TRANSPORT_ERRORS as exc:
            print(f"  post API attempt {attempt + 1}/5: {type(exc).__name__}: {exc}", file=sys.stderr)
            if attempt == 4:
                raise ApiError(f"Arctic Shift 帖子请求连续失败: {type(exc).__name__}: {exc}") from exc
            retry_pause(attempt)
            continue
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            raise ApiError("返回里没有帖子列表")
        posts = []
        for item in data:
            if isinstance(item, dict):
                post = slim_post(item)
                if post:
                    posts.append(post)
        return posts
    raise ApiError(last)


def attach_posts(rows: list[dict], args: argparse.Namespace) -> list[dict]:
    ids: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if row.get("kind") == "post":
            continue
        link = bare(row.get("linkId") or "")
        if link and link not in seen:
            seen.add(link)
            ids.append(link)
    ids = ids[:300]
    found: dict[str, dict] = {}
    for index in range(0, len(ids), 80):
        batch = fetch_post_batch(ids[index:index + 80], max(args.delay, 1))
        for post in batch:
            found[post["id"]] = post
        if index + 80 < len(ids):
            time.sleep(args.delay)
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row.get("group") or "", []).append(row)
    out: list[dict] = []
    for group, items in grouped.items():
        comments = [row for row in items if row.get("kind") != "post"]
        used: set[str] = set()
        posts: list[dict] = []
        for comment in comments:
            post = found.get(bare(comment.get("linkId") or ""))
            if not post:
                continue
            comment["linkTitle"] = post.get("title") or comment.get("linkTitle") or ""
            comment["linkFlair"] = post.get("linkFlair") or ""
            if post["id"] in used:
                continue
            used.add(post["id"])
            if args.exclude_nsfw and post.get("over18"):
                continue
            clone = dict(post)
            clone["group"] = group
            posts.append(clone)
        assign_depth(comments)
        out.extend(posts)
        out.extend(comments)
    return out


def clean_document(body: str, args: argparse.Namespace) -> tuple[str, str]:
    text = strip_controls(body.replace("\r\n", "\n").replace("\r", "\n"))
    quote = ""
    if not args.keep_quotes:
        fresh: list[str] = []
        quoted: list[str] = []
        for line in text.split("\n"):
            if re.match(r"^\s*>", line):
                quoted.append(re.sub(r"^\s*>\s?", "", line))
            else:
                fresh.append(line)
        text = "\n".join(fresh).strip()
        quote = "\n".join(quoted).strip()

    def scrub(value: str) -> str:
        if not args.keep_urls or not args.keep_markdown:
            value = re.sub(r"\[([^\]]*)\]\((?:https?://|www\.)[^)\s]+\)", r"\1", value)
        if not args.keep_urls:
            value = re.sub(r"\b(?:https?://|www\.)\S+", " ", value, flags=re.I)
        if not args.keep_markdown:
            value = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", value)
            value = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", value)
            value = re.sub(r"(\*\*|__)(.*?)\1", r"\2", value)
            value = re.sub(r"(\*|_)(.*?)\1", r"\2", value)
            value = re.sub(r"~~(.*?)~~", r"\1", value)
            value = re.sub(r"`{1,3}[^`]*`{1,3}", " ", value)
            value = re.sub(r"^#{1,6}\s+", "", value, flags=re.M)
            value = re.sub(r"^\s*[-*+]\s+", "", value, flags=re.M)
        if not args.keep_mentions:
            value = re.sub(r"(^|[^A-Za-z0-9_])/?u/[A-Za-z0-9_-]{2,30}\b", r"\1", value)
            value = re.sub(r"(^|[^A-Za-z0-9_])/?r/[A-Za-z0-9_]{2,50}\b", r"\1", value)
        value = value.replace("<", "＜").replace(">", "＞")
        return re.sub(r"[ \t]{2,}", " ", value)

    text = scrub(text)
    quote = scrub(quote) if quote else ""
    if args.flatten:
        text = re.sub(r"\s+", " ", text).strip()
        quote = re.sub(r"\s+", " ", quote).strip()
    else:
        text = text.strip()
        quote = quote.strip()
    return text, quote


def group_key(row: dict, split: str, after: str = "", before: str = "") -> str:
    if split == "none":
        return "corpus"
    if split == "flair":
        return (row.get("linkFlair") or "").strip() or "未标flair"
    if split == "month":
        return utc_parts(row["createdUtc"])["date"][:7]
    if row.get("group"):
        return str(row["group"])
    day = utc_parts(row["createdUtc"])["date"]
    return half_id_from_day(day, after, before)


def file_stub(name: str) -> str:
    cleaned = re.sub(r"_+", "_", re.sub(r"[^\w.\-]+", "_", name, flags=re.UNICODE)).strip("_")
    return (cleaned or "corpus")[:80]


def write_outputs(rows: list[dict], out: Path, record: dict, flatten: bool, chronological: bool) -> None:
    del flatten
    out.mkdir(parents=True, exist_ok=True)
    filters = record.get("filters", {})
    holder = argparse.Namespace(
        keep_urls=not filters.get("stripUrls", True),
        keep_markdown=not filters.get("stripMarkdown", True),
        keep_mentions=not filters.get("stripUsernames", True),
        keep_quotes=not filters.get("separateQuotes", True),
        flatten=bool(filters.get("flatten", False)),
    )
    chosen = ordered(rows, chronological)
    # Keep fetched parent posts for context, never contaminate the comment corpus by default.
    context_by_group = {}
    for row in chosen:
        if row.get("kind") == "post":
            group = str(row.get("group") or "")
            context_by_group.setdefault(group, {})[str(row.get("id") or "")] = row
    if not filters.get("includePostsInCorpus", False):
        chosen = [row for row in chosen if row.get("kind") != "post"]
    buckets: dict[str, list[tuple[dict, str, str, int]]] = {}
    split = str(filters.get("split") or "half")
    for row in chosen:
        text, quote = clean_document(row.get("body") or "", holder)
        if not text:
            continue
        buckets.setdefault(group_key(row, split, str(filters.get("after") or ""), str(filters.get("before") or "")), []).append((row, text, quote, word_count(text)))
    file_stats = []
    for name in sorted(buckets):
        items = buckets[name]
        stub = file_stub(name)
        (out / f"{stub}.txt").write_text("\n\n".join(item[1] for item in items) + "\n", encoding="utf-8-sig")
        index_lines = ["kind\tid\ttimestamp_utc\tdepth\tlink_id\tflair\tauthor\tscore\twords\tpermalink"]
        quotes = []
        for row, _text, quote, words in items:
            parts = utc_parts(row["createdUtc"])
            depth = "" if row.get("depth") is None else row["depth"]
            cells = [
                row.get("kind") or "comment",
                row.get("id") or "",
                parts["iso"],
                depth,
                row.get("linkId") or "",
                row.get("linkFlair") or "",
                row.get("author") or "",
                row.get("score") or 0,
                words,
                row.get("permalink") or "",
            ]
            index_lines.append("\t".join(re.sub(r"[\t\r\n]+", " ", str(cell)).strip() for cell in cells))
            if quote:
                quotes.append(quote)
        (out / f"{stub}.index.txt").write_text("\n".join(index_lines) + "\n", encoding="utf-8-sig")
        # Stable machine-readable record boundaries (unlike blank-line-delimited TXT).
        documents = []
        for row, clean_text, quote, words in items:
            context = context_by_group.get(str(row.get("group") or ""), {}).get(bare(row.get("linkId") or ""), {})
            doc = {
                "kind": row.get("kind") or "comment",
                "id": row.get("id") or "",
                "timestamp_utc": utc_parts(row["createdUtc"])["iso"],
                "link_id": row.get("linkId") or "",
                "parent_id": row.get("parentId") or "",
                "post_title": row.get("linkTitle") or context.get("title") or "",
                "post_flair": row.get("linkFlair") or context.get("linkFlair") or "",
                "permalink": row.get("permalink") or "",
                "word_count": words,
                "cleaned_text": clean_text,
                "excluded_quotes": quote,
            }
            documents.append(doc)
        (out / f"{stub}.jsonl").write_text(
            "".join(json.dumps(doc, ensure_ascii=False) + "\n" for doc in documents),
            encoding="utf-8"
        )
        with (out / f"{stub}.csv").open("w", encoding="utf-8-sig", newline="") as csv_out:
            fields = list(documents[0].keys())
            writer = csv.DictWriter(csv_out, fieldnames=fields)
            writer.writeheader()
            writer.writerows(documents)
        if quotes:
            (out / f"{stub}.quotes.txt").write_text("\n\n".join(quotes) + "\n", encoding="utf-8-sig")
        file_stats.append({"name": f"{stub}.txt", "docs": len(items), "words": sum(item[3] for item in items)})
    record.setdefault("result", {})["files"] = file_stats
    record["result"]["words"] = sum(item["words"] for item in file_stats)
    record["result"]["documentsExported"] = sum(item["docs"] for item in file_stats)
    record["result"]["commentOnlyExport"] = not bool(filters.get("includePostsInCorpus", False))
    (out / "README.txt").write_text(readme(record), encoding="utf-8-sig")
    (out / "query.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def readme(record: dict) -> str:
    filters = record.get("filters", {})
    result = record.get("result", {})
    files = result.get("files") or []
    lines = [
        "Shift Corpus",
        "============",
        "",
        "每个不带 .index 或 .quotes 的 txt 是一个语料库。不要把 README、index、quotes 加进 AntConc。",
        "同一个 txt 里，文本之间空一行。时间、楼层和 flair 在同名 .index.txt。",
        "",
        f"检索时间 (UTC): {record.get('retrievedAt', '')}",
        "数据源: Arctic Shift  https://arctic-shift.photon-reddit.com",
        f"版块: {', '.join(filters.get('subreddits') or []) or '（未限定）'}",
        f"日期: {filters.get('after') or '不限'} 至 {filters.get('before') or '不限'}（含结束日，UTC）",
        f"每段最多保留: {filters.get('maxKeep')}",
        f"按半年分别检索: {bool(filters.get('halfFetch'))}",
        f"分层抽样: {bool(filters.get('stratifiedSample'))}"
        + (
            f"，每个半年 {filters.get('samplePerPeriod')} 条，按天定额、一天内按钟点各抽 1 条，seed {filters.get('seed')}"
            if filters.get("stratifiedSample")
            else ""
        ),
        f"只抓: {filters.get('onlyPeriod') or '全部'}",
        f"切分: {filters.get('split') or 'half'}",
        f"评论采集: {result.get('comments', 0)}  关联帖子抓取: {result.get('posts', 0)}  导出语料词数: {result.get('words', 0)}",
        f"导出帖子正文: {bool(filters.get('includePostsInCorpus', False))}；默认只导出评论正文。",
        "CSV/JSONL 每条记录单独保存，即使评论正文存在空行也可准确对应 ID。",
    ]
    if result.get("sampleTarget") is not None:
        lines.append(f"按天抽样留下: {result.get('sampleKept')} / 目标 {result.get('sampleTarget')}")
    lines.extend([
        "",
        "各文件",
        "------",
    ])
    lines.extend(f"{item['name']}: {item['docs']} 条, {item['words']} 词" for item in files)
    lines.extend([
        "",
        "楼层 0 是帖子，1 是顶层评论。父评论不在样本里时楼层留空。",
        "AntConc 里为每个 txt 单独建一个语料库，用来比较半年、月份或 flair。",
        "重跑: python3 shift_corpus.py --from-json query.json --out rerun",
        "",
    ])
    if result.get("warning"):
        lines.append("警告: " + str(result["warning"]))
    if result.get("error"):
        lines.append("错误（结果可能不完整）: " + str(result["error"]))
    lines.append("")
    return "\n".join(lines)


def build_record(args: argparse.Namespace, rows: list[dict], stats: dict, retrieved: str) -> dict:
    ordered_rows = ordered(rows, not args.keep_order)
    earliest = utc_parts(ordered_rows[0]["createdUtc"])["iso"] if ordered_rows else None
    latest = utc_parts(ordered_rows[-1]["createdUtc"])["iso"] if ordered_rows else None
    if not args.keep_order and ordered_rows:
        earliest = utc_parts(min(rows, key=lambda r: r["createdUtc"])["createdUtc"])["iso"]
        latest = utc_parts(max(rows, key=lambda r: r["createdUtc"])["createdUtc"])["iso"]
    return {
        "source": "arctic-shift",
        "endpoint": API,
        "retrievedAt": retrieved,
        "filters": {
            "body": args.body,
            "subreddits": args.subreddits,
            "author": args.author,
            "linkId": args.link_id,
            "parentId": args.parent_id,
            "topLevelOnly": bool(args.top_level and not args.parent_id),
            "after": args.after,
            "before": args.before,
            "sort": args.sort,
            "maxKeep": args.max,
            "minScore": args.min_score,
            "minWords": args.min_words,
            "excludeDeleted": bool(args.exclude_deleted),
            "excludeAutomod": bool(args.exclude_automod),
            "excludeBots": bool(args.exclude_bots),
            "excludeNsfw": bool(args.exclude_nsfw),
            "englishOnly": bool(args.english),
            "nearDup": bool(args.near_dup),
            "includePosts": bool(args.with_posts),
            "includePostsInCorpus": bool(args.include_posts_in_corpus),
            "partialPolicy": args.partial_policy,
            "halfFetch": bool(args.half),
            "periodDays": args.period_days,
            "onlyPeriod": args.only_period,
            "stratifiedSample": bool(args.stratified_sample),
            "samplePerPeriod": args.sample_per_period,
            "scoreBins": args.score_bins,
            "seed": args.seed,
            "localText": args.local,
            "localCaseSensitive": bool(args.case_sensitive),
            "flatten": bool(args.flatten),
            "chronological": not args.keep_order,
            "split": args.split,
            "stripUrls": not args.keep_urls,
            "stripMarkdown": not args.keep_markdown,
            "stripUsernames": not args.keep_mentions,
            "separateQuotes": not args.keep_quotes,
        },
        "result": {
            "comments": sum(1 for row in rows if row.get("kind") != "post"),
            "posts": sum(1 for row in rows if row.get("kind") == "post"),
            "words": 0,
            "earliest": earliest,
            "latest": latest,
            "scanned": stats["scanned"],
            "pages": stats["pages"],
            "warning": stats["warning"],
            "error": stats["error"],
            "sampleTarget": stats.get("sampleTarget"),
            "sampleKept": stats.get("sampleKept"),
            "windows": stats.get("windows", []),
            "files": [],
        },
    }


def load_json_args(path: Path, base: argparse.Namespace) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    filters = payload.get("filters") if isinstance(payload, dict) else None
    if not isinstance(filters, dict):
        raise SystemExit("query.json 里没有 filters 对象。")
    base.body = str(filters.get("body") or "")
    subs = filters.get("subreddits") or []
    if isinstance(subs, str):
        subs = [subs]
    base.subreddits = [str(s) for s in subs]
    base.author = str(filters.get("author") or "")
    base.link_id = str(filters.get("linkId") or "")
    base.parent_id = str(filters.get("parentId") or "")
    base.top_level = bool(filters.get("topLevelOnly"))
    base.after = str(filters.get("after") or "")
    base.before = str(filters.get("before") or "")
    base.sort = "asc" if filters.get("sort") == "asc" else "desc"
    if filters.get("maxKeep"):
        base.max = int(filters["maxKeep"])
    score = filters.get("minScore")
    base.min_score = int(score) if isinstance(score, (int, float)) and not isinstance(score, bool) else None
    if score is None:
        base.min_score = None
    base.keep_deleted = not bool(filters.get("excludeDeleted", True))
    base.exclude_automod = bool(filters.get("excludeAutomod", False))
    base.exclude_bots = bool(filters.get("excludeBots", False))
    base.exclude_nsfw = bool(filters.get("excludeNsfw", False))
    base.english = bool(filters.get("englishOnly", False))
    base.near_dup = bool(filters.get("nearDup", False))
    base.with_posts = bool(filters.get("includePosts", False))
    base.include_posts_in_corpus = bool(filters.get("includePostsInCorpus", False))
    base.partial_policy = str(filters.get("partialPolicy") or "proportional")
    base.half = bool(filters.get("halfFetch", False))
    base.period_days = int(filters.get("periodDays") or 0)
    base.only_period = str(filters.get("onlyPeriod") or "")
    base.stratified_sample = bool(filters.get("stratifiedSample", False))
    if filters.get("samplePerPeriod"):
        base.sample_per_period = int(filters["samplePerPeriod"])
    if filters.get("scoreBins"):
        base.score_bins = str(filters["scoreBins"])
    if filters.get("seed") is not None:
        base.seed = int(filters["seed"])
    words = filters.get("minWords")
    base.min_words = int(words) if isinstance(words, int) and not isinstance(words, bool) else None
    split = filters.get("split")
    base.split = split if split in {"none", "half", "month", "flair"} else "half"
    base.keep_urls = not bool(filters.get("stripUrls", True))
    base.keep_markdown = not bool(filters.get("stripMarkdown", True))
    base.keep_mentions = not bool(filters.get("stripUsernames", True))
    base.keep_quotes = not bool(filters.get("separateQuotes", True))
    base.local = str(filters.get("localText") or "")
    base.case_sensitive = bool(filters.get("localCaseSensitive", False))
    base.flatten = bool(filters.get("flatten", False))
    base.keep_order = not bool(filters.get("chronological", True))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="把 Arctic Shift 的 Reddit 评论导出成 AntConc 语料。")
    parser.add_argument("--from-json", dest="from_json", help="用之前下载的 query.json 重跑")
    parser.add_argument("--body", default="", help="正文关键词，PostgreSQL websearch 语法")
    parser.add_argument("--subreddit", action="append", default=[], help="版块，可重复，或用逗号分隔")
    parser.add_argument("--author", default="", help="作者，不带 u/")
    parser.add_argument("--link-id", default="", help="帖子 id、t3_ id，或 Reddit 链接")
    parser.add_argument("--parent-id", default="", help="父评论 id，可带 t1_")
    parser.add_argument("--top-level", action="store_true", help="只要顶层评论")
    parser.add_argument("--after", default="", help="开始日期 YYYY-MM-DD，含当天，UTC")
    parser.add_argument("--before", default="", help="结束日期 YYYY-MM-DD，含当天，UTC")
    parser.add_argument("--sort", choices=("asc", "desc"), default="desc")
    parser.add_argument("--max", type=int, default=300, help="最多保留多少条，1-20000")
    parser.add_argument("--min-score", type=int, default=None)
    parser.add_argument("--min-words", type=int, default=None)
    parser.add_argument("--keep-deleted", action="store_true", help="保留 [deleted]/[removed]")
    parser.add_argument("--exclude-automod", action="store_true")
    parser.add_argument("--exclude-bots", action="store_true")
    parser.add_argument("--exclude-nsfw", action="store_true")
    parser.add_argument("--english", action="store_true", help="只保留像英文的正文")
    parser.add_argument("--near-dup", action="store_true", help="去掉开头相同的复制文本")
    parser.add_argument("--with-posts", action="store_true", help="关联帖子仅作为评论元信息（title/flair），默认不计入词频")
    parser.add_argument("--include-posts-in-corpus", action="store_true", help="兼容旧行为：额外将帖子正文计入 AntConc 语料（不推荐）")
    parser.add_argument("--partial-policy", choices=("proportional", "full"), default="proportional", help="最后不足180天的窗口按天数比例调整样本目标；full则保持180")
    parser.add_argument("--half", action="store_true", help="按时间段分别检索，每段单独计 --max")
    parser.add_argument("--period-days", type=int, default=0, help="每段多少天。0 表示仍按 6 个月切")
    parser.add_argument("--only-period", default="", help="只抓一段，例如 2022-05-01_2022-06-29")
    parser.add_argument("--stratified-sample", action="store_true", help="每个半年按天定额抽样，一天内再按钟点分散")
    parser.add_argument("--sample-per-period", type=int, default=2000, help="每个半年保留的评论数；不加 --half 时是整段日期的总数")
    parser.add_argument("--score-bins", default="0-1,2-10,11+", help="保留该参数以免旧命令失败，抽样不再按分数分层")
    parser.add_argument("--seed", type=int, default=1, help="抽样随机种子，同一种子可复现")
    parser.add_argument("--split", choices=("half", "month", "flair", "none"), default="half")
    parser.add_argument("--keep-urls", action="store_true")
    parser.add_argument("--keep-markdown", action="store_true")
    parser.add_argument("--keep-mentions", action="store_true")
    parser.add_argument("--keep-quotes", action="store_true", help="引用行留在语料正文里")
    parser.add_argument("--local", default="", help="抓下来之后再按子串过滤")
    parser.add_argument("--case-sensitive", action="store_true")
    parser.add_argument("--flatten", action="store_true", help="把每条评论压成一行")
    parser.add_argument("--keep-order", action="store_true", help="按检索顺序导出，而不是时间升序")
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--max-pages", type=int, default=400)
    parser.add_argument("--delay", type=float, default=0.35)
    parser.add_argument("--out", default="shift-corpus")
    args = parser.parse_args(argv)
    if args.from_json:
        load_json_args(Path(args.from_json), args)
    raw_subs = args.subreddits if args.from_json else args.subreddit
    args.subreddits = normalize_subreddits(list(raw_subs))
    args.author = re.sub(r"^/?u/", "", args.author.strip(), flags=re.I)
    args.link_id = normalize_link(args.link_id)
    args.parent_id = normalize_parent(args.parent_id)
    args.body = args.body.strip()
    args.local = args.local.strip()
    args.exclude_deleted = not args.keep_deleted
    if args.author and not re.fullmatch(r"[A-Za-z0-9_-]{2,30}", args.author):
        raise SystemExit(f"作者名无效: {args.author}")
    if args.link_id and not re.fullmatch(r"[A-Za-z0-9]{2,20}", args.link_id):
        raise SystemExit(f"帖子 ID 无效: {args.link_id}")
    if args.parent_id and not re.fullmatch(r"(t1_)?[A-Za-z0-9]{2,20}", args.parent_id):
        raise SystemExit(f"父评论 ID 无效: {args.parent_id}")
    for label, value in (("开始日期", args.after), ("结束日期", args.before)):
        if value and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise SystemExit(f"{label}要写成 YYYY-MM-DD。")
    if args.after and args.before and args.after > args.before:
        raise SystemExit("开始日期晚于结束日期。")
    if args.half and (not args.after or not args.before):
        raise SystemExit("分段检索时，开始和结束日期都要填。")
    if not (0 <= args.period_days <= 3660):
        raise SystemExit("--period-days 要在 0 到 3660 之间。")
    if not (1 <= args.sample_per_period <= 20000):
        raise SystemExit("--sample-per-period 要在 1 到 20000 之间。")
    parse_score_bins(args.score_bins)
    if args.include_posts_in_corpus and not args.with_posts:
        raise SystemExit("--include-posts-in-corpus 必须同时加 --with-posts")
    if args.stratified_sample and (not args.after or not args.before):
        raise SystemExit("按天抽样时，开始和结束日期都要填。")
    if not (1 <= args.max <= 20000):
        raise SystemExit("--max 要在 1 到 20000 之间。")
    if not (1 <= args.page_size <= 100):
        raise SystemExit("--page-size 要在 1 到 100 之间。")
    has_scope = bool(args.subreddits or args.author or args.link_id or args.parent_id or args.top_level)
    has_anchor = bool(args.subreddits or args.author or args.link_id or args.parent_id)
    if args.body and not has_scope:
        raise SystemExit("正文关键词必须同时指定版块、作者、帖子、父评论，或加上 --top-level。")
    if not args.body and not has_anchor:
        raise SystemExit("请至少指定版块、作者、帖子或父评论。")
    return args


def parse_score_bins(spec: str) -> list[tuple[str, int, int | None]]:
    bins: list[tuple[str, int, int | None]] = []
    for piece in spec.split(","):
        label = piece.strip()
        if not label:
            continue
        plus = re.fullmatch(r"(-?\d+)\+", label)
        span = re.fullmatch(r"(-?\d+)\s*-\s*(-?\d+)", label)
        if plus:
            bins.append((label, int(plus.group(1)), None))
        elif span:
            lo, hi = int(span.group(1)), int(span.group(2))
            if lo > hi:
                raise SystemExit(f"分数段上下界颠倒: {label}")
            bins.append((label, lo, hi))
        else:
            raise SystemExit(f"无法识别的分数段: {label}。例子: 0-1,2-10,11+")
    if not bins:
        raise SystemExit("至少要一个分数段。")
    return bins


def each_day(start: str, end: str) -> list[str]:
    cursor = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    stop = datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    days: list[str] = []
    while cursor <= stop:
        days.append(cursor.strftime("%Y-%m-%d"))
        cursor += timedelta(days=1)
    return days


def day_quotas(days: list[str], target: int, seed: str) -> dict[str, int]:
    """Equal daily quota. Remainder days are chosen with `seed`, not the first days."""
    count = len(days)
    if count == 0:
        return {}
    base, extra = divmod(target, count)
    rng = random.Random(seed)
    bonus = set(rng.sample(days, extra)) if extra else set()
    return {day: base + (1 if day in bonus else 0) for day in days}


def slot_moment(day: str, index: int, quota: int, rng: random.Random) -> tuple[int, int]:
    """Random UTC second inside slot `index`, and the exclusive end of that day."""
    start = int(datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
    end = start + 86400
    if quota <= 1:
        return rng.randrange(start, end), end
    span = 86400 / quota
    lo = start + int(index * span)
    hi = start + int((index + 1) * span)
    if hi <= lo:
        hi = min(end, lo + 1)
    if lo >= end:
        lo = end - 1
        hi = end
    return rng.randrange(lo, hi), end


def sample_params(args: argparse.Namespace, subreddit: str, after_ts: int, before_ts: int) -> list[tuple[str, str]]:
    params: list[tuple[str, str]] = [
        ("limit", "100"),
        ("sort", "asc"),
        ("after", str(after_ts)),
        ("before", str(before_ts)),
    ]
    if args.body:
        params.append(("body", args.body))
    if subreddit:
        params.append(("subreddit", subreddit))
    if args.author:
        params.append(("author", args.author))
    if args.link_id:
        params.append(("link_id", args.link_id))
    if args.parent_id:
        params.append(("parent_id", args.parent_id))
    elif args.top_level:
        params.append(("parent_id", ""))
    return params


def draw_comment(
    args: argparse.Namespace,
    moment: int,
    day_start: int,
    day_end: int,
    rng: random.Random,
    seen: set[str],
    dup_exact: set[str],
    dup_prefix: set[str],
    tally: dict[str, int],
) -> tuple[dict | None, str | None]:
    """One page after `moment`; up to two further pages if filters leave nothing."""
    subs = args.subreddits or [""]
    for subreddit in subs:
        cursor = moment - 1
        for _attempt in range(3):
            if tally["pages"]:
                time.sleep(args.delay)
            try:
                batch = fetch_page(sample_params(args, subreddit, cursor, day_end), max(args.delay, 1))
            except ApiError as exc:
                return None, str(exc)
            tally["pages"] += 1
            tally["scanned"] += len(batch)
            if not batch:
                break
            eligible: list[tuple[dict, str, str | None]] = []
            for comment in batch:
                unix = comment["createdUtc"]
                if unix < day_start or unix >= day_end or unix < moment:
                    continue
                if comment["id"] in seen:
                    continue
                if not keep_comment(comment, args):
                    continue
                exact, prefix = text_fingerprint(comment["body"])
                if args.near_dup and seen_duplicate(exact, prefix, dup_exact, dup_prefix):
                    continue
                eligible.append((comment, exact, prefix))
            if eligible:
                comment, exact, prefix = eligible[rng.randrange(len(eligible))]
                seen.add(comment["id"])
                if args.near_dup:
                    remember_duplicate(exact, prefix, dup_exact, dup_prefix)
                return comment, None
            nxt = max(comment["createdUtc"] for comment in batch)
            if nxt <= cursor or len(batch) < 100:
                break
            cursor = nxt
    return None, None


def sample_range(args: argparse.Namespace, period_id: str, start: str, end: str) -> tuple[list[dict], dict]:
    days = each_day(start, end)
    if not days:
        return [], {"scanned": 0, "pages": 0, "warning": None, "error": "没有可抽的日期。", "sampleTarget": 0, "sampleKept": 0}
    quotas = day_quotas(days, args.sample_per_period, f"{args.seed}:{period_id}:quota")
    print(
        f"sample {period_id} seed={args.seed} days={len(days)} target={args.sample_per_period}",
        file=sys.stderr,
    )
    rows: list[dict] = []
    seen: set[str] = set()
    dup_exact: set[str] = set()
    dup_prefix: set[str] = set()
    tally = {"scanned": 0, "pages": 0}
    error = None
    for day in days:
        quota = quotas[day]
        if quota <= 0:
            print(f"  {day} quota=0 kept=0", file=sys.stderr)
            continue
        rng = random.Random(f"{args.seed}:{period_id}:{day}")
        kept = 0
        day_start = int(datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
        for index in range(quota):
            moment, day_end = slot_moment(day, index, quota, rng)
            comment, draw_error = draw_comment(
                args, moment, day_start, day_end, rng, seen, dup_exact, dup_prefix, tally
            )
            if draw_error:
                error = draw_error
                break
            if comment:
                comment["group"] = period_id
                rows.append(comment)
                kept += 1
        print(f"  {day} quota={quota} kept={kept}", file=sys.stderr)
        if error:
            break
    print(
        f"  comments target={args.sample_per_period} kept={len(rows)} short={args.sample_per_period - len(rows)} pages={tally['pages']}",
        file=sys.stderr,
    )
    return rows, {
        "scanned": tally["scanned"],
        "pages": tally["pages"],
        "warning": None,
        "error": error,
        "sampleTarget": args.sample_per_period,
        "sampleKept": len(rows),
    }


def attach_or_depth(rows: list[dict], args: argparse.Namespace, stats: dict) -> list[dict]:
    if args.with_posts and rows:
        try:
            return attach_posts(rows, args)
        except ApiError as exc:
            stats["error"] = str(exc)
            return rows
    assign_depth(rows)
    return rows


def gather(args: argparse.Namespace) -> tuple[list[dict], dict]:
    if args.stratified_sample:
        if args.half:
            windows = period_windows(args.after, args.before, args.period_days)
            if args.only_period:
                windows = [item for item in windows if item[0] == args.only_period]
        else:
            windows = [(f"{args.after}_{args.before}", args.after, args.before)]
        if not windows:
            return [], {"scanned": 0, "pages": 0, "warning": None, "error": "没有可抓的半年。", "sampleTarget": 0, "sampleKept": 0}
        all_rows: list[dict] = []
        scanned = 0
        pages = 0
        warning = None
        error = None
        target = 0
        kept = 0
        window_stats = []
        for period_id, start, end in windows:
            print(f"period {period_id} {start}..{end}", file=sys.stderr)
            local = argparse.Namespace(**vars(args))
            local.after = start
            local.before = end
            local.half = False
            number_of_days = len(each_day(start, end))
            if (args.period_days > 0 and args.partial_policy == "proportional"
                    and number_of_days < args.period_days):
                local.sample_per_period = max(1, round(args.sample_per_period * number_of_days / args.period_days))
            rows, stats = sample_range(local, period_id, start, end)
            window_stats.append({
                "period": period_id, "start": start, "end": end,
                "days": number_of_days, "sampleTarget": stats.get("sampleTarget"),
                "sampleKept": stats.get("sampleKept"),
                "scanned": stats.get("scanned"), "pages": stats.get("pages"),
                "error": stats.get("error")
            })
            rows = attach_or_depth(rows, local, stats)
            all_rows.extend(rows)
            scanned += stats["scanned"]
            pages += stats["pages"]
            target += stats.get("sampleTarget") or 0
            kept += stats.get("sampleKept") or 0
            warning = stats["warning"] or warning
            if stats["error"]:
                error = stats["error"]
                break
        return all_rows, {
            "scanned": scanned,
            "pages": pages,
            "warning": warning,
            "error": error,
            "sampleTarget": target,
            "sampleKept": kept,
            "windows": window_stats,
        }
    if args.half:
        bins = period_windows(args.after, args.before, args.period_days)
        if args.only_period:
            bins = [item for item in bins if item[0] == args.only_period]
        if not bins:
            return [], {"scanned": 0, "pages": 0, "warning": None, "error": "没有可抓的半年。"}
        all_rows: list[dict] = []
        scanned = 0
        pages = 0
        warning = None
        error = None
        for period_id, start, end in bins:
            print(f"period {period_id} {start}..{end}", file=sys.stderr)
            local = argparse.Namespace(**vars(args))
            local.after = start
            local.before = end
            local.half = False
            rows, stats = collect(local)
            for row in rows:
                row["group"] = period_id
            rows = attach_or_depth(rows, local, stats)
            all_rows.extend(rows)
            scanned += stats["scanned"]
            pages += stats["pages"]
            warning = stats["warning"] or warning
            if stats["error"]:
                error = stats["error"]
                break
        return all_rows, {"scanned": scanned, "pages": pages, "warning": warning, "error": error}
    rows, stats = collect(args)
    rows = attach_or_depth(rows, args, stats)
    return rows, stats


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows, stats = gather(args)
    record = build_record(args, rows, stats, retrieved)
    if not rows:
        print(stats["error"] or stats["warning"] or "没有符合条件的评论。", file=sys.stderr)
        return 1
    write_outputs(rows, Path(args.out), record, args.flatten, not args.keep_order)
    print(f"wrote {len(rows)} texts -> {args.out}", file=sys.stderr)
    if stats["error"]:
        print(stats["error"], file=sys.stderr)
        return 2
    if stats["warning"]:
        print(stats["warning"], file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("已中断。", file=sys.stderr)
        raise SystemExit(130)

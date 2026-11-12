#!/usr/bin/env python3
"""
MuttSearch - Fast, MIME-aware search utility for local Mutt mbox archives.

Designed for monthly inbox/outbox mbox naming conventions such as:
    rebuts_<month>_<year>   (received / inbox)
    enviats_<month>_<year>  (sent / outbox)

Aligns with Mutt 2.4.3 Manual specifications:
  - Ch. 4.2 & 8.3 : Regex (~) vs. literal substring (=) & case-sensitivity control
  - Ch. 4.9       : Local mbox ("From_ " separator) auto-detection
  - Ch. 4.13.1    : Preserves file atime/mtime so Mutt new-mail polling still works
  - Ch. 5.6       : Attachment counting/matching (excluding PGP/PKCS7 signatures)
  - Ch. 9.1       : Opens aggregated search results in Mutt via `mutt -R -f`
  - Ch. 9.3       : Equivalent to $thorough_search=yes and $rfc2047_parameters=yes
"""

import argparse
import datetime
import email
import email.header
import email.utils
import gzip
import mailbox
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Pattern, Tuple

VERSION = "1.0.0"

# Month mapping supporting Catalan/Valencian abbreviations (from your filenames),
# numeric months (1-12 / 01-12), and English 3-letter fallbacks.
MONTH_ALIASES: Dict[str, str] = {
    "1": "gen", "01": "gen", "gen": "gen", "jan": "gen",
    "2": "feb", "02": "feb", "feb": "feb",
    "3": "mar", "03": "mar", "mar": "mar",
    "4": "abr", "04": "abr", "abr": "abr", "apr": "abr",
    "5": "mai", "05": "mai", "mai": "mai", "may": "mai",
    "6": "jun", "06": "jun", "jun": "jun",
    "7": "jul", "07": "jul", "jul": "jul",
    "8": "ago", "08": "ago", "ago": "ago", "aug": "ago",
    "9": "sep", "09": "sep", "sep": "sep", "set": "sep",
    "10": "oct", "oct": "oct",
    "11": "nov", "nov": "nov",
    "12": "des", "des": "des", "dec": "des",
}

# Ignored signature/vcard MIME types per Mutt Manual Ch. 5.6 (Example 5.2)
IGNORED_ATTACHMENT_MIMES = (
    "application/pgp-signature",
    "application/pgp-encrypted",
    "application/pgp-keys",
    "application/pkcs7-signature",
    "text/x-vcard",
)


class Colors:
    """ANSI color helpers (disabled automatically when piping or via --no-color)."""
    HEADER = "\033[1;36m"
    FILE = "\033[1;35m"
    DATE = "\033[0;33m"
    ADDR = "\033[1;32m"
    SUBJ = "\033[1;37m"
    ATTACH = "\033[0;36m"
    MATCH = "\033[1;31m"
    DIM = "\033[2m"
    RESET = "\033[0m"

    @classmethod
    def disable(cls) -> None:
        for attr in ("HEADER", "FILE", "DATE", "ADDR", "SUBJ", "ATTACH", "MATCH", "DIM", "RESET"):
            setattr(cls, attr, "")


def build_arg_parser() -> argparse.ArgumentParser:
    epilog_text = """
FILE NAMING & ARCHIVE FILTERS:
  MuttSearch automatically recognizes your monthly files:
    rebuts_<mes>_<any>   -> matched with --box in  (or --box rebuts)
    enviats_<mes>_<any>  -> matched with --box out (or --box enviats)
  Months accept either names (gen, feb, mar, abr, mai, jun, jul, ago, sep, oct, nov, des)
  or numbers (1..12). You can pass multiple months/years separated by commas.

MUTT 2.4.3 MANUAL EQUIVALENTS:
  -n / --name      <->  ~L EXPR   (From, To, Cc, Bcc)
  --from / --to    <->  ~f / ~C   (Originator / Recipients)
  -t / --topic     <->  ~s EXPR   (Subject header)
  -k / --keyword   <->  ~B EXPR   (Whole message, decoded like $thorough_search=yes)
  -b / --body      <->  ~b EXPR   (Message body only, decoded)
  -a / --attach    <->  ~X 1-     (Has attachment, or matches attachment filename)
  --mime           <->  ~M EXPR   (MIME Content-Type matching EXPR)
  --after/--before <->  ~d MIN-MAX (Date-sent range)
  -o / --open      <->  mutt -R -f <results_mbox> (Open matches in Mutt read-only)

EXAMPLES:
  1. Case-insensitive search for " Joan " in all 2026 received emails:
     MuttSearch -n "joan" --box in -y 2026

  2. Case-sensitive search (-c) for keyword "URGENT" in Nov & Oct 2026:
     MuttSearch -k "URGENT" -c -m oct,nov -y 2026

  3. Find emails about "pressupost" that contain ANY attachment:
     MuttSearch -t "pressupost" -a

  4. Find sent emails in 2025-2026 with a PDF attachment named "factura":
     MuttSearch --box out -y 2025,2026 -a "factura.*\\.pdf" -r

  5. Search across a specific root archive folder and open results directly in Mutt:
     MuttSearch -d ~/Mail -n "elkins" -k "muttrc" --open

  6. Print the equivalent native Mutt limit/search pattern:
     MuttSearch -n "anna" -t "reunió" -a --mutt-pattern
"""
    parser = argparse.ArgumentParser(
        prog="MuttSearch",
        description=(
            "MuttSearch: Search local Mutt mbox archives by correspondent name, "
            "topic/subject, body keywords, dates, and MIME attachments."
        ),
        epilog=epilog_text,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "files",
        nargs="*",
        help="Optional specific mbox file(s) or directories to search (default: --dir).",
    )
    parser.add_argument(
        "-V", "--version",
        action="version",
        version=f"%(prog)s {VERSION}",
    )

    # --- Archive & File Selection ---
    arch = parser.add_argument_group("Archive & File Selection")
    arch.add_argument(
        "-d", "--dir",
        default=".",
        metavar="PATH",
        help="Base mail directory to scan recursively (default: current directory).",
    )
    arch.add_argument(
        "--box",
        choices=["all", "in", "out", "rebuts", "enviats"],
        default="all",
        help="Filter by mailbox direction: 'in'/'rebuts', 'out'/'enviats', or 'all' (default).",
    )
    arch.add_argument(
        "-y", "--year",
        metavar="YYYY[,YYYY]",
        help="Filter mailbox filenames/paths by year(s), e.g. '2026' or '2025,2026'.",
    )
    arch.add_argument(
        "-m", "--month",
        metavar="MON[,MON]",
        help="Filter mailbox filenames by month(s), e.g. 'gen,feb,nov' or '1,2,11'.",
    )
    arch.add_argument(
        "--max-depth",
        type=int,
        default=3,
        metavar="N",
        help="Maximum directory recursion depth when scanning --dir (default: 3).",
    )

    # --- Search Criteria ---
    crit = parser.add_argument_group("Search Criteria (combined with logical AND; use --or for OR)")
    crit.add_argument(
        "-n", "--name",
        metavar="PATTERN",
        help="Search correspondent name or email in From, To, Cc, Bcc, Reply-To (~L).",
    )
    crit.add_argument(
        "--from",
        dest="from_addr",
        metavar="PATTERN",
        help="Search only in the From/Sender header (~f).",
    )
    crit.add_argument(
        "--to",
        dest="to_addr",
        metavar="PATTERN",
        help="Search only in recipient headers: To, Cc, Bcc (~C).",
    )
    crit.add_argument(
        "-t", "--topic",
        metavar="PATTERN",
        help="Search in the Subject header (~s).",
    )
    crit.add_argument(
        "-k", "--keyword",
        metavar="PATTERN",
        help="Search anywhere in headers, decoded message body, or attachment names (~B).",
    )
    crit.add_argument(
        "-b", "--body",
        metavar="PATTERN",
        help="Search strictly inside the decoded message body (~b).",
    )
    crit.add_argument(
        "-a", "--attachment",
        nargs="?",
        const="*",
        default=None,
        metavar="FILENAME_PAT",
        help=(
            "Require attachments (~X 1-). Used alone ('-a'), matches any email with "
            "an attachment. Given a value ('-a pdf'), matches attachment filenames."
        ),
    )
    crit.add_argument(
        "--mime",
        metavar="MIME_PAT",
        help="Match MIME Content-Type of attachments/parts, e.g. 'application/pdf' or 'image/' (~M).",
    )
    crit.add_argument(
        "--after",
        metavar="YYYY-MM-DD",
        help="Match messages sent on or after this date.",
    )
    crit.add_argument(
        "--before",
        metavar="YYYY-MM-DD",
        help="Match messages sent on or before this date.",
    )
    crit.add_argument(
        "--or",
        dest="logical_or",
        action="store_true",
        help="Combine text criteria (--name, --topic, --keyword, etc.) with OR instead of AND.",
    )

    # --- Matching Behavior ---
    mode = parser.add_argument_group("Case Sensitivity & Regex Behavior")
    case_grp = mode.add_mutually_exclusive_group()
    case_grp.add_argument(
        "-i", "--ignore-case",
        action="store_true",
        default=True,
        help="Case-insensitive search (default).",
    )
    case_grp.add_argument(
        "-c", "--case-sensitive",
        action="store_true",
        help="Enforce strict upper/lower case matching.",
    )
    case_grp.add_argument(
        "-S", "--smart-case",
        action="store_true",
        help="Mutt native behavior (Ch. 4.2): case-sensitive only if pattern has uppercase.",
    )
    mode.add_argument(
        "-r", "--regex",
        action="store_true",
        help="Treat patterns as regular expressions (~) instead of literal strings (=).",
    )

    # --- Output & Mutt Integration ---
    out = parser.add_argument_group("Output & Mutt Integration")
    out.add_argument(
        "-o", "--open",
        action="store_true",
        help="Open all matching messages directly inside Mutt (read-only temporary mbox).",
    )
    out.add_argument(
        "--export",
        metavar="MBOX_FILE",
        help="Save all matching messages to the specified mbox file.",
    )
    out.add_argument(
        "--snippet",
        action="store_true",
        help="Print a matching text snippet for body/keyword hits.",
    )
    out.add_argument(
        "--count",
        action="store_true",
        help="Only print match counts per file and total.",
    )
    out.add_argument(
        "--mutt-pattern",
        action="store_true",
        help="Print the equivalent native Mutt search/limit pattern (Ch. 4.3) and exit.",
    )
    out.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored terminal output.",
    )

    return parser


# ---------------------------------------------------------------------------
# Decoding & MIME Inspection Helpers
# ---------------------------------------------------------------------------

def decode_mime_header(raw_val: Optional[str]) -> str:
    """Decode RFC 2047 encoded email headers safely into a clean Unicode string."""
    if not raw_val:
        return ""
    parts: List[str] = []
    try:
        for chunk, enc in email.header.decode_header(raw_val):
            if isinstance(chunk, bytes):
                charset = enc or "utf-8"
                try:
                    parts.append(chunk.decode(charset, errors="replace"))
                except LookupError:
                    parts.append(chunk.decode("utf-8", errors="replace"))
            else:
                parts.append(str(chunk))
    except Exception:
        return str(raw_val)
    # Collapse folded header newlines/tabs (Mutt Ch. 3.12.1)
    return re.sub(r"[\r\n\t]+", " ", "".join(parts)).strip()


def strip_html_basic(html_text: str) -> str:
    """Lightweight fallback stripper if an email only contains text/html."""
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html_text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_body_and_attachments(msg: email.message.Message) -> Tuple[str, List[Tuple[str, str, int]]]:
    """
    Walk MIME tree once to extract:
      1. Decoded text body (equivalent to Mutt's $thorough_search=yes)
      2. List of attachments as (filename, content_type, approx_bytes)
         following Mutt Manual Ch. 5.6 disposition & MIME rules.
    """
    plain_parts: List[str] = []
    html_parts: List[str] = []
    attachments: List[Tuple[str, str, int]] = []

    for idx, part in enumerate(msg.walk()):
        if part.is_multipart():
            continue

        ctype = (part.get_content_type() or "application/octet-stream").lower()
        disp = (part.get_content_disposition() or "").lower()
        raw_fname = part.get_filename()
        fname = decode_mime_header(raw_fname) if raw_fname else ""

        payload = part.get_payload(decode=True)
        size = len(payload) if payload else 0

        # Determine if this MIME part counts as an attachment (Mutt Ch. 5.6)
        is_explicit_attach = disp == "attachment" or bool(fname)
        is_non_body_part = ctype not in ("text/plain", "text/html", "text/enriched")

        if (is_explicit_attach or is_non_body_part) and ctype not in IGNORED_ATTACHMENT_MIMES:
            # Avoid counting the root inline text body if a client gave no filename
            if not (idx <= 1 and disp == "inline" and not fname and ctype.startswith("text/")):
                attachments.append((fname or f"<unnamed:{ctype}>", ctype, size))

        # Extract searchable body text from text/* parts (unless strictly a binary file)
        if payload and ctype.startswith("text/") and disp != "attachment":
            charset = part.get_content_charset() or "utf-8"
            try:
                decoded = payload.decode(charset, errors="replace")
            except LookupError:
                decoded = payload.decode("utf-8", errors="replace")

            if ctype == "text/html":
                html_parts.append(decoded)
            else:
                plain_parts.append(decoded)

    body_text = "\n".join(plain_parts) if plain_parts else "\n".join(strip_html_basic(h) for h in html_parts)
    return body_text, attachments


def get_all_headers_text(msg: email.message.Message) -> str:
    """Return all decoded headers joined as searchable text."""
    lines = []
    for k, v in msg.items():
        lines.append(f"{k}: {decode_mime_header(str(v))}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Pattern Compilation & File Discovery
# ---------------------------------------------------------------------------

def compile_matcher(pattern_str: str, args: argparse.Namespace) -> Pattern[str]:
    """Compile literal or regex pattern with requested case sensitivity."""
    expr = pattern_str if args.regex else re.escape(pattern_str)

    if args.case_sensitive:
        flags = 0
    elif args.smart_case:
        # Mutt Manual Ch. 4.2: case-sensitive iff pattern contains >= 1 uppercase char
        flags = 0 if any(ch.isupper() for ch in pattern_str) else re.IGNORECASE
    else:
        flags = re.IGNORECASE

    try:
        return re.compile(expr, flags)
    except re.error as exc:
        sys.exit(f"Error: Invalid regular expression '{pattern_str}': {exc}")


def is_mbox_file(path: Path) -> bool:
    """Detect mbox or gzipped mbox files (Mutt Manual Ch. 4.9 & Ch. 6.12)."""
    if not path.is_file() or path.name.startswith("."):
        return False
    try:
        if path.suffix == ".gz":
            with gzip.open(path, "rb") as fh:
                head = fh.read(5)
        else:
            if path.stat().st_size == 0:
                return False
            with path.open("rb") as fh:
                head = fh.read(5)
        return head == b"From "
    except OSError:
        return False


def discover_mailboxes(args: argparse.Namespace) -> List[Path]:
    """Find and filter mbox files by --box, --year, and --month."""
    candidates: List[Path] = []

    if args.files:
        for item in args.files:
            p = Path(item).expanduser()
            if p.is_file():
                candidates.append(p)
            elif p.is_dir():
                candidates.extend(sorted(f for f in p.rglob("*") if is_mbox_file(f)))
            else:
                print(f"Warning: '{item}' not found, skipping.", file=sys.stderr)
    else:
        base = Path(args.dir).expanduser().resolve()
        if not base.exists():
            sys.exit(f"Error: Directory '{base}' does not exist.")
        if base.is_file():
            candidates.append(base)
        else:
            for root, dirs, files in os.walk(base):
                rel_depth = len(Path(root).relative_to(base).parts)
                if rel_depth >= args.max_depth:
                    dirs[:] = []
                # Skip hidden directories (.mutt, .git, header cache)
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for fname in sorted(files):
                    fpath = Path(root) / fname
                    if is_mbox_file(fpath):
                        candidates.append(fpath)

    # Apply --box, --year, and --month filename filters
    years = [y.strip() for y in args.year.split(",") if y.strip()] if args.year else []
    months: List[str] = []
    if args.month:
        for m in args.month.split(","):
            key = m.strip().lower()
            months.append(MONTH_ALIASES.get(key, key))

    filtered: List[Path] = []
    for fpath in candidates:
        name_low = fpath.name.lower()
        full_low = str(fpath).lower()

        if args.box in ("in", "rebuts") and not name_low.startswith("rebuts"):
            continue
        if args.box in ("out", "enviats") and not name_low.startswith("enviats"):
            continue
        if years and not any(y in full_low for y in years):
            continue
        if months and not any(re.search(rf"(^|_){re.escape(m)}(_|$|\.)", name_low) for m in months):
            continue

        filtered.append(fpath)

    return filtered


# ---------------------------------------------------------------------------
# Date Parsing & Native Mutt Pattern Builder
# ---------------------------------------------------------------------------

def parse_cli_date(date_str: str) -> datetime.date:
    """Parse YYYY-MM-DD or DD/MM/YYYY dates."""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y%m%d"):
        try:
            return datetime.datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    sys.exit(f"Error: Invalid date '{date_str}'. Use YYYY-MM-DD or DD/MM/YYYY.")


def parse_msg_date(msg: email.message.Message) -> Optional[datetime.datetime]:
    raw_date = msg.get("Date")
    if not raw_date:
        return None
    try:
        return email.utils.parsedate_to_datetime(raw_date)
    except Exception:
        return None


def build_native_mutt_pattern(args: argparse.Namespace) -> str:
    """Generate the equivalent Mutt 2.4.3 search/limit pattern (Ch. 4.3)."""
    op = "~" if args.regex else "="
    tokens: List[str] = []

    if args.name:
        tokens.append(f'{op}L "{args.name}"')
    if args.from_addr:
        tokens.append(f'{op}f "{args.from_addr}"')
    if args.to_addr:
        tokens.append(f'{op}C "{args.to_addr}"')
    if args.topic:
        tokens.append(f'{op}s "{args.topic}"')
    if args.keyword:
        tokens.append(f'{op}B "{args.keyword}"')
    if args.body:
        tokens.append(f'{op}b "{args.body}"')
    if args.attachment is not None:
        tokens.append("~X 1-")
    if args.mime:
        tokens.append(f'~M "{args.mime}"')
    if args.after or args.before:
        d_min = parse_cli_date(args.after).strftime("%d/%m/%Y") if args.after else ""
        d_max = parse_cli_date(args.before).strftime("%d/%m/%Y") if args.before else ""
        tokens.append(f"~d {d_min}-{d_max}")

    if not tokens:
        return "~A"
    joiner = " | " if args.logical_or else " "
    return joiner.join(tokens)


# ---------------------------------------------------------------------------
# Core Search Engine
# ---------------------------------------------------------------------------

def format_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes}B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f}K"
    return f"{num_bytes / (1024 * 1024):.1f}M"


def extract_snippet(text: str, matcher: Pattern[str], radius: int = 45) -> str:
    m = matcher.search(text)
    if not m:
        return ""
    start = max(0, m.start() - radius)
    end = min(len(text), m.end() + radius)
    raw = re.sub(r"\s+", " ", text[start:end]).strip()
    # Highlight match inside snippet
    return matcher.sub(lambda hit: f"{Colors.MATCH}{hit.group(0)}{Colors.RESET}", raw)


def iter_mbox_messages(fpath: Path) -> Iterable[Tuple[int, email.message.Message]]:
    """
    Iterate over an mbox (or .gz mbox) safely while preserving original
    atime/mtime so Mutt's new-mail detection (Ch. 4.13.1) is untouched.
    """
    orig_stat = fpath.stat()
    temp_uncompressed: Optional[Path] = None

    try:
        target_path = fpath
        if fpath.suffix == ".gz":
            fd, tmp_name = tempfile.mkstemp(prefix="muttsearch_gz_", suffix=".mbox")
            os.close(fd)
            temp_uncompressed = Path(tmp_name)
            with gzip.open(fpath, "rb") as src, temp_uncompressed.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            target_path = temp_uncompressed

        mbox_obj = mailbox.mbox(str(target_path), create=False)
        try:
            for idx, msg in enumerate(mbox_obj, start=1):
                yield idx, msg
        finally:
            mbox_obj.close()
    finally:
        if temp_uncompressed and temp_uncompressed.exists():
            temp_uncompressed.unlink()
        try:
            os.utime(fpath, ns=(orig_stat.st_atime_ns, orig_stat.st_mtime_ns))
        except OSError:
            pass


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.no_color or not sys.stdout.isatty():
        Colors.disable()

    if args.mutt_pattern:
        print(build_native_mutt_pattern(args))
        return

    has_any_filter = any([
        args.name, args.from_addr, args.to_addr, args.topic,
        args.keyword, args.body, args.attachment is not None,
        args.mime, args.after, args.before,
    ])
    if not has_any_filter:
        parser.error(
            "Please provide at least one search criterion "
            "(e.g., -n NAME, -t TOPIC, -k KEYWORD, -a, --mime, --after). "
            "Use -h or --help for examples."
        )

    # Pre-compile patterns
    pat_name = compile_matcher(args.name, args) if args.name else None
    pat_from = compile_matcher(args.from_addr, args) if args.from_addr else None
    pat_to = compile_matcher(args.to_addr, args) if args.to_addr else None
    pat_topic = compile_matcher(args.topic, args) if args.topic else None
    pat_kw = compile_matcher(args.keyword, args) if args.keyword else None
    pat_body = compile_matcher(args.body, args) if args.body else None
    pat_att = (
        compile_matcher(args.attachment, args)
        if (args.attachment and args.attachment != "*")
        else None
    )
    pat_mime = compile_matcher(args.mime, args) if args.mime else None
    date_after = parse_cli_date(args.after) if args.after else None
    date_before = parse_cli_date(args.before) if args.before else None

    files = discover_mailboxes(args)
    if not files:
        sys.exit("No matching mbox files found for the given archive filters.")

    # Prepare export / Mutt temporary mbox if needed
    out_mbox_path: Optional[Path] = None
    cleanup_temp = False
    if args.export:
        out_mbox_path = Path(args.export).expanduser()
    elif args.open:
        fd, tmp_path = tempfile.mkstemp(prefix="MuttSearch_", suffix=".mbox")
        os.close(fd)
        out_mbox_path = Path(tmp_path)
        cleanup_temp = True

    out_mbox = mailbox.mbox(str(out_mbox_path), create=True) if out_mbox_path else None

    total_matches = 0
    total_scanned = 0
    need_mime_walk = bool(pat_kw or pat_body or args.attachment is not None or pat_mime or args.snippet or not args.count)

    try:
        for fpath in files:
            file_matches = 0
            for msg_idx, msg in iter_mbox_messages(fpath):
                total_scanned += 1

                from_hdr = decode_mime_header(msg.get("From", ""))
                sender_hdr = decode_mime_header(msg.get("Sender", ""))
                to_hdr = decode_mime_header(msg.get("To", ""))
                cc_hdr = decode_mime_header(msg.get("Cc", ""))
                bcc_hdr = decode_mime_header(msg.get("Bcc", ""))
                reply_hdr = decode_mime_header(msg.get("Reply-To", ""))
                subj_hdr = decode_mime_header(msg.get("Subject", ""))

                correspondents = " ".join(filter(None, [from_hdr, sender_hdr, to_hdr, cc_hdr, bcc_hdr, reply_hdr]))
                recipients = " ".join(filter(None, [to_hdr, cc_hdr, bcc_hdr]))

                # Date checks (always strict bounds)
                msg_dt = parse_msg_date(msg)
                if date_after or date_before:
                    if not msg_dt:
                        continue
                    msg_d = msg_dt.date()
                    if date_after and msg_d < date_after:
                        continue
                    if date_before and msg_d > date_before:
                        continue

                body_text = ""
                attachments: List[Tuple[str, str, int]] = []
                parsed_mime = False

                def ensure_mime() -> None:
                    nonlocal body_text, attachments, parsed_mime
                    if not parsed_mime:
                        body_text, attachments = extract_body_and_attachments(msg)
                        parsed_mime = True

                checks: List[bool] = []

                if pat_name:
                    checks.append(bool(pat_name.search(correspondents)))
                if pat_from:
                    checks.append(bool(pat_from.search(f"{from_hdr} {sender_hdr}")))
                if pat_to:
                    checks.append(bool(pat_to.search(recipients)))
                if pat_topic:
                    checks.append(bool(pat_topic.search(subj_hdr)))
                if pat_body:
                    ensure_mime()
                    checks.append(bool(pat_body.search(body_text)))
                if pat_kw:
                    ensure_mime()
                    att_names = " ".join(a[0] for a in attachments)
                    full_haystack = f"{get_all_headers_text(msg)}\n{att_names}\n{body_text}"
                    checks.append(bool(pat_kw.search(full_haystack)))
                if args.attachment is not None:
                    ensure_mime()
                    if pat_att is None:
                        checks.append(len(attachments) > 0)
                    else:
                        checks.append(any(pat_att.search(a[0]) for a in attachments))
                if pat_mime:
                    ensure_mime()
                    part_mimes = [p.get_content_type() or "" for p in msg.walk()]
                    checks.append(any(pat_mime.search(m) for m in part_mimes))

                matched = any(checks) if (checks and args.logical_or) else all(checks)
                if not matched:
                    continue

                file_matches += 1
                total_matches += 1

                if out_mbox is not None:
                    out_mbox.add(msg)

                if not args.count:
                    if need_mime_walk:
                        ensure_mime()
                    dt_str = msg_dt.strftime("%Y-%m-%d %H:%M") if msg_dt else decode_mime_header(msg.get("Date", "Unknown Date"))[:16]
                    subj_disp = subj_hdr or "(no subject)"
                    if pat_topic:
                        subj_disp = pat_topic.sub(lambda h: f"{Colors.MATCH}{h.group(0)}{Colors.RESET}{Colors.SUBJ}", subj_disp)

                    print(
                        f"{Colors.FILE}[{fpath.name} #{msg_idx}]{Colors.RESET} "
                        f"{Colors.DATE}{dt_str}{Colors.RESET} | "
                        f"{Colors.SUBJ}{subj_disp}{Colors.RESET}"
                    )
                    print(f"  {Colors.DIM}From:{Colors.RESET} {Colors.ADDR}{from_hdr or '-'}{Colors.RESET}")
                    if to_hdr or cc_hdr:
                        rcpt_line = to_hdr + (f" (Cc: {cc_hdr})" if cc_hdr else "")
                        print(f"  {Colors.DIM}To:  {Colors.RESET} {rcpt_line}")
                    if attachments:
                        att_summary = ", ".join(f"{name} [{ctype}, {format_size(sz)}]" for name, ctype, sz in attachments)
                        print(f"  {Colors.ATTACH}Atts ({len(attachments)}): {att_summary}{Colors.RESET}")
                    if args.snippet and (pat_kw or pat_body):
                        snip_pat = pat_kw or pat_body
                        snip = extract_snippet(body_text, snip_pat)  # type: ignore[arg-type]
                        if snip:
                            print(f"  {Colors.DIM}Text:{Colors.RESET} ...{snip}...")
                    print()

            if args.count and file_matches > 0:
                print(f"{Colors.FILE}{fpath}{Colors.RESET}: {file_matches} match(es)")

        if out_mbox is not None:
            out_mbox.flush()
            out_mbox.close()

        print(
            f"{Colors.HEADER}Matched {total_matches} message(s){Colors.RESET} "
            f"across {len(files)} mailbox file(s) ({total_scanned} messages scanned)."
        )

        if args.export and total_matches > 0:
            print(f"Saved results to: {out_mbox_path}  (open with: mutt -R -f '{out_mbox_path}')")

        if args.open:
            if total_matches == 0:
                print("No messages to open in Mutt.")
            else:
                # Invoke Mutt in read-only mode (-R) on the temporary mbox (Ch. 9.1, Table 9.1)
                subprocess.run(["mutt", "-R", "-f", str(out_mbox_path)], check=False)

    finally:
        if cleanup_temp and out_mbox_path and out_mbox_path.exists():
            out_mbox_path.unlink()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nSearch aborted.")
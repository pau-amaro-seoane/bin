#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2026 Pau Amaro Seoane
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

r"""
MergeBibTex.py: Standard BibTeX Merger, Deduplicator, and Crossref Linker.

===============================================================================
1. PURPOSE & MOTIVATION
===============================================================================
In large, multi-author astrophysics LaTeX projects, different collaborators 
often add the exact same publication to `.bib` files under different citation 
keys:
  - NASA ADS Bibcodes:   @ARTICLE{2019MNRAS.482.2913B, ...}
  - Author-Year format:  @ARTICLE{BellovaryEtAl2019, ...}
  - Arbitrary strings:   @ARTICLE{amazingpaperxxxxx, ...}

While co-authors are actively editing the `.tex` manuscript, rewriting their 
`.tex` files to enforce a single citation key causes version-control conflicts. 
Instead, we need a unified `.bib` file where:
  1. Redundant full copies of the same paper are merged into a single master 
     entry renamed according to a strict standard:
       * 1 Author:   Surname1Year          (e.g., AmaroSeoane2026)
       * 2 Authors:  Surname1Surname2Year  (e.g., SmithKlein2023)
       * >2 Authors: Surname1EtAlYear      (e.g., BellovaryEtAl2019)
  2. All alternative citation keys (`2019MNRAS.482.2913B`, `amazingpaperxxxxx`) 
     are kept in the `.bib` file as lightweight `crossref = {...}` entries 
     linked to the master entry, placed immediately adjacent to it.
  3. Only when explicitly requested via `--merge-latex` (`-mtex`) are the `.tex` 
     files rewritten to replace all variant keys with the master key.

===============================================================================
2. HOW STANDARD BIBTEX HANDLES `crossref = {...}`
===============================================================================
Standard `bibtex` (used by MNRAS, A&A, ApJ/AAS, PRD/APS, and `natbib`) resolves 
cross-references in a single top-to-bottom pass over the `.bib` file. This 
imposes two strict technical requirements that this script automatically obeys:

  A. Ordering Constraint (Child BEFORE Parent):
     In standard `bibtex`, an entry containing `crossref = {TargetKey}` MUST 
     appear *before* `@ARTICLE{TargetKey, ...}` in the `.bib` file. If the 
     parent entry appears first and a `.tex` file only cites the alias 
     `\cite{amazingpaperxxxxx}`, `bibtex` fails with:
       "A bad cross reference---entry 'amazingpaperxxxxx' refers to entry 
        'BellovaryEtAl2019', which doesn't exist"
     Therefore, for every paper that has multiple keys, this script outputs 
     the contiguous block with the `crossref` aliases immediately preceding 
     the canonical master entry:

       @ARTICLE{2019MNRAS.482.2913B,
         crossref = {BellovaryEtAl2019}
       }

       @ARTICLE{amazingpaperxxxxx,
         crossref = {BellovaryEtAl2019}
       }

       @ARTICLE{BellovaryEtAl2019,
         author = {{Bellovary}, Jillian M. and ...},
         title  = "{Multimessenger signatures of massive black holes...}",
         ...
       }

  B. Pure Inheritance (No Extraneous Fields in Alias Stubs):
     When `bibtex` processes `@ARTICLE{amazingpaperxxxxx, crossref = {BellovaryEtAl2019}}`,
     it copies every missing bibliographic field (`author`, `title`, `journal`, 
     `year`, `volume`, `pages`, `doi`, etc.) from `BellovaryEtAl2019` into 
     `amazingpaperxxxxx`. We intentionally omit `note = {...}` inside the alias 
     stub so that no unwanted text is printed in the compiled PDF reference list.

  C. Note on `bibtex -min-crossrefs`:
     If Co-Author A writes `\cite{BellovaryEtAl2019}` in Section 1 and Co-Author B 
     writes `\cite{amazingpaperxxxxx}` in Section 2, standard `bibtex` sees two 
     distinct cited keys (`BellovaryEtAl2019` and `amazingpaperxxxxx`) and will 
     keep both active so neither co-author gets a `[?]` citation error. When 
     preparing the final camera-ready submission, running this script with 
     `--merge-latex` (`-mtex`) unifies all `\cite{...}` calls in the `.tex` 
     files to `\cite{BellovaryEtAl2019}` and optionally strips the alias stubs.

===============================================================================
3. DUPLICATE DETECTION ALGORITHM
===============================================================================
Entries are matched across `.bib` files by normalizing and comparing three 
intrinsic bibliographic fingerprints:
  1. `doi`    : Lowercased, stripped of braces, quotes, and `https://doi.org/`.
  2. `adsurl` : Extracted 19-character ADS bibcode (e.g., `2019mnras.482.2913b`)
                regardless of whether the URL uses `http://adsabs.harvard.edu` 
                or `https://ui.adsabs.harvard.edu`.
  3. `title`  : Lowercased, stripped of LaTeX macros (`\ensuremath`, `\star`), 
                braces, punctuation, and extra whitespace.

A Disjoint-Set (Union-Find) graph clusters all entries that share ANY of these 
three identifiers (or an identical citation key). Within each cluster, the most 
complete record (preferring published journal articles with a `doi`, `volume`, 
and `pages` over older arXiv preprints) is selected as the master entry.
"""

import argparse
import os
import re
import shutil
import sys
import unicodedata
from typing import Dict, List, Optional, Set


# ==============================================================
# REGULAR EXPRESSIONS & CONSTANTS and milky derivatives... 
# =============================================================

# Matches the opening header of a BibTeX entry, e.g.: @ARTICLE{2019MNRAS.482.2913B,
# Group 1: Entry type (e.g. 'ARTICLE')
# Group 2: Citation key (e.g. '2019MNRAS.482.2913B')
BIB_ENTRY_START_RE = re.compile(
    r'@([a-zA-Z]+)\s*\{\s*([^,\s]+)\s*,',
    re.MULTILINE
)

# Non-bibliographic BibTeX directives that should be skipped during entry parsing
IGNORED_META_TYPES = {'comment', 'preamble', 'string'}

# Matches standard LaTeX and natbib citation commands in .tex files:
# \cite, \citet, \citep, \citealt, \citealp, \citeauthor, \citeyear, \citeyearpar,
# including starred variants (\citet*) and optional bracketed arguments (\citep[e.g.][p.~4]{...}).
LATEX_CITE_RE = re.compile(
    r'(\\[a-zA-Z]*cite[a-zA-Z]*\*?(?:\s*\[[^\]]*\])*)\s*\{([^}]+)\}'
)


# ====================================
# CORE DATA STRUCTURES
# ===================================

class BibEntry:
    r"""
    Container representing a single parsed BibTeX entry and its normalized 
    lookup fingerprints (`norm_doi`, `norm_adsurl`, `norm_title`).
    """
    def __init__(
        self,
        entry_type: str,
        key: str,
        raw_text: str,
        fields: Dict[str, str],
        source_file: str
    ) -> None:
        self.entry_type: str = entry_type.lower()
        self.original_type_str: str = entry_type
        self.key: str = key
        self.raw_text: str = raw_text
        self.fields: Dict[str, str] = fields
        self.source_file: str = source_file

        # Extract normalized identifiers for duplicate matching
        self.norm_doi: Optional[str] = normalize_doi(fields.get('doi', ''))
        self.norm_adsurl: Optional[str] = normalize_adsurl(fields.get('adsurl', ''))
        self.norm_title: Optional[str] = normalize_title(fields.get('title', ''))

        # Check if this entry is already a crossref stub from a previous run
        self.is_crossref_stub: bool = (
            'crossref' in self.fields
            and 'title' not in self.fields
            and 'author' not in self.fields
        )

    def completeness_score(self) -> int:
        r"""
        Calculates a quality score used to select the richest master record 
        when multiple BibTeX entries represent the same paper. Published 
        journal entries (having a `doi`, `volume`, and `pages`) outscore 
        incomplete entries or raw arXiv e-prints.
        """
        if self.is_crossref_stub:
            return -100
        score = len(self.fields)
        if self.norm_doi:
            score += 25
        if 'volume' in self.fields:
            score += 15
        if 'pages' in self.fields:
            score += 15
        if 'journal' in self.fields and 'arxiv' not in self.fields['journal'].lower():
            score += 20
        if self.norm_adsurl:
            score += 5
        return score


class UnionFind:
    r"""
    Disjoint-Set data structure used to group BibTeX entries into connected 
    components (clusters) whenever they share a DOI, an ADS URL, a Title, 
    a crossref target, or an identical citation key.
    """
    def __init__(self, size: int) -> None:
        self.parent: List[int] = list(range(size))

    def find(self, idx: int) -> int:
        r"""Finds the cluster root index for element `idx` with path compression."""
        if self.parent[idx] != idx:
            self.parent[idx] = self.find(self.parent[idx])
        return self.parent[idx]

    def union(self, idx_a: int, idx_b: int) -> None:
        r"""Merges the clusters containing `idx_a` and `idx_b`."""
        root_a = self.find(idx_a)
        root_b = self.find(idx_b)
        if root_a != root_b:
            # Attach the later index to the earlier index to preserve file order
            if root_a < root_b:
                self.parent[root_b] = root_a
            else:
                self.parent[root_a] = root_b


# ====================================================
# FINGERPRINT NORMALIZATION FUNCTIONS (NOT ORANGES)
# ==================================================

def strip_outer_delimiters(value: str) -> str:
    r"""
    Recursively strips outer whitespace, double quotes `"..."`, and curly 
    braces `{...}` from a raw BibTeX field string.
    """
    val = value.strip()
    while len(val) >= 2:
        if (val.startswith('{') and val.endswith('}')) or (
            val.startswith('"') and val.endswith('"')
        ):
            val = val[1:-1].strip()
        else:
            break
    return val


def normalize_doi(raw_doi: str) -> Optional[str]:
    r"""
    Normalizes a `doi` field so that formatting variations match identically:
      - `doi = {10.3847/1538-4357/aca283}`
      - `doi = "https://doi.org/10.3847/1538-4357/ACA283"`
    Both normalize to: `'10.3847/1538-4357/aca283'`.
    """
    if not raw_doi:
        return None
    cleaned = strip_outer_delimiters(raw_doi).lower()
    cleaned = re.sub(r'^https?://(dx\.)?doi\.org/', '', cleaned)
    cleaned = cleaned.strip()
    return cleaned if cleaned else None


def normalize_adsurl(raw_url: str) -> Optional[str]:
    r"""
    Normalises an `adsurl` field by extracting the ADS bibcode suffix after 
    `/abs/`, unescaping LaTeX symbols (`\&` -> `&`), and lowercasing:
      - `adsurl = {https://ui.adsabs.harvard.edu/abs/2023ApJ...942....9H}`
      - `adsurl = {http://adsabs.harvard.edu/abs/2023ApJ...942....9H}`
    Both normalize to: `'2023apj...942....9h'`.
    """
    if not raw_url:
        return None
    cleaned = strip_outer_delimiters(raw_url)
    cleaned = cleaned.replace(r'\&', '&').replace(r'\%', '%')
    match = re.search(r'/abs/([^\s/}]+)', cleaned)
    if match:
        return match.group(1).lower()
    return cleaned.lower() if cleaned else None


def normalize_title(raw_title: str) -> Optional[str]:
    r"""
    Normalizes a `title` field so minor LaTeX formatting or brace differences 
    do not prevent matching:
      - `title = "{Multimessenger signatures of massive black holes in dwarf galaxies}"`
      - `title = {{Multimessenger} Signatures of Massive Black Holes in Dwarf Galaxies}`
    Both normalize to:
      `'multimessenger signatures of massive black holes in dwarf galaxies'`.
    """
    if not raw_title:
        return None
    text = strip_outer_delimiters(raw_title)
    # Remove purely decorative LaTeX wrapper macros while keeping their inner text
    text = re.sub(r'\\(textbf|textit|emph|textrm|textsc|ensuremath)\b', ' ', text)
    # Convert remaining LaTeX command names (e.g. \alpha, \star) to plain letters
    text = re.sub(r'\\([a-zA-Z]+)', r'\1', text)
    # Replace all punctuation, braces, math shifts, and hyphens with spaces
    text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip().lower()
    # Ignore very short generic titles (e.g. "Erratum", "Introduction")
    if len(text) < 12:
        return None
    return text


# ===================================
# BALANCED-BRACE BIBTEX PARSER
# ================================

def extract_fields_from_body(body: str) -> Dict[str, str]:
    r"""
    Parses the key-value interior of a BibTeX entry (`field = {value}, ...`) 
    using a character-level state machine that tracks nested `{...}` and `"..."`.
    """
    fields: Dict[str, str] = {}
    i = 0
    n = len(body)

    while i < n:
        # Advance past whitespace and commas between fields
        while i < n and body[i] in ' \t\r\n,':
            i += 1
        if i >= n:
            break

        # Read field name (left of '=')
        name_start = i
        while i < n and body[i] not in '= \t\r\n':
            i += 1
        field_name = body[name_start:i].strip().lower()

        # Advance to '='
        while i < n and body[i] in ' \t\r\n':
            i += 1
        if i >= n or body[i] != '=':
            while i < n and body[i] != '\n':
                i += 1
            continue
        i += 1  # Skip '='

        # Skip whitespace after '='
        while i < n and body[i] in ' \t\r\n':
            i += 1
        if i >= n:
            break

        # Parse field value according to delimiter type
        val_start = i
        if body[i] == '{':
            depth = 0
            while i < n:
                if body[i] == '{':
                    depth += 1
                elif body[i] == '}':
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
                i += 1
        elif body[i] == '"':
            i += 1
            while i < n:
                if body[i] == '"' and body[i - 1] != '\\':
                    i += 1
                    break
                i += 1
        else:
            # Bare token (e.g., year = 2019, month = jan)
            while i < n and body[i] not in ',\r\n}':
                i += 1

        field_val = body[val_start:i].strip()
        if field_name:
            fields[field_name] = field_val

    return fields


def parse_bib_file(filepath: str) -> List[BibEntry]:
    r"""
    Reads a `.bib` file and extracts all syntactically complete BibTeX entries 
    by counting curly braces from `@TYPE{key,` down to the matching `}`. 
    Orphaned comments outside entries are automatically ignored.
    """
    if not os.path.isfile(filepath):
        sys.stderr.write(f"[WARNING] Input BibTeX file not found: '{filepath}'. Skipping.\n")
        return []

    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except OSError as err:
        sys.stderr.write(f"[ERROR] Could not read '{filepath}': {err}\n")
        return []

    entries: List[BibEntry] = []

    for match in BIB_ENTRY_START_RE.finditer(content):
        entry_type = match.group(1)
        citation_key = match.group(2).strip()

        if entry_type.lower() in IGNORED_META_TYPES:
            continue

        start_idx = match.start()
        body_start_idx = match.end()

        open_brace_idx = content.find('{', start_idx)
        if open_brace_idx == -1:
            continue

        # Walk forward counting '{' and '}' until depth returns to 0
        depth = 0
        end_idx = -1
        for idx in range(open_brace_idx, len(content)):
            char = content[idx]
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    end_idx = idx + 1
                    break

        if end_idx == -1:
            sys.stderr.write(
                f"[WARNING] Unbalanced braces in entry '{citation_key}' "
                f"(file: {filepath}). Skipping.\n"
            )
            continue

        raw_entry = content[start_idx:end_idx].strip()
        body_text = content[body_start_idx : end_idx - 1]
        fields = extract_fields_from_body(body_text)

        entries.append(
            BibEntry(
                entry_type=entry_type,
                key=citation_key,
                raw_text=raw_entry,
                fields=fields,
                source_file=filepath
            )
        )

    return entries


# =============================================================================
# CANONICAL KEY GENERATOR (Surname1Year / Surname1Surname2Year / Surname1EtAlYear)
# ===============================================================================

def clean_latex_surname(raw_surname: str) -> str:
    r"""
    Transforms a raw BibTeX surname (which may contain braces, hyphens, or 
    LaTeX diacritics like `V{\'a}zquez-Aceves` or `Baub{\"o}ck`) into a clean 
    ASCII PascalCase identifier (`VazquezAceves`, `Baubock`).
    """
    s = raw_surname.strip()
    # Strip standard LaTeX accent macros (\'a, \"o, \~n, \^e, \v{s}, \c{c}, etc.)
    s = re.sub(r'\\[\'"^`~=.uvHcdb](\{[a-zA-Z]\}|[a-zA-Z])', r'\1', s)
    s = re.sub(r'\\[a-zA-Z]+\b', '', s)
    # Convert any Unicode accented characters to their base ASCII equivalents
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
    # Split on non-alphanumeric characters and PascalCase each segment
    parts = re.split(r'[^a-zA-Z0-9]+', s)
    cleaned = ''.join(p[0].upper() + p[1:] for p in parts if p)
    return cleaned if cleaned else "Anon"


def extract_author_surnames(author_field: str) -> List[str]:
    r"""
    Parses a BibTeX `author` string and returns a list of clean ASCII surnames.
    Splits authors by ` and ` at brace depth 0 and handles both `"Last, First"` 
    and `"First Middle Last"` formats, as well as institutional collaborations.
    """
    raw = strip_outer_delimiters(author_field)
    if not raw:
        return ["Unknown"]

    raw = re.sub(r'\s+', ' ', raw)

    # Split by ' and ' at brace depth 0
    authors: List[str] = []
    depth = 0
    current: List[str] = []
    i = 0
    n = len(raw)

    while i < n:
        if raw[i] == '{':
            depth += 1
            current.append(raw[i])
            i += 1
        elif raw[i] == '}':
            depth = max(0, depth - 1)
            current.append(raw[i])
            i += 1
        elif depth == 0 and raw[i : i + 5].lower() == ' and ':
            authors.append(''.join(current).strip())
            current = []
            i += 5
        else:
            current.append(raw[i])
            i += 1

    if current:
        authors.append(''.join(current).strip())

    surnames: List[str] = []
    for auth in authors:
        if not auth:
            continue
        if auth.lower() == 'others':
            surnames.append('others')
            continue

        # Locate the first comma at brace depth 0 ("Surname, Given" format)
        comma_idx = -1
        d = 0
        for idx, ch in enumerate(auth):
            if ch == '{':
                d += 1
            elif ch == '}':
                d = max(0, d - 1)
            elif ch == ',' and d == 0:
                comma_idx = idx
                break

        if comma_idx != -1:
            surname_part = auth[:comma_idx].strip()
        else:
            # "Given Middle Surname" format
            tokens = auth.split()
            surname_part = tokens[-1] if tokens else auth

        surnames.append(clean_latex_surname(surname_part))

    return surnames if surnames else ["Unknown"]


def generate_canonical_key(entry: BibEntry, reserved_keys: Set[str]) -> str:
    r"""
    Synthesizes the canonical citation key for `entry` based on author count:
      - 1 author  : Surname1Year          (e.g. AmaroSeoane2026)
      - 2 authors : Surname1Surname2Year  (e.g. SmithKlein2023)
      - >2 authors: Surname1EtAlYear      (e.g. BellovaryEtAl2019)

    If the resulting key is already in `reserved_keys` (i.e. belonging to a 
    different paper by the same author(s) in the same year), appends a letter 
    suffix (`a`, `b`, `c`, ...).
    """
    surnames = extract_author_surnames(entry.fields.get('author', ''))

    raw_year = strip_outer_delimiters(entry.fields.get('year', ''))
    year_match = re.search(r'\b(18|19|20)\d{2}\b', raw_year)
    year_str = year_match.group(0) if year_match else "XXXX"

    if len(surnames) == 1:
        base_key = f"{surnames[0]}{year_str}"
    elif len(surnames) == 2 and surnames[1] != 'others':
        base_key = f"{surnames[0]}{surnames[1]}{year_str}"
    else:
        base_key = f"{surnames[0]}EtAl{year_str}"

    candidate = base_key
    suffix_idx = 0
    while candidate in reserved_keys:
        suffix = chr(ord('a') + suffix_idx)
        candidate = f"{base_key}{suffix}"
        suffix_idx += 1

    reserved_keys.add(candidate)
    return candidate


# =======================================================
# BIBTEX BLOCK FORMATTING & OPTIONAL LATEX REWRITING
# ======================================================

def format_cluster_for_bibtex(
    master_entry: BibEntry,
    canonical_key: str,
    alias_keys: List[str],
    emit_crossrefs: bool = True
) -> str:
    r"""
    Formats a deduplicated publication cluster for standard BibTeX.

    CRITICAL BIBTEX ORDERING NOTE:
    In standard `bibtex`, any entry that uses `crossref = {ParentKey}` MUST 
    appear *above* `ParentKey` in the `.bib` file. Otherwise, if a `.tex` 
    manuscript cites only the alias key, `bibtex` will fail with:
      "A bad cross reference---entry 'alias' refers to entry 'ParentKey', 
       which doesn't exist"
    Therefore, all `@TYPE{alias, crossref = {canonical_key}}` entries are 
    placed immediately ABOVE the master `@TYPE{canonical_key, ...}` entry, 
    forming a clean, self-contained block.
    """
    # Rewrite the opening key of the master entry to `canonical_key`
    master_block = BIB_ENTRY_START_RE.sub(
        f"@{master_entry.original_type_str}{{{canonical_key},",
        master_entry.raw_text,
        count=1
    )

    if not alias_keys or not emit_crossrefs:
        return master_block

    blocks: List[str] = []
    for alias in alias_keys:
        # Keep the crossref entry completely pure (no extra 'note' field) so 
        # BibTeX inherits all fields from `canonical_key` without printing 
        # extraneous notes in the bibliography.
        stub = (
            f"@{master_entry.original_type_str}{{{alias},\n"
            f"       crossref = {{{canonical_key}}}\n"
            f"}}"
        )
        blocks.append(stub)

    blocks.append(master_block)
    return "\n\n".join(blocks)


def replace_keys_in_latex_files(
    tex_files: List[str],
    alias_map: Dict[str, str],
    create_backup: bool = True,
    verbose: bool = False
) -> None:
    r"""
    Only executed when `--merge-latex` / `-mtex` is explicitly passed.
    Scans the provided `.tex` files and replaces all aliased citation keys 
    inside `\cite{...}` commands with their canonical key.
    """
    if not alias_map:
        if verbose:
            print("\nNo alias mappings needed replacement in LaTeX files.")
        return

    print("\n=== Updating LaTeX Files (--merge-latex / -mtex) ===")
    for tex_path in tex_files:
        if not os.path.isfile(tex_path):
            sys.stderr.write(f"[WARNING] LaTeX file not found: '{tex_path}'. Skipping.\n")
            continue

        try:
            with open(tex_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        except OSError as err:
            sys.stderr.write(f"[ERROR] Failed to read '{tex_path}': {err}\n")
            continue

        replacements_count = 0

        def rewrite_cite(match: re.Match) -> str:
            nonlocal replacements_count
            cmd_prefix = match.group(1)
            raw_keys = match.group(2)
            key_list = [k.strip() for k in raw_keys.split(',')]

            new_key_list: List[str] = []
            for k in key_list:
                mapped_k = alias_map.get(k, k)
                if mapped_k != k:
                    replacements_count += 1
                    if verbose:
                        print(f"  [{tex_path}] \\cite: '{k}' -> '{mapped_k}'")
                # Prevent duplicate keys inside the same \cite{a, b} call
                if mapped_k not in new_key_list:
                    new_key_list.append(mapped_k)

            return f"{cmd_prefix}{{{', '.join(new_key_list)}}}"

        updated_content = LATEX_CITE_RE.sub(rewrite_cite, content)

        if replacements_count > 0:
            if create_backup:
                backup_path = f"{tex_path}.bak"
                shutil.copy2(tex_path, backup_path)
            with open(tex_path, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            print(
                f"  -> Replaced {replacements_count:3d} citation instance(s) in '{tex_path}'"
                + (f" (backup saved to '{tex_path}.bak')" if create_backup else "")
            )
        else:
            print(f"  -> No aliased keys found in '{tex_path}' (file untouched).")


# ===============================
# MAIN DEDUPLICATION PIPELINE
# ==============================

def process_bib_files(
    input_files: List[str],
    output_file: str,
    rename_all: bool = False,
    merge_latex_files: Optional[List[str]] = None,
    drop_crossrefs_on_merge: bool = False,
    no_backup: bool = False,
    dry_run: bool = False,
    verbose: bool = False
) -> None:
    r"""
    Main orchestration function:
      1. Parses all input `.bib` files.
      2. Clusters duplicate entries via Union-Find on `doi`, `adsurl`, `title`, 
         existing `crossref`, and identical keys.
      3. Renames multi-key clusters to `Surname1EtAlYear` / `Surname1Surname2Year`.
      4. Emits standard BibTeX `crossref = {...}` blocks so all keys continue 
         working without modifying `.tex` files (unless `-mtex` is passed).
    """
    # -------------------------------------------------------------------------
    # Step 1: Parse all input .bib files
    # -------------------------------------------------------------------------
    all_entries: List[BibEntry] = []
    for path in input_files:
        parsed = parse_bib_file(path)
        if verbose:
            print(f"Loaded {len(parsed):4d} entries from '{path}'")
        all_entries.extend(parsed)

    total_entries = len(all_entries)
    if total_entries == 0:
        print("No valid BibTeX entries found in input files. Exiting.")
        return

    # -------------------------------------------------------------------------
    # Step 2: Build connected components of duplicate papers via Union-Find
    # -------------------------------------------------------------------------
    uf = UnionFind(total_entries)

    doi_map: Dict[str, int] = {}
    adsurl_map: Dict[str, int] = {}
    title_map: Dict[str, int] = {}
    key_map: Dict[str, int] = {}

    for idx, entry in enumerate(all_entries):
        # 1. Link by normalized DOI
        if entry.norm_doi:
            if entry.norm_doi in doi_map:
                uf.union(idx, doi_map[entry.norm_doi])
            else:
                doi_map[entry.norm_doi] = idx

        # 2. Link by normalized ADS URL / Bibcode
        if entry.norm_adsurl:
            if entry.norm_adsurl in adsurl_map:
                uf.union(idx, adsurl_map[entry.norm_adsurl])
            else:
                adsurl_map[entry.norm_adsurl] = idx

        # 3. Link by normalized Title
        if entry.norm_title:
            if entry.norm_title in title_map:
                uf.union(idx, title_map[entry.norm_title])
            else:
                title_map[entry.norm_title] = idx

        # 4. Link by identical citation key (unless titles explicitly conflict)
        if entry.key in key_map:
            prev_idx = key_map[entry.key]
            prev_entry = all_entries[prev_idx]
            if (
                not entry.norm_title
                or not prev_entry.norm_title
                or entry.norm_title == prev_entry.norm_title
            ):
                uf.union(idx, prev_idx)
        else:
            key_map[entry.key] = idx

    # Also link any pre-existing crossref stubs to their target key
    for idx, entry in enumerate(all_entries):
        if entry.is_crossref_stub:
            target_key = strip_outer_delimiters(entry.fields.get('crossref', ''))
            if target_key in key_map:
                uf.union(idx, key_map[target_key])

    # Group entries by cluster root index
    clusters: Dict[int, List[BibEntry]] = {}
    for idx, entry in enumerate(all_entries):
        root = uf.find(idx)
        clusters.setdefault(root, []).append(entry)

    # -------------------------------------------------------------------------
    # Step 3: Select master entry, generate canonical key, and build crossrefs
    # -------------------------------------------------------------------------
    reserved_keys: Set[str] = set()

    # Reserve all original keys from single-key clusters first so that newly 
    # generated canonical keys never collide with an untouched existing key.
    for group in clusters.values():
        distinct_keys = {e.key for e in group}
        for k in distinct_keys:
            reserved_keys.add(k)

    output_blocks: List[str] = []
    alias_to_canonical: Dict[str, str] = {}
    multi_key_paper_count = 0
    redundant_records_merged = 0

    if verbose:
        print("\n=== Duplicate Clustering & Crossref Resolution ===")

    # Determine whether to emit crossref stubs in the .bib file:
    # By default, ALWAYS emit them so .tex files don't need to be touched.
    emit_crossrefs = not (merge_latex_files and drop_crossrefs_on_merge)

    for group in clusters.values():
        # Choose the highest-scoring (most complete) BibTeX entry in the cluster
        master_entry = max(group, key=lambda e: e.completeness_score())

        # Collect all distinct citation keys used for this paper across all files
        distinct_keys: List[str] = []
        for e in group:
            if e.key not in distinct_keys:
                distinct_keys.append(e.key)

        if len(group) > 1:
            redundant_records_merged += len(group) - 1

        if len(distinct_keys) > 1 or rename_all:
            if len(distinct_keys) > 1:
                multi_key_paper_count += 1

            # Temporarily free this cluster's own keys from `reserved_keys` so
            # that if one of the existing keys is ALREADY `BellovaryEtAl2019`, 
            # `generate_canonical_key` can pick `BellovaryEtAl2019` instead of 
            # `BellovaryEtAl2019a`.
            for k in distinct_keys:
                reserved_keys.discard(k)

            canonical_key = generate_canonical_key(master_entry, reserved_keys)

            # Re-reserve all alias keys as well so no other paper can take them
            for k in distinct_keys:
                reserved_keys.add(k)
        else:
            canonical_key = distinct_keys[0]
            reserved_keys.add(canonical_key)

        # All original keys that differ from `canonical_key` become crossref aliases
        alias_keys = [k for k in distinct_keys if k != canonical_key]
        for alias in alias_keys:
            alias_to_canonical[alias] = canonical_key

        if verbose and (len(group) > 1 or alias_keys):
            raw_title = strip_outer_delimiters(master_entry.fields.get('title', 'Untitled'))
            short_title = (raw_title[:52] + '...') if len(raw_title) > 55 else raw_title
            print(
                f"  * Canonical: {canonical_key:<24} | "
                f"Crossrefs: {str(alias_keys):<36} | "
                f"Title: \"{short_title}\""
            )

        block_str = format_cluster_for_bibtex(
            master_entry=master_entry,
            canonical_key=canonical_key,
            alias_keys=alias_keys,
            emit_crossrefs=emit_crossrefs
        )
        output_blocks.append(block_str)

    # -------------------------------------------------------------------------
    # Step 4: Print Summary & Write Output Files
    # -------------------------------------------------------------------------
    print("\n=== Execution Summary ===")
    print(f"Input .bib files processed            : {len(input_files)}")
    print(f"Total BibTeX entries scanned          : {total_entries}")
    print(f"Unique physical papers identified     : {len(clusters)}")
    print(f"Duplicate full records eliminated     : {redundant_records_merged}")
    print(f"Papers with multiple keys unified     : {multi_key_paper_count}")
    print(f"Crossref alias entries generated      : {len(alias_to_canonical) if emit_crossrefs else 0}")
    if not merge_latex_files:
        print("LaTeX (.tex) files                    : UNTOUCHED (all old keys preserved via crossref)")

    if dry_run:
        print("\n[DRY RUN] No files were written or modified on disk.")
        return

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(
                "%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n"
                "%% Awesome! Automatically merged and deduplicated by MergeBibTex.py\n"
                "%% Standard BibTeX crossref aliases are placed immediately ABOVE\n"
                "%% their canonical parent entry as required by the BibTeX engine.\n"
                "%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n\n"
            )
            f.write("\n\n".join(output_blocks) + "\n")
        print(f"Merged BibTeX file written to         : {output_file}")
    except OSError as err:
        sys.stderr.write(f"[ERROR] Failed to write output file '{output_file}': {err}\n")
        sys.exit(1)

    # Only modify .tex files if --merge-latex / -mtex was explicitly passed
    if merge_latex_files:
        replace_keys_in_latex_files(
            tex_files=merge_latex_files,
            alias_map=alias_to_canonical,
            create_backup=not no_backup,
            verbose=verbose
        )


# ========================================
# COMMAND-LINE INTERFACE (--help / -h)
# =======================================

def parse_cli_arguments() -> argparse.Namespace:
    epilog_help = r"""
===============================================================
DETAILED USAGE EXAMPLES (because I KNOW I will forget these...)
==============================================================

1. DEFAULT WORKFLOW (Safe for Multi-Author Collaboration — Does NOT touch .tex):
   Merges `mbh.bib`, `ucb.bib`, `emri.bib`, `emri2.bib`, and `emri3.bib` into 
   `merged.bib`. Detects duplicate papers via `title`, `doi`, and `adsurl`. 
   When a paper appears under multiple keys (e.g., `2019MNRAS.482.2913B`, 
   `BellovaryEtAl2019`, and `amazingpaperxxxxx`), renames the master entry to 
   `BellovaryEtAl2019` and keeps `2019MNRAS.482.2913B` and `amazingpaperxxxxx` 
   immediately above it using `crossref = {BellovaryEtAl2019}`:

     $ MergeBibTex.py mbh.bib ucb.bib emri.bib emri2.bib emri3.bib -o merged.bib

2. DRY RUN WITH VERBOSE LOGGING (Inspect duplicates before writing anything):
   Prints every detected duplicate cluster, the chosen canonical key, and all 
   linked `crossref` keys without writing or modifying any files:

     $ MergeBibTex.py *.bib -v -n

3. MERGE LATEX CITATIONS (`--merge-latex` / `-mtex`):
   If you want to replace all variant keys (like `\cite{amazingpaperxxxxx}` 
   and `\cite{2019MNRAS.482.2913B}`) directly inside your LaTeX files with the 
   single canonical key (`\cite{BellovaryEtAl2019}`), pass `-mtex` followed by 
   your `.tex` files (automatic `.tex.bak` backups are created):

     $ MergeBibTex.py *.bib -o merged.bib -mtex main.tex section1.tex section2.tex

4. RENAME EVERY ENTRY IN THE BIBLIOGRAPHY (`--rename-all`):
   By default, only papers that show up with multiple different keys (or when 
   `-mtex` is used with `--rename-all`) are renamed to `Surname1Year` / 
   `Surname1Surname2Year` / `Surname1EtAlYear`. To enforce this naming 
   convention across EVERY entry in the `.bib` file (while still keeping old 
   keys working via `crossref`):

     $ MergeBibTex.py *.bib -o merged.bib --rename-all
"""

    parser = argparse.ArgumentParser(
        prog="MergeBibTex.py",
        description=(
            "Merge multiple BibTeX (.bib) files into a single file, identifying "
            "duplicate papers by normalizing and comparing 'title', 'doi', and "
            "'adsurl'. When the same paper appears under different citation keys, "
            "renames the master entry to Surname1Year (1 author), "
            "Surname1Surname2Year (2 authors), or Surname1EtAlYear (>2 authors), "
            "and links all other keys to it via standard BibTeX 'crossref = {...}' "
            "entries placed immediately adjacent to the master entry."
        ),
        epilog=epilog_help,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "inputs",
        nargs="+",
        metavar="BIB_FILE",
        help="One or more input .bib files to merge and deduplicate."
    )

    parser.add_argument(
        "-o", "--output",
        type=str,
        default="merged_clean.bib",
        metavar="OUT_BIB",
        help="Output filename for the merged BibTeX file (default: merged_clean.bib)."
    )

    parser.add_argument(
        "-mtex", "--merge-latex",
        nargs="+",
        metavar="TEX_FILE",
        dest="merge_latex",
        help=(
            "Optional list of LaTeX (.tex) files in which to replace all aliased "
            "citation keys inside \\cite{...} commands with the single canonical "
            "key (e.g., replacing 'amazingpaperxxxxx' with 'BellovaryEtAl2019'). "
            "If omitted, .tex files are NOT modified and all keys remain active "
            "in the .bib file via 'crossref'."
        )
    )

    parser.add_argument(
        "--drop-crossrefs",
        action="store_true",
        help=(
            "Only used together with --merge-latex (-mtex): after replacing all "
            "old keys in the .tex files, omit the 'crossref' alias stubs from "
            "the output .bib file."
        )
    )

    parser.add_argument(
        "--no-backup",
        action="store_true",
        help=(
            "Only used together with --merge-latex (-mtex): do not create .bak "
            "backup files when modifying .tex files."
        )
    )

    parser.add_argument(
        "--rename-all",
        action="store_true",
        help=(
            "Rename ALL BibTeX entries to Surname1Year / Surname1Surname2Year / "
            "Surname1EtAlYear (linking their original keys via 'crossref'), "
            "even for papers that only appeared once."
        )
    )

    parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        help="Run the duplicate analysis and print statistics without writing any files."
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print detailed per-cluster logs showing canonical keys and crossref aliases."
    )

    return parser.parse_args()


if __name__ == "__main__":
    cli_args = parse_cli_arguments()
    process_bib_files(
        input_files=cli_args.inputs,
        output_file=cli_args.output,
        rename_all=cli_args.rename_all,
        merge_latex_files=cli_args.merge_latex,
        drop_crossrefs_on_merge=cli_args.drop_crossrefs,
        no_backup=cli_args.no_backup,
        dry_run=cli_args.dry_run,
        verbose=cli_args.verbose
    )

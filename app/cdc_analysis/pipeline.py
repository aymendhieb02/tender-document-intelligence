"""Deterministic structure reconstruction over ordered source elements only."""
from collections import defaultdict
import re
from typing import Any

from .contract import DocumentInput, DocumentResultAdapter
from .adapter import IntelligenceDocumentAdapter
from .headings import HeadingDetector, LanguagePack, classify, normalize
from .schema import (Annex, Article, Diagnostic, Evidence, Paragraph, Requirement,
                     Section, SpecialDocument, TableReference, TenderDocument)
from .requirements import enrich_requirements


class CDCAnalyzer:
    def __init__(self, language_pack: LanguagePack | None = None,
                 adapter: DocumentResultAdapter | None = None):
        self.pack = language_pack or LanguagePack()
        self.detector = HeadingDetector(self.pack)
        self.adapter = adapter

    def analyze(self, document_result: Any) -> TenderDocument:
        if self.adapter is not None:
            document = self.adapter.adapt(document_result)
        elif isinstance(document_result, DocumentInput):
            document = document_result
        elif callable(getattr(document_result, "model_dump", None)):
            document = IntelligenceDocumentAdapter().adapt(document_result)
        elif isinstance(document_result, dict):
            document = (IntelligenceDocumentAdapter().adapt(document_result)
                        if "source_type" in document_result and "diagnostics" in document_result
                        else DocumentInput.model_validate(document_result))
        else:
            raise TypeError("Provide a DocumentResultAdapter for the producer's DocumentResult")
        result = TenderDocument(document_id=document.document_id, metadata=dict(document.metadata))
        stack: list[tuple[int, Section]] = []
        article = None
        annex = None
        toc_candidates = []
        observed = []
        counters = defaultdict(int)

        def new_id(kind):
            counters[kind] += 1
            node_id = f"{kind}-{counters[kind]}"
            result.source_order.append(node_id)
            return node_id

        def evidence(page, element, line=None):
            parts = element.parts
            return Evidence(document_id=document.document_id, page=page.page_number,
                            element_id=element.id, raw_text=element.text, bbox=element.bbox,
                            coordinate_space=page.coordinate_space, page_width=page.width,
                            page_height=page.height, line_index=line,
                            source_element_ids=[p.id for p in parts] or [element.id],
                            source_text_parts=[p.text for p in parts] or [element.text],
                            source_element_types=[p.source_type for p in parts] or [element.source_type],
                            source_element_confidences=[p.confidence for p in parts] or [element.confidence])

        def extend(page):
            for _, section in stack:
                section.end_page = page
            if article is not None:
                article.page_end = page
            if annex is not None:
                annex.page_end = page

        # Only repeated text in the same margin is furniture. Repetition alone is insufficient.
        margins = defaultdict(set)
        def margin_key(page, element):
            if not element.bbox or not page.height:
                return None
            _, top, _, bottom = element.bbox
            band = "top" if bottom <= page.height * .10 else "bottom" if top >= page.height * .90 else None
            if band is None:
                return None
            return band, re.sub(r"\d+", "#", normalize(element.text))

        for page in document.pages:
            for element in page.elements:
                key = margin_key(page, element)
                if key:
                    margins[key].add(page.page_number)
        repeated = {key for key, pages in margins.items() if len(pages) >= 3}
        annexes_per_page = defaultdict(int)
        for page in document.pages:
            for element in page.elements:
                heading = self.detector.detect(element.text, element.kind, element.heading_level)
                if heading and heading.kind == "annex":
                    annexes_per_page[page.page_number] += 1
        indexed_annex_pages = {number for number, count in annexes_per_page.items() if count >= 2}
        contact_only_pages = set()
        for page in document.pages:
            content = [normalize(e.text) for e in page.elements if e.text.strip()]
            if len(content) <= 20 and content:
                furniture = sum(bool(re.search(r"(?:https?://|www\.|facebook|telephone|\btel\b|page\s*\|?\s*\d+|\+?\d{2,})", line)) for line in content)
                contact_signals = sum(bool(re.search(r"(?:https?://|www\.|facebook|telephone|\btel\b|@)", line)) for line in content)
                if contact_signals >= 2 and furniture / len(content) >= 0.60:
                    contact_only_pages.add(page.page_number)
        toc_entry = re.compile(self.pack.toc_entry, re.I)
        toc_title = re.compile(self.pack.toc_title, re.I)

        for page in document.pages:
            toc_mode = False
            toc_annex_pending = None
            if page.page_number in contact_only_pages:
                for element in page.elements:
                    result.furniture_evidence.append(evidence(page, element))
                continue
            if not page.elements:
                extend(page.page_number)
            for element in page.elements:
                ev = evidence(page, element)
                if element.kind in ("header", "footer") or margin_key(page, element) in repeated:
                    result.furniture_evidence.append(ev)
                    continue
                section_id = stack[-1][1].id if stack else None
                if element.kind == "table":
                    extend(page.page_number)
                    table = TableReference(id=new_id("table"), table_id=element.table_id or element.id,
                                           table_type=annex.annex_type if annex else classify(element.text, self.pack),
                                           source_section=section_id, source_annex=annex.id if annex else None,
                                           source_evidence=[ev])
                    result.tables.append(table)
                    owner = article or annex or (stack[-1][1] if stack else None)
                    if owner is not None:
                        owner.table_refs.append(table.id)
                    continue
                for line_index, raw_line in enumerate(element.text.splitlines()):
                    text = raw_line.strip()
                    if not text:
                        continue
                    ev = evidence(page, element, line_index)
                    norm = normalize(text)
                    annex_repeat = re.match(r"^annexes\s+(\d+)\b", norm)
                    if annex and annex_repeat and annex.number == annex_repeat.group(1).zfill(2):
                        annex.source_evidence.append(ev)
                        annex.page_end = page.page_number
                        for _, parent_section in stack[:-1]:
                            parent_section.end_page = page.page_number
                        result.furniture_evidence.append(ev)
                        continue
                    if toc_title.fullmatch(norm):
                        toc_mode = True
                        result.toc_evidence.append(ev)
                        continue
                    entry = toc_entry.match(raw_line)
                    if element.kind == "toc" or entry:
                        result.toc_evidence.append(ev)
                        if entry:
                            candidate = self.detector.detect(entry.group("title"))
                            if candidate:
                                toc_candidates.append((candidate, int(entry.group("page")), ev))
                        continue
                    # Untagged TOC lines remain evidence, unless actual layout marks body start.
                    if toc_mode and element.kind != "heading":
                        result.toc_evidence.append(ev)
                        toc_heading_text = re.sub(r"\s*\(\s*pages?\s+\d+(?:\s*[-–]\s*[^)]*)?\s*\)\s*$", "", text, flags=re.I)
                        candidate = self.detector.detect(toc_heading_text)
                        if candidate:
                            page_match = re.search(r"\bpages?\s+(\d+)(?:\s*[-–]\s*\d+)?", text, re.I)
                            toc_candidates.append((candidate, int(page_match.group(1)) if page_match else None, ev))
                            toc_annex_pending = candidate if candidate.kind == "annex" and not candidate.title else None
                        elif toc_annex_pending and len(text) < 220:
                            from dataclasses import replace
                            candidate, expected_page, prior_ev = toc_candidates[-1]
                            updated = replace(candidate, title=text)
                            toc_candidates[-1] = (updated, expected_page, prior_ev)
                            toc_annex_pending = None
                        continue
                    toc_mode = False
                    if result.title is None and re.search(self.pack.document_title, norm):
                        result.title = text
                        result.title_evidence.append(ev)
                        continue
                    heading = self.detector.detect(text, element.kind, element.heading_level)
                    if toc_annex_pending and heading is None and len(text) < 220:
                        from dataclasses import replace
                        candidate, expected_page, prior_ev = toc_candidates[-1]
                        toc_candidates[-1] = (replace(candidate, title=text), expected_page, prior_ev)
                        result.toc_evidence.append(ev)
                        toc_annex_pending = None
                        continue
                    if heading and heading.kind == "section" and element.kind != "heading" and not element.bold:
                        row_number = re.search(r"row-(\d+)$", element.id)
                        if row_number and int(row_number.group(1)) > 2:
                            heading = None
                    if heading and heading.kind == "annex" and page.page_number in indexed_annex_pages:
                        result.toc_evidence.append(ev)
                        toc_candidates.append((heading, None, ev))
                        toc_annex_pending = heading if not heading.title else None
                        continue
                    pending = article or annex or (stack[-1][1] if stack else None)
                    pending_empty = (pending is not None and pending.title is None
                            and len(pending.source_evidence) == 1
                            and not getattr(pending, "paragraphs", [])
                            and not getattr(pending, "clauses", [])
                            and not getattr(pending, "articles", [])
                            and not getattr(pending, "subsections", [])
                            and not pending.table_refs)
                    typed_annex_title = isinstance(pending, Annex) and classify(text, self.pack) != "unknown"
                    typographic_title = element.bold or element.kind == "heading"
                    if (isinstance(pending, Annex) and pending.title is None
                            and typed_annex_title and len(text) < 180
                            and (text.upper() == text or element.kind == "heading" or element.bold)
                            and (heading is None or not heading.patterned)):
                        pending.title = text
                        pending.annex_type = classify(text, self.pack)
                        pending.source_evidence.append(ev)
                    elif (pending_empty and len(text) < 180 and (typographic_title or typed_annex_title)
                            and (heading is None or not heading.patterned)):
                        pending.title = text
                        pending.source_evidence.append(ev)
                        if isinstance(pending, Annex):
                            pending.annex_type = classify(text, self.pack)
                        elif isinstance(pending, Section):
                            pending.normalized_title = norm
                        extend(page.page_number)
                        continue
                    if heading and heading.kind == "subsection" and article is not None:
                        heading = None  # decimal clauses inside an article belong to that article
                    if heading and heading.kind == "section" and annex is not None:
                        row_number = re.search(r"row-(\d+)$", element.id)
                        early_page_heading = bool(row_number and int(row_number.group(1)) <= 1
                                                  and (element.bold or element.kind == "heading"
                                                       or (heading.title or "").isupper()))
                        if not early_page_heading:
                            heading = None
                    if heading:
                        observed.append((heading, page.page_number, ev))
                        if heading.kind in ("section", "subsection"):
                            article = None
                            if heading.kind == "subsection" and annex is not None:
                                while stack and stack[-1][0] >= heading.level:
                                    stack.pop()
                                subsection = Section(
                                    id=new_id("section"), number=heading.number, title=heading.title,
                                    normalized_title=normalize(heading.title) if heading.title else None,
                                    start_page=page.page_number, end_page=page.page_number, source_evidence=[ev],
                                    evidence_status="detected", signals={"numbering_pattern": True,
                                                                          "typography_signal": element.kind == "heading" or bool(element.bold),
                                                                          "toc_match": False})
                                annex.subsections.append(subsection)
                                stack.append((heading.level, subsection))
                                extend(page.page_number)
                                continue
                            annex = None
                            while stack and stack[-1][0] >= heading.level:
                                stack.pop()
                            section = Section(id=new_id("section"), number=heading.number, title=heading.title,
                                              normalized_title=normalize(heading.title) if heading.title else None,
                                              start_page=page.page_number, end_page=page.page_number,
                                              source_evidence=[ev], evidence_status="detected" if heading.patterned else "probable",
                                              signals={"numbering_pattern": heading.patterned,
                                                       "typography_signal": element.kind == "heading" or bool(element.bold),
                                                       "toc_match": False})
                            (stack[-1][1].subsections if stack else result.sections).append(section)
                            if heading.level > (stack[-1][0] + 1 if stack else 1):
                                result.diagnostics.append(Diagnostic(code="hierarchy_gap", message="Missing parent heading; attached to nearest known ancestor", source_evidence=[ev]))
                            stack.append((heading.level, section))
                        elif heading.kind == "article":
                            article = Article(id=new_id("article"), number=heading.number, title=heading.title,
                                              page_start=page.page_number, page_end=page.page_number, source_evidence=[ev])
                            owner_articles = annex.articles if annex else stack[-1][1].articles if stack else result.articles
                            if any(a.number == article.number for a in owner_articles):
                                result.diagnostics.append(Diagnostic(code="duplicate_article_number", message="Repeated article number in the same parent", source_evidence=[ev]))
                            owner_articles.append(article)
                        else:
                            article = None
                            annex = Annex(id=new_id("annex"), number=heading.number, title=heading.title,
                                          page_start=page.page_number, page_end=page.page_number,
                                          annex_type=classify(heading.title or "", self.pack),
                                          source_section=stack[-1][1].id if stack else None, source_evidence=[ev])
                            result.annexes.append(annex)
                        extend(page.page_number)
                        continue
                    extend(page.page_number)
                    clause = re.match(self.pack.clause, text, re.I)
                    decimal = re.match(self.pack.subsection, text, re.I) if article else None
                    paragraph = Paragraph(id=new_id("paragraph"), text=text,
                                          number=(clause or decimal).group("number") if clause or decimal else None,
                                          page_start=page.page_number, page_end=page.page_number, source_evidence=[ev])
                    if article:
                        article.clauses.append(paragraph)
                        article.text += ("\n" if article.text else "") + text
                        article.source_evidence.append(ev)
                    elif annex:
                        annex.paragraphs.append(paragraph)
                    elif stack:
                        stack[-1][1].paragraphs.append(paragraph)
                    else:
                        result.paragraphs.append(paragraph)
                    # Raw requirement candidates only; no inferred values or BOQ row extraction.
                    if annex and annex.annex_type in ("boq", "price_schedule"):
                        continue
                    for category, pattern in self.pack.requirements:
                        if re.search(pattern, norm):
                            result.requirements.append(Requirement(
                                id=new_id("requirement"), type=category, text=text, source_page=page.page_number,
                                source_bbox=element.bbox, source_section=stack[-1][1].id if stack else None,
                                source_article=article.id if article else None, source_annex=annex.id if annex else None,
                                source_evidence=[ev]))

        for candidate, expected_page, ev in toc_candidates:
            matches = [(h, p, e) for h, p, e in observed if h.kind == candidate.kind and h.number == candidate.number]
            if not matches:
                result.diagnostics.append(Diagnostic(code="toc_unconfirmed", message="TOC entry has no confirmed body heading", source_evidence=[ev]))
            elif not any(p == expected_page for _, p, _ in matches):
                if expected_page is not None:
                    result.diagnostics.append(Diagnostic(code="toc_disagreement", message=f"TOC page {expected_page}; body pages {[p for _, p, _ in matches]}. Physical body pages retained; printed labels may differ.", source_evidence=[ev] + [e for _, _, e in matches]))
            elif candidate.title and matches[0][0].title and normalize(candidate.title) != normalize(matches[0][0].title):
                toc_name, body_name = normalize(candidate.title), normalize(matches[0][0].title)
                if toc_name not in body_name and body_name not in toc_name:
                    result.diagnostics.append(Diagnostic(code="toc_title_disagreement", message=f"TOC title '{candidate.title}' differs from body title '{matches[0][0].title}'; body title retained", source_evidence=[ev, matches[0][2]]))
            if candidate.kind == "annex" and candidate.title:
                matching_annex = next((node for node in result.annexes if node.number == candidate.number), None)
                if matching_annex and (matching_annex.title is None or expected_page is None):
                    matching_annex.title = candidate.title
                    if ev not in matching_annex.source_evidence:
                        matching_annex.source_evidence.append(ev)
                    matching_annex.annex_type = classify(candidate.title, self.pack)

        def visit_sections(sections):
            for section in sections:
                section.signals["toc_match"] = any(c.kind in ("section", "subsection") and c.number == section.number for c, _, _ in toc_candidates)
                yield section
                yield from visit_sections(section.subsections)

        for node in [*visit_sections(result.sections), *result.annexes]:
            if isinstance(node, Annex) and node.annex_type == "unknown" and node.subsections:
                node.annex_type = classify(" ".join(s.title or "" for s in node.subsections), self.pack)
            kind = node.annex_type if isinstance(node, Annex) else classify(node.title or "", self.pack)
            if kind != "unknown":
                start = node.page_start if isinstance(node, Annex) else node.start_page
                end = node.page_end if isinstance(node, Annex) else node.end_page
                result.detected_special_documents.append(SpecialDocument(
                    id=f"special-{node.id}", document_type=kind, page_start=start, page_end=end,
                    source_node=node.id, source_evidence=node.source_evidence,
                    handoff="boq_agent" if kind == "boq" else None))
            elif isinstance(node, Annex):
                result.diagnostics.append(Diagnostic(code="unknown_annex_type", message="Annex classification needs human review", source_evidence=node.source_evidence))
        if not result.sections:
            result.diagnostics.append(Diagnostic(code="no_sections", message="No section headings confirmed; unassigned content is preserved"))
        if not document.pages:
            result.diagnostics.append(Diagnostic(code="empty_document", message="Document has no pages"))
        if any(not p.height or any(e.bbox is None for e in p.elements) for p in document.pages):
            result.diagnostics.append(Diagnostic(code="limited_layout", message="Missing geometry limits automatic furniture suppression and heading disambiguation"))
        if document.metadata.get("cdc_adapter") == "document_intelligence_v1":
            result.diagnostics.append(Diagnostic(code="producer_semantic_layout_unavailable", message="Producer currently supplies text and geometry, not heading levels, TOC kinds or table candidates. Generic geometry retained in metadata; no table semantics inferred."))
        result.requirements.extend(enrich_requirements(result.sections, result.annexes))
        return result

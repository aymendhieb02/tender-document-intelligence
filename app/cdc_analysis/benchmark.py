"""Exact-match structural metrics. Predictions can never self-verify labels."""
from typing import Any
from .schema import TenderDocument


def structural_records(document: TenderDocument) -> dict[str, list[dict[str, Any]]]:
    records: dict[str, list[dict[str, Any]]] = {k: [] for k in ("sections", "articles", "annexes", "annex_subsections", "requirements", "special_documents")}

    def articles(items, parent):
        for item in items:
            records["articles"].append(dict(parent=parent, number=item.number, title=item.title,
                                             start=item.page_start, end=item.page_end,
                                             source_page=item.source_evidence[0].page if item.source_evidence else None))

    def sections(items, parent="document"):
        for index, item in enumerate(items):
            path = f"{parent}/section[{index}]"
            records["sections"].append(dict(parent=parent, number=item.number, title=item.title,
                                             start=item.start_page, end=item.end_page,
                                             source_page=item.source_evidence[0].page if item.source_evidence else None))
            articles(item.articles, path)
            sections(item.subsections, path)

    sections(document.sections)
    articles(document.articles, "document")
    for index, item in enumerate(document.annexes):
        records["annexes"].append(dict(number=item.number, title=item.title, start=item.page_start,
                                      end=item.page_end, annex_type=item.annex_type,
                                      source_page=item.source_evidence[0].page if item.source_evidence else None))
        articles(item.articles, f"document/annex[{index}]")
        for child in item.subsections:
            records["annex_subsections"].append(dict(parent=item.number, number=child.number, title=child.title,
                start=child.start_page, end=child.end_page,
                source_page=child.source_evidence[0].page if child.source_evidence else None))
    for item in document.requirements:
        records["requirements"].append(dict(type=item.type, text=item.text, page=item.source_page))
    nodes = {section.id: section for section in (node for node in document.sections)}
    # Also index nested structural parents for special-document provenance.
    def index_sections(items):
        for item in items:
            nodes[item.id] = item
            index_sections(item.subsections)
    index_sections(document.sections)
    annex_nodes = {item.id: item for item in document.annexes}
    for item in document.detected_special_documents:
        node = nodes.get(item.source_node) or annex_nodes.get(item.source_node)
        number = node.number if node else None
        records["special_documents"].append(dict(document_type=item.document_type,
            start=item.page_start, end=item.page_end, number=number,
            source_page=item.source_evidence[0].page if item.source_evidence else None))
    return records


def evaluate(prediction: TenderDocument, ground_truth: dict) -> dict:
    if (ground_truth.get("status") != "verified" or not ground_truth.get("reviewer")
            or not ground_truth.get("verified_at") or not ground_truth.get("source_sha256")):
        return {"status": "NOT YET MEASURABLE", "reason": "Human-verified source-linked labels required"}
    if ground_truth.get("document_id") != prediction.document_id:
        raise ValueError("Ground truth and prediction document IDs differ")
    from collections import Counter
    from json import dumps

    metrics = {}
    for category, rows in structural_records(prediction).items():
        if category not in ground_truth.get("records", {}):
            continue  # Unlabelled categories are not negatives.
        expected = ground_truth["records"][category]
        actual_counts = Counter(dumps(row, sort_keys=True, ensure_ascii=False) for row in rows)
        expected_counts = Counter(dumps(row, sort_keys=True, ensure_ascii=False) for row in expected)
        correct = sum((actual_counts & expected_counts).values())
        metrics[category] = {"exact_matches": correct, "predicted": len(rows), "expected": len(expected),
                             "precision": correct / len(rows) if rows else None,
                             "recall": correct / len(expected) if expected else None}
    # Distinguish structure, titles, boundaries, classification and evidence pages.
    def score(name, expected, actual, fields):
        if name in metrics:
            return
        from collections import Counter
        expected_counts = Counter(tuple(row.get(field) for field in fields) for row in expected)
        actual_counts = Counter(tuple(row.get(field) for field in fields) for row in actual)
        correct = sum((expected_counts & actual_counts).values())
        metrics[name] = {"exact_matches": correct, "predicted": len(actual), "expected": len(expected),
                         "precision": correct / len(actual) if actual else None,
                         "recall": correct / len(expected) if expected else None}

    sections = structural_records(prediction)["sections"]
    expected_sections = ground_truth.get("records", {}).get("sections", [])
    major = lambda rows: [row for row in rows if row.get("parent") == "document" and row.get("number") in set("ABCDE")]
    if "sections" in ground_truth.get("records", {}):
        score("major_section_detection", major(expected_sections), major(sections), ("number", "source_page"))
        score("section_title_matching", expected_sections, sections, ("parent", "number", "title"))
        score("section_boundary_accuracy", expected_sections, sections, ("parent", "number", "start", "end"))
        score("source_page_accuracy", expected_sections, sections, ("parent", "number", "source_page"))
    articles = structural_records(prediction)["articles"]
    if "articles" in ground_truth.get("records", {}):
        score("article_detection", ground_truth["records"]["articles"], articles, ("parent", "source_page"))
        score("article_numbering", ground_truth["records"]["articles"], articles, ("parent", "number"))
        score("article_title_matching", ground_truth["records"]["articles"], articles, ("parent", "number", "title"))
        score("article_page_range_accuracy", ground_truth["records"]["articles"], articles, ("parent", "number", "start", "end"))
        score("article_source_page_accuracy", ground_truth["records"]["articles"], articles, ("parent", "number", "source_page"))
    annexes = structural_records(prediction)["annexes"]
    if "annexes" in ground_truth.get("records", {}):
        score("annex_detection", ground_truth["records"]["annexes"], annexes, ("number", "source_page"))
        score("annex_classification", ground_truth["records"]["annexes"], annexes, ("number", "annex_type"))
        score("annex_source_page_accuracy", ground_truth["records"]["annexes"], annexes, ("number", "source_page"))
        score("boq_annex_detection", [x for x in ground_truth["records"]["annexes"] if x.get("annex_type") == "boq"],
              [x for x in annexes if x.get("annex_type") == "boq"], ("number", "start", "end"))
    children = structural_records(prediction)["annex_subsections"]
    if "annex_subsections" in ground_truth.get("records", {}):
        expected_children = ground_truth["records"]["annex_subsections"]
        score("annex_subsection_detection", expected_children, children, ("parent", "number", "source_page"))
        score("annex_subsection_title_matching", expected_children, children, ("parent", "number", "title"))
        score("annex_subsection_page_range_accuracy", expected_children, children, ("parent", "number", "start", "end"))
    if "special_documents" in ground_truth.get("records", {}):
        score("special_document_classification", ground_truth["records"]["special_documents"],
              structural_records(prediction)["special_documents"], ("document_type", "number", "start", "end"))
    return {"status": "measured", "method": "exact record multiset match including ranges and numbering", "metrics": metrics}

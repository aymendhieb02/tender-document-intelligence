from pathlib import Path

import pytest

from app.boq import extract_male_municipal_from_document
from app.cdc_analysis import CDCAnalyzer
from app.document_intelligence import DocumentProcessor, document_intelligence_contract_version
from app.document_intelligence.schemas import EvidenceElement, GeometryGroup, PageResult


ROOT = Path(__file__).resolve().parents[2]
REFERENCE_PDF = ROOT / "datasets/boq/male_municipal_maintenance_v1/reference/MM_Cahier-des-charges-type-Entretien.pdf"


def test_reference_document_result_flows_through_cdc_and_specialized_boq():
    assert document_intelligence_contract_version == "1.0"
    assert all(item is not None for item in (EvidenceElement, GeometryGroup, PageResult))
    document = DocumentProcessor(mode="native", use_cache=False).process(REFERENCE_PDF)

    assert len(document.pages) == 30
    assert document.diagnostics.ocr_page_count == 0
    tender = CDCAnalyzer().analyze(document)
    assert tender.document_id == document.document_id

    handoff = next(item for item in tender.detected_special_documents if item.handoff == "boq_agent")
    assert handoff.document_type == "boq"
    assert (handoff.page_start, handoff.page_end) == (25, 25)

    result = extract_male_municipal_from_document(document, page_number=handoff.page_start)
    assert result.document_id == document.document_id
    assert result.detected is True
    assert result.extractor_family == "MALE_MUNICIPAL_MAINTENANCE_BOQ_V1"
    assert len(result.rows) == 5
    assert all(row.source_page == 25 for row in result.rows)
    assert all(row.quantity.normalized_value is None for row in result.rows)
    assert all(row.unit_price_ht.normalized_value is None for row in result.rows)
    assert all(row.total_ht.normalized_value is None for row in result.rows)
    assert all(not row.article.evidence for row in result.rows if row.article.value_origin == "TEMPLATE_INFERRED")

    page25 = document.pages[24]
    observed_ids = {element.id for element in page25.elements}
    observed = next(evidence for evidence in result.source_evidence
                    if evidence.source_page == 25 and evidence.element_ids)
    assert set(observed.element_ids) <= observed_ids
    assert observed.raw_text
    source_element = next(element for element in page25.elements if element.id in observed.element_ids)
    assert observed.source == source_element.source
    assert observed.ocr_confidence == source_element.confidence
    assert observed.source_bbox is not None


def test_cdc_rejects_evidence_claiming_a_different_physical_page():
    document = DocumentProcessor(mode="native", use_cache=False).process(REFERENCE_PDF)
    first_page = document.pages[0]
    assert first_page.elements
    invalid_element = first_page.elements[0].model_copy(update={"page_number": 31})
    invalid_page = first_page.model_copy(update={"elements": [invalid_element, *first_page.elements[1:]]})
    invalid_document = document.model_copy(update={"pages": [invalid_page, *document.pages[1:]]})

    with pytest.raises(ValueError, match="Element page does not match its containing page"):
        CDCAnalyzer().analyze(invalid_document)

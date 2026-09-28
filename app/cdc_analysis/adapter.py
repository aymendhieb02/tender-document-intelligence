"""Consumer-side mapping of the Document Intelligence schema, with no OCR imports."""
from typing import Any

from .contract import DocumentInput, ElementInput, PageInput


class IntelligenceDocumentAdapter:
    def adapt(self, document_result: Any) -> DocumentInput:
        value = document_result if isinstance(document_result, dict) else document_result.model_dump(mode="json")
        if value.get("source_type") not in ("pdf", "image") or "diagnostics" not in value:
            raise ValueError("Expected the Document Intelligence DocumentResult contract")
        pages = []
        all_geometry = {}
        for page in value["pages"]:
            producer_elements = {item["id"]: item for item in page["elements"]}
            elements = []
            page_geometry = page.get("geometry") or {}
            rows = page_geometry.get("rows", []) if isinstance(page_geometry, dict) else []
            # Document Intelligence currently returns words. Group its own geometric
            # rows into line candidates, while keeping every producer word and bbox.
            groups = [row.get("element_ids", []) for row in rows if row.get("element_ids")]
            assigned = {element_id for group in groups for element_id in group}
            groups.extend([[key] for key in producer_elements if key not in assigned])
            for row_index, group in enumerate(groups):
                items = [producer_elements[element_id] for element_id in group if element_id in producer_elements]
                if not items:
                    continue
                items.sort(key=lambda item: (item.get("bbox") or {}).get("x1", 0))
                for item in items:
                    if item.get("page_number", page["page_number"]) != page["page_number"]:
                        raise ValueError("Element page does not match its containing page")
                    if item.get("coordinate_space") not in (None, page["coordinate_space"]):
                        raise ValueError("Element and page coordinate spaces differ")
                bboxes = [item["bbox"] for item in items if item.get("bbox")]
                bbox = ((min(box["x1"] for box in bboxes), min(box["y1"] for box in bboxes),
                         max(box["x2"] for box in bboxes), max(box["y2"] for box in bboxes))
                        if bboxes else None)
                elements.append(ElementInput(
                    id=f"p{page['page_number']}-row-{row_index:04d}",
                    text=" ".join(item["text"] for item in items), bbox=bbox,
                    parts=[{"id": item["id"], "text": item["text"],
                            "bbox": tuple(item["bbox"][k] for k in ("x1", "y1", "x2", "y2"))
                            if item.get("bbox") else None} for item in items]))
            pages.append(PageInput(page_number=page["page_number"], width=page["width"], height=page["height"],
                                   coordinate_space=page["coordinate_space"], elements=elements))
            # Preserve page transforms and layout counts without retaining duplicate
            # geometry arrays or falsely treating visual rows as semantic tables.
            all_geometry[str(page["page_number"])] = {
                "pdf_to_page": page.get("pdf_to_page"), "pdf_rotation": page.get("pdf_rotation"),
                "geometry_method": page_geometry.get("method"),
                "geometry_row_count": len(rows), "geometry_cell_count": len(page_geometry.get("cells", [])),
                "geometry_region_count": len(page_geometry.get("regions", [])),
                "diagnostics": page.get("diagnostics")}
        return DocumentInput(document_id=value["document_id"], pages=pages,
                             metadata={"source_type": value["source_type"], "mode": value.get("mode"),
                                       "producer_diagnostics": value["diagnostics"],
                                       "producer_page_geometry": all_geometry,
                                       "cdc_adapter": "document_intelligence_v1"})

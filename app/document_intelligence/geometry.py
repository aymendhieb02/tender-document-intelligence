import numpy as np

from app.core.schemas import BoundingBox
from .schemas import EvidenceElement, GeometryGroup, PageGeometry


def transform_bbox(box: BoundingBox, matrix: np.ndarray) -> BoundingBox:
    """Axis-aligned envelope of all four transformed corners; source box survives."""
    corners = np.array([[box.x1, box.y1, 1], [box.x2, box.y1, 1],
                        [box.x2, box.y2, 1], [box.x1, box.y2, 1]], dtype=float)
    points = corners @ np.asarray(matrix).T
    return BoundingBox(x1=float(points[:, 0].min()), y1=float(points[:, 1].min()),
                       x2=float(points[:, 0].max()), y2=float(points[:, 1].max()))


def union_boxes(boxes: list[BoundingBox]) -> BoundingBox:
    return BoundingBox(x1=min(b.x1 for b in boxes), y1=min(b.y1 for b in boxes),
                       x2=max(b.x2 for b in boxes), y2=max(b.y2 for b in boxes))


def reading_order(elements: list[EvidenceElement]) -> list[EvidenceElement]:
    # Ties retain source order. Missing geometry is explicitly last, never inferred.
    return sorted(elements, key=lambda e: (e.page_number, e.bbox is None,
                  e.bbox.y1 if e.bbox else 0, e.bbox.x1 if e.bbox else 0, e.id))


def layout_evidence(elements: list[EvidenceElement]) -> PageGeometry:
    groups: list[list[EvidenceElement]] = []
    for element in elements:
        if element.bbox is None:
            continue
        target = None
        for group in reversed(groups):
            anchor = group[0].bbox
            overlap = min(anchor.y2, element.bbox.y2) - max(anchor.y1, element.bbox.y1)
            height = min(anchor.y2 - anchor.y1, element.bbox.y2 - element.bbox.y1)
            if height > 0 and overlap / height >= 0.5:
                target = group
                break
        if target is None:
            groups.append([element])
        else:
            target.append(element)
    rows = [GeometryGroup(id=f"row-{i}", bbox=union_boxes([e.bbox for e in group]),
                          element_ids=[e.id for e in sorted(group, key=lambda e: e.bbox.x1)])
            for i, group in enumerate(groups)]
    cells = [GeometryGroup(id=f"cell-{e.id}", bbox=e.bbox, element_ids=[e.id])
             for e in elements if e.bbox]
    aligned: list[list[tuple[int, EvidenceElement]]] = []
    for row_index, group in enumerate(groups):
        for element in group:
            tolerance = max(4.0, (element.page_width or 0) * 0.005)
            target = next((column for column in aligned
                           if abs(column[0][1].bbox.x1 - element.bbox.x1) <= tolerance), None)
            if target is None:
                aligned.append([(row_index, element)])
            else:
                target.append((row_index, element))
    columns = [GeometryGroup(id=f"column-{i}", bbox=union_boxes([e.bbox for _, e in column]),
                            element_ids=[e.id for _, e in column])
               for i, column in enumerate(aligned) if len({row for row, _ in column}) >= 2]
    # Repeated alignment is a candidate region, not a claim of a table or header.
    regions = [GeometryGroup(id="aligned-region-0", bbox=union_boxes([c.bbox for c in columns]),
                             element_ids=list(dict.fromkeys(eid for c in columns for eid in c.element_ids)))] if len(columns) >= 2 else []
    return PageGeometry(rows=rows, cells=cells, columns=columns, regions=regions)

# Tender Document Intelligence — Document Intelligence V1

This branch publishes the domain-neutral Document Intelligence producer and its public Contract 1.0. The producer handles multi-page PDFs and images, returns page-level evidence, and exposes native PDF or PaddleOCR/Tesseract provenance with rendered-page pixel boxes. It contains no CDC or BOQ extraction.

## Install

Use Python 3.11 on Windows for the verified dependency lock:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-document-intelligence-dev.txt
python -m pip check
$env:PADDLE_PDX_CACHE_HOME = Join-Path (Get-Location) '.cache/paddlex'
```

For exactly reproduced Windows packages, install `requirements-lock-win-py311.txt`. PaddleOCR downloads its PP-OCRv4 model weights on first run unless the verified weights are provisioned locally.

## Use

```python
from app.document_intelligence import DocumentProcessor

result = DocumentProcessor().process("document.pdf")
```

The result's public version is `document_intelligence_contract_version == "1.0"`. Version is out-of-band; the JSON shape is frozen by `tests/document_intelligence/fixtures/document_result_v1.schema.json`. See [producer setup and limits](docs/DOCUMENT_INTELLIGENCE.md) and the [consumer guide](docs/DOCUMENT_INTELLIGENCE_CONSUMER_GUIDE.md).

To write evidence JSON from the command line:

```powershell
python scripts/process_document.py document.pdf --output outputs/document.json
```

## Verification

```powershell
$env:RUN_REAL_OCR = '1'
python -m pytest tests/document_intelligence -q
python -m pytest -q
```

Without `RUN_REAL_OCR=1`, the real local-model test is skipped. See [the migration and compatibility reports](docs/DOCUMENT_INTELLIGENCE_COMPATIBILITY_REPORT.md) for verified versions, real OCR evidence, integration compatibility, and known failures.

The implementation reuses the verified OCR inference and preprocessing behavior. Generic processing selects a full-page policy; legacy region selection stays outside the generic path. The shared OCR adapters/configuration retain their historical names for compatibility.

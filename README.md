# Tender Document Intelligence — Backend Integration V1

[![Deterministic CI](https://github.com/aymendhieb02/tender-document-intelligence/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/aymendhieb02/tender-document-intelligence/actions/workflows/ci.yml)

This repository integrates Document Intelligence Contract 1.0, the deterministic CDC Analyzer V1, and the specialized `MALE_MUNICIPAL_MAINTENANCE_BOQ_V1` consumer. The producer returns physical-page evidence; CDC reconstructs tender structure and locates BOQ annexes; the specialized extractor parses supported BOQ evidence. The current integration checkout does not yet contain the historical FastAPI/invoice application shell.

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

The result's public version is `document_intelligence_contract_version == "1.0"`. Version is out-of-band; the JSON shape is frozen by `tests/document_intelligence/fixtures/document_result_v1.schema.json`. See [producer setup and limits](docs/DOCUMENT_INTELLIGENCE.md), the [consumer guide](docs/DOCUMENT_INTELLIGENCE_CONSUMER_GUIDE.md), the [CDC handoff contract](docs/CDC_BOQ_HANDOFF.md), and [integrated backend status](docs/INTEGRATED_BACKEND_V1.md).

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

The deterministic tests include a native-PDF DocumentProcessor → CDC → BOQ handoff test over the 30-page reference tender. This document has usable embedded text, so the test exercises the shared result without loading OCR models. The real local-model test is skipped unless `RUN_REAL_OCR=1`.

The implementation reuses the verified OCR inference and preprocessing behavior. Generic processing selects a full-page policy; legacy region selection stays outside the generic path. The shared OCR adapters/configuration retain their historical names for compatibility.

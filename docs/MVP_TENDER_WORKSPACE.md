# MVP Tender Workspace

## Routes

- `/` dashboard and workflow entry point
- `/cdc` general tender upload and analysis
- `/cdc/result/:id` compatibility route (results are currently held in the browser session)
- `/cdc/male` Ministry of Local Affairs upload and BOQ workflow
- `/cdc/male/result/:id` compatibility route
- `/invoice` and `/invoice/result/:id` remain on the existing invoice workflow

The Ministry workflow is labeled **Ministère des Affaires Locales** in the interface.

## Workspace sections

The CDC result workspace reuses the existing document tree, source viewer, evidence inspector, and BOQ table. It adds V2 summary and semantic requirements, a financial and deadlines view, and an Ask Tender panel. Missing values are shown as an em dash. Evidence links navigate to source pages where page metadata is available.

## API dependencies

Tender uploads use `POST /api/v2/cdc/analyze` or `POST /api/v2/cdc/male/analyze`, sending the selected file as multipart `file`. The UI consumes the V2 `document`, `tender_document`, and module envelope (`summary`, `requirements_intelligence`, `financial_deadline_intelligence`, `boq`, and `evidence`). Invoice API usage is unchanged.

## Ask Tender integration boundary

`askTender(documentId, question)` in `app/static/app/api.js` isolates the UI call to `POST /api/v2/cdc/ask`. It handles an unavailable endpoint (404/501), loading and errors, response text, and evidence references. The panel does not create answers locally; the endpoint contract should be aligned with Agent 16 before enabling server functionality.

## Known MVP limitations

- Upload results are not persisted by the current frontend, so the result routes display the re-upload notice after a page refresh.
- The Ask Tender backend is not part of this branch; it shows an unavailable state until integrated.
- V2 provides physical page counts but not rendered page geometry in its envelope. The existing viewer can display evidence metadata but may lack source-page imagery without richer page data.
- Summary identity fields can be absent; absent values remain blank markers rather than inferred labels.

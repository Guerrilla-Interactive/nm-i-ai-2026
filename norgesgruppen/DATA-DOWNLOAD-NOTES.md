# NorgesGruppen Data Download Notes

> Updated: 2026-03-19

## Download Source

The training data is available from the **Submit page** at:
- https://app.ainm.no/submit/norgesgruppen-data (requires Google login)

The page generates **GCS signed URLs** (1-hour expiry) for each file.

## GCS Bucket

- **Bucket:** `nmaichamps-participant-data`
- **Path prefix:** `norgesgruppen-data/`
- **Full base:** `gs://nmaichamps-participant-data/norgesgruppen-data/`

### Files

| File | Size | GCS Path |
|---|---|---|
| NM_NGD_coco_dataset.zip | ~864 MB | `norgesgruppen-data/NM_NGD_coco_dataset.zip` |
| NM_NGD_product_images.zip | ~60 MB | `norgesgruppen-data/NM_NGD_product_images.zip` |

## Signed URL Pattern

URLs are signed with GOOG4-RSA-SHA256 using service account:
- `1065880881946-compute@developer.gserviceaccount.com`
- Expiry: 3600 seconds (1 hour)
- Signature algorithm: GOOG4-RSA-SHA256

Pattern:
```
https://storage.googleapis.com/nmaichamps-participant-data/norgesgruppen-data/<FILENAME>
  ?X-Goog-Algorithm=GOOG4-RSA-SHA256
  &X-Goog-Credential=1065880881946-compute@developer.gserviceaccount.com/<DATE>/auto/storage/goog4_request
  &X-Goog-Date=<TIMESTAMP>
  &X-Goog-Expires=3600
  &X-Goog-SignedHeaders=host
  &X-Goog-Signature=<HEX_SIGNATURE>
```

## How to Re-download

If signed URLs expire:
1. Open https://app.ainm.no/submit/norgesgruppen-data in browser (logged in)
2. The page generates fresh signed URLs on load
3. Click the download links or extract URLs from page DOM

## Competition Info from Submit Page

- Team: "Frikk"
- 55 teams competing
- 0/3 daily submissions used
- 0/2 in-flight submissions

# Generation Proof (Provenance)

TrustRender can embed a cryptographic generation proof in the PDF metadata, recording which template, which data, which engine version, and when the document was generated.

This is not a digital signature (no PKI required). It is a generation proof: it answers "was this document produced from this data using this template?"

## Usage

**CLI:**

```
trustrender render invoice.j2.typ data.json -o out.pdf --provenance
```

**Python API:**

```python
pdf = render("invoice.j2.typ", data, output="out.pdf", provenance=True)
```

## Verification

```python
from trustrender.provenance import verify_provenance

result = verify_provenance(pdf_bytes, "invoice.j2.typ", original_data)
print(result.verified)  # True if template + data hashes match
print(result.reason)    # "match", "data_mismatch", "template_mismatch", "no_provenance"
```

## What is recorded

- Engine name and version
- SHA-256 hash of the template file
- SHA-256 hash of the canonical JSON data
- UTC timestamp
- Combined proof hash (SHA-256 of all above)

The proof is embedded in the PDF Info dictionary and survives normal PDF handling.

## Output fingerprinting

Every render records the SHA-256 of the final PDF bytes (after all post-processing including ZUGFeRD and provenance embedding) in the render trace. This creates an input-to-output hash chain: template hash + data hash + output hash.

## What provenance is NOT

- Not a digital signature
- Not immutable storage
- Not tamper-proof against PDF editing
- Not third-party verifiable without the original inputs
- Not replay-capable (timestamps differ)

Provenance works with all render modes — with or without ZUGFeRD, with or without contract validation.

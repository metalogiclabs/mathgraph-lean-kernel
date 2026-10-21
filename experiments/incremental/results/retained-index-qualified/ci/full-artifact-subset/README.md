# Partial full-artifact read: blocked

This was a **partial remote ZIP read attempt**, not a full archive download or SHA-256 verification.

The authenticated GitHub redirect-only probe succeeded. The inventory attempt then encountered the
explicit transport error `URLError (OSError): Tunnel connection failed: 403 Forbidden`.
The exact endpoint stage was not retained by the helper. **No ZIP body bytes were received.**
After the explicit denial, the probe stopped. No alternative host, proxy, network bypass, or whole
archive download was attempted.

Consequently, no central-directory inventory, individual entry, CRC, raw entry hash, complete-index
comparison, receipt, decision, or negative-control oracle was recovered from this full artifact.
This result adds no validation beyond the already available compact artifact and existing reviews.

The published full artifact is 4,210,910,584 bytes, ID `12075154855`, associated with successful run
`38961520032` and source `ef434eb2477fb64d7fd90fdf23f55bd0b35a0243`. Its published SHA-256 is
`2fcf3e723403d7c34c8e06604607ec0eb69f5a04f82940bb984db9b0840898f0`; that hash remains **unverified** here.

`blocker.json` preserves the sanitized observed failure. `transfer-log.json` records zero body bytes.
`remote_zip_subset.py` is the prepared stdlib range reader with explicit 206/Content-Range checks,
a 100 MB cumulative cap, a 30 MB selected compressed-entry cap, local/central header checks, and
per-entry size/CRC/raw-SHA checks. It never prints or persists credentials or signed URLs.
No runtime, repository source, or Git state was changed by this probe.

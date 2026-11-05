Capability: rp-file-store. Source: EPIC `toolkit-v1-foundation`; architecture `index.adoc` (N-6).

## ADDED Requirements

### Requirement: Files are kept byte for byte, per tenant, over S3

The file store SHALL put, get and delete a blob by a random key in the tenant's bucket over the S3
protocol, return exactly the bytes stored, and never create a missing bucket on put.

#### Scenario: round trip
- **WHEN** a scan is put and then read back from Garage
- **THEN** the bytes and their SHA-256 are identical

#### Scenario: a put after the tenant is gone
- **WHEN** a blob is put into the bucket of a deleted tenant
- **THEN** the put fails and no bucket is created

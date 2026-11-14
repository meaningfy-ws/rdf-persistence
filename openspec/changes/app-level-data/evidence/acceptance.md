# Acceptance of app-level-data

- **Verdict:** accepted by the developer on 2026-11-14, in the epic session: "i accept the demo,
  and feel free to close and archive the change. if it is not okay we will open a new change
  request from mwb2 project".
- **What was shown:** no live demo was run. The developer accepted on the delivery as reported: the
  spec scenarios run as `tests/feature/application_data.feature` on the fakes and as IT-01 to
  IT-04 (`tests/integration/tenancy/test_application_data.py`) on Fuseki, where the toy library's
  `Template` is stored, read back, replaced with a version conflict, kept out of a tenant's listing
  and left alone by the start-up sweep.
- **Follow-up:** a shortcoming found in use is raised as a new change, from the consumer project
  that meets it.

# Security review and remediation record

Reviewed 11 November 2026 against the local Velora workspace. This record covers
the application and maintenance tools inspected here; it is not a penetration
test or a guarantee that no vulnerability exists.

## Findings fixed in this review

The audit helper was written before private API configuration and the 3D studio
were added. It could open `.env` files while scanning and verified only the QR
library. `py/tools/security-audit.py` now:

- Inventories private environment, key and database paths without opening their
  contents. Tracked private files in reachable Git history are flagged by path;
  their blobs are never read. Only locations/categories of source findings are
  reported, never matching values or hashes of secret values.
- Skips developer credential directories and does not follow source-directory
  symbolic links or junctions outside the workspace. Dependency checks also
  refuse linked vendor files that escape the workspace.
- Checks all four locally bundled Three.js modules as well as the MFA QR library.
  Missing/modified module hashes cause a failing audit result.

The Three.js **0.180.0** tarball was retrieved from the official npm registry.
Its SHA-256 matched the previously recorded archive hash. All four local modules
matched the archive after the documented relative-import adjustment. Per-file
upstream and local hashes are now recorded in `json/vendor/three-source.json`.
No library version or runtime dependency was changed by this security review.

## Existing application controls verified

The focused backend review found no new confirmed authorization or request
boundary defect. Existing controls include server-side roles, immediate
department-folder permission checks, session ownership and revocation,
password/MFA reauthentication, explicit Origin and CSRF checks on mutations,
parameterized database queries, bounded request sizes/rates/worker counts,
private-file exclusions and restrictive browser response policies.

Protected HTML is authorized before delivery; anonymous users are redirected to
sign-in and customer accounts cannot open admin HTML. Vendor JavaScript has an
explicit allowlist. Finance and HR rules remain enforced by the backend rather
than by hidden interface controls. Two-factor enrollment remains optional until
the account owner completes setup.

The project is now a Git checkout and private `.env.local` configuration exists.
The earlier audit's claims that no checkout or environment file existed are
historical and no longer describe the workspace. Credential, account/database,
MFA-key and private-document contents were not opened for this pass.

## Runtime and dependencies

The project-local runtime used for verification reports Python **3.15.2**,
OpenSSL **3.5.9** and SQLite **3.53.4**. The application backend uses Python's
standard library. Offline image preparation uses Pillow separately; development
tools are not automatically runtime dependencies. The runtime lock and bundled
vendor source records identify the selected versions. This review does not
claim that every pinned version is the latest upstream release.

## Verification

All verification accounts, databases and secrets used by tests were disposable.

| Check | Result |
| --- | --- |
| Adversarial request/authorization hardening | 20 tests passed |
| MFA, session and account security | 23 tests passed |
| Audit-tool private-file/Git/vendor fixtures | 3 passed; symbolic-link fixture skipped because Windows did not permit link creation |
| Scanner synthetic detection/redaction self-test | Passed |
| Bundled Three.js archive and four module comparison | Matched recorded archive and documented local adjustment |

The redacted workspace/history scan covered 622 working-tree text files and 793
reachable Git text blobs. Its only pattern match in each scope is the deliberate
`user:pass` URL rejection fixture in `py/tests/test_seo_server.py:174`, not an actual
credential. No private-file path was found in the scanned history, and no required
ignore rule was missing. The report is recorded separately in
`json/reports/security-audit-2026-11-11.json`. Deliberately skipped private files are
listed as unscanned, never counted as evidence that their contents are clean.
The helper does not contact vulnerability databases, inspect remote-only or
unreachable Git history, or establish whether a provider credential is revoked.

Run from the repository root:

```powershell
.runtime\python-3.15.2\python.exe -I py/tools/security-audit.py --self-test
.runtime\python-3.15.2\python.exe -I py/tools/security-audit.py --json
.runtime\python-3.15.2\python.exe -I -m unittest discover -s py/tests -p test_security_audit_tool.py
.runtime\python-3.15.2\python.exe -I -m unittest discover -s py/tests -p test_hardening_server.py
.runtime\python-3.15.2\python.exe -I -m unittest discover -s py/tests -p test_security_server.py
```

## Public-hosting work remains

Velora is still served locally by Python's HTTP server. The [Python maintainers
do not recommend `http.server` for production](https://docs.python.org/3/library/http.server.html).
Public hosting therefore still needs a maintained production serving stack,
HTTPS, an explicitly reviewed proxy/host configuration, restricted durable
storage/backups and operational monitoring. The existing `--secure-cookies`
option adds cookie/header attributes; it does not install TLS or trust forwarded
headers automatically. No public hosting configuration was changed here.

Email verification and email-based password recovery are not implemented. Those
flows need a real configured email service and token delivery before they can be
presented as working account features. Credentials should remain in private
server configuration, consistent with the [OWASP secrets-management
guidance](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html).

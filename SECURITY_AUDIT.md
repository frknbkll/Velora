# Security audit record

Reviewed 1 November 2026 against the local Velora workspace. This is an engineering audit and remediation record, not a guarantee that no vulnerability exists. Network infrastructure, external accounts, operating-system security and future integrations are outside the verified application scope.

## Secrets, environment and Git

- No `.env` file or environment variable named like an API key, token, password or credential was found in the initial project inventory. Environment **values were not disclosed**. The inherited `DEBUG` variable has a non-boolean value; the application does not read that variable or enable a framework debugger from it.
- `.velora/security.key` is an expected private MFA master key, not a browser API key. Its presence and size were checked without opening or hashing it. No real database contents were read for this audit.
- Git is installed, but `git rev-parse --show-toplevel` confirms this workspace is not in a Git checkout. Working files can be scanned, but no local commit history exists to inspect; this is not evidence that an external or deleted repository is free of secrets.
- The reusable `tools/security-audit.py` scanner reports categories and locations only. It scans project text and small direct `tmp/` text artefacts, skips the private database/key, and lists skipped files. When run in a Git checkout it also scans reachable text history and flags private file paths without opening private binary contents. Pattern scanning cannot establish provider-revocation status or prove that every possible secret is absent.

If a real credential is ever found in a public bundle or Git history, remove it from browser code, revoke/rotate it at the provider and check its use history. Deleting its visible line alone does not invalidate the exposed credential. Keep future service secrets in private server configuration; a browser cannot conceal a secret it receives.

## Dependency inventory and update evidence

The app uses Python's standard library; its entry files import no third-party Python package. There is no Node/npm or Python package manifest and no project package set to uninstall. Global developer tools were deliberately left outside this app's dependency scope.

The initial interpreter was Python **3.14.8**. The official [Python 3.14.10 release page](https://www.python.org/downloads/release/python-31410/) identifies the 25 October 2026 release as a security update. A project-local **Python 3.14.10** runtime is now installed under `.runtime/python-3.14.10/`; the official Windows archive's SHA-256 matches `runtime-lock.json`, and its executables have valid Python Software Foundation Authenticode signatures. `Start-Velora.cmd` selects that runtime, launches isolated mode, and disables application debug inheritance. The installed runtime reports isolated mode and environment isolation. No unrelated global Python package was replaced.

The official runtime bundles **OpenSSL 3.5.9** and **SQLite 3.50.4**. OpenSSL's [supported-download table](https://openssl-library.org/source/) lists 3.5.9 as the current 3.5 LTS patch. SQLite 3.50.4 is older than the current SQLite release: its [maintainer CVE table](https://sqlite.org/cves.html) lists issues fixed in later versions that require arbitrary SQL/FTS5 with defensive mode disabled, or optional extensions. Velora exposes no arbitrary-SQL or database-upload feature. Keep the bundled-library version visible in maintenance review and use defensive database settings; do not claim that every bundled component is the latest upstream version or replace individual runtime DLLs without a tested, trusted distribution.

The only bundled JavaScript library is **Nayuki QR Code Generator 1.8.0**, used locally to create MFA QR codes. The local bytes match `assets/vendor/qrcodegen-source.json` and its recorded official release hash. The upstream [release list](https://github.com/nayuki/QR-Code-generator/releases) still identifies 1.8.0 as latest, and its [maintainer advisory page](https://github.com/nayuki/QR-Code-generator/security/advisories) currently shows no published advisories. That observation is not a guarantee that no undisclosed vulnerability exists. No network request, code-evaluation or telemetry primitive was found in the bundled library's source.

Fonts are delivered locally with their SIL Open Font License notices and source/hash records under `assets/fonts/`. There are no analytics, advertising, payment, CAPTCHA or remote-font SDKs enabled in page delivery. Their creation tools are not runtime website dependencies.

## Application control verification

The root audit and parallel code reviews cover server-side admin authorization, account ownership, sessions/MFA, request validation, DOM output handling, CSRF/origin checks, CORS, rate limits, HTTP security headers, static-file boundaries and database/private-directory permissions. Confirmed findings, fixes and exact test results will be added after those reviews finish; this inventory does not pre-assert their outcome.

Private Windows storage ACL metadata was reviewed: there are no broad Everyone, Users or Authenticated Users grants on the reviewed database/key storage; access is limited to the owner, SYSTEM, Administrators and the managed execution identity. This is filesystem access control, not database-at-rest encryption. Device/disk access by an authorized administrator remains outside that protection.

## Reproducible checks

```powershell
.runtime\python-3.14.10\python.exe -I tools/security-audit.py --self-test
.runtime\python-3.14.10\python.exe -I tools/security-audit.py
.runtime\python-3.14.10\python.exe -I tools/security-audit.py --json
.runtime\python-3.14.10\python.exe -I -m unittest discover -s tests -p "test_*_server.py"
```

The scanner does not contact vulnerability databases or change files. Browser/API adversarial tests must continue to use temporary accounts and databases rather than the owner's data. The scanner's own synthetic-fixture checks passed, and the initial workspace scan found zero matching secret patterns in 111 text files. Later application edits should be rescanned before the final audit is closed.

## Deployment boundary

This application remains a local development server. Python explicitly states that [`http.server` is not recommended for production](https://docs.python.org/3/library/http.server.html). Public deployment requires a production serving stack, HTTPS, private durable storage, reviewed proxy/host configuration, restricted backups and operational monitoring. A Secure-cookie flag does not itself provide TLS or configure a trusted reverse proxy. The lack of a public deployment prevents a meaningful external perimeter, TLS or hosted-provider audit in this session.

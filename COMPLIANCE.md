# Privacy and consumer-information implementation

Reviewed 4 November 2026. This records the implementation and outstanding operator decisions. It is not a certification of legal compliance.

## Current service and region

The site is a local fashion showcase with real account features, public account-holder reviews and private customer-support chat. There is no checkout, payment processing, order fulfillment or mailing service. Reviews are not verified purchases. The Netherlands/EU references below are a working starting point based on the project context; the operator's actual establishment and target markets still need confirmation.

## Implemented website controls

| Request | Implementation / evidence |
| --- | --- |
| Privacy notice | `privacy.html`: data, purposes, account access, retention, rights and limitations |
| Terms | `terms.html`: free showcase/account scope and distinct account acceptance |
| Refund policy | `refund-policy.html`: no existing orders or payments; general EU reference without inventing a returns operation |
| Cookie policy and choice | `cookie-policy.html` and shared privacy controls; optional saved-shopping storage starts off |
| Form consent | Account terms and 16+ confirmation are required; no inferred marketing permission |
| Minimal collection | First name, last name, city, country, email, password hash and acceptance records; no birth date, street address, identity document or payment field |
| Third-party audit | `THIRD_PARTY_AUDIT.md`: local assets/library; no enabled tracking SDK |
| Fair presentation | No manufactured customer scores or signup success; showcase pricing and AI previews identified |
| Account-holder reviews | `reviews.html`: one editable/deletable review per signed-in account, star rating, optional photo, account name by default or anonymous public display; no verified-purchase label |
| Customer support | Private guest/account conversations and staff inbox; persistent messages and read positions; availability derived from staff presence; no fabricated replies or promised response times |
| Pricing | Bag subtotal is explicitly a preview; no checkout or subscription charges |
| Accessibility | Shared focus/contrast/keyboard and image-text improvements; verify actual pages and content after edits |
| Operator details | `business-details.html`: available details only; missing values remain clearly marked |
| Children | Accounts restricted to age 16+ as site policy, using a confirmation instead of collecting birth dates |
| Unsubscribe | `unsubscribe.html` explains that no mailing list is active. Do not collect subscribers until a working consent/unsubscribe service exists |
| Image rights | `IMAGE_RIGHTS.md` and `image-rights-register.json`: provenance evidence and unresolved rights separated |
| Data deletion | Authenticated account deletion with password and MFA where enabled; reviews, review-photo records and account-linked support conversations cascade from the account; support conversations can also be deleted from chat; final-admin safeguard; browser data can be cleared separately |

## Operator information still required

Enter the actual registered legal name, establishment country, registration number (KvK where applicable), VAT number where applicable, physical/business address, customer-service email, direct contact method, privacy contact and return address. No fictional employee email is a substitute for an accountable operator. The admin business-details editor can publish the confirmed supported fields.

For Dutch businesses, the official [business identity guidance](https://business.gov.nl/regulations/rules-business-correspondence/) explains website disclosures. Actual applicability must be checked against the operator's legal form and country.

## Before public collection or sales

1. Supply working operator and privacy contacts and verify registration details.
2. Set a defined backup retention schedule, remove expired private backups, and make deletion effective in retained/restored copies. There is no automatic backup expiry in this installation. Keep a record of deletion requests without reintroducing unnecessary personal data.
3. Identify any host/email/payment processor, its processing agreement, storage region, logging retention and transfer safeguards before connecting it. Update the notice to match the actual deployment.
4. Verify original image rights, permitted modifications and releases. AI edits do not clear the source photograph's rights. The owner has confirmed that stock licences/source links are unavailable; no stock licence has been purchased or certified.
5. Before offering a purchase: verify garment details and stock, publish seller/complaint/return details, set total tax-inclusive pricing and delivery charges, and provide the applicable withdrawal procedure and form. Check the online withdrawal-function requirements applicable to the actual launch date and service. There is currently no purchase flow to cancel.
6. If email marketing is introduced, implement separate unchecked permission, proof of that permission and a working one-click unsubscribe method without account sign-in before taking addresses. Account terms acceptance is not marketing consent.

The current [Dutch online-sales guidance](https://business.gov.nl/regulations/long-distance-sales-and-purchases/) covers price disclosure, genuine reviews, availability statements and optional choices. [EU withdrawal guidance](https://europa.eu/youreurope/citizens/consumers/shopping/returns/index_en.htm) describes the usual 14-day distance-sale framework and exceptions.

## Validation and maintenance

API checks run against disposable databases: `python -m unittest discover -s tests -p "test_*_server.py"`.
Chrome checks: `python tests/run-privacy-browser.py`, `python tests/run-account-privacy-browser.py`, `python tests/run-business-browser.py`, plus the existing account and catalog browser runners.

Text contrast corrections use the [W3C WCAG 2.2 contrast guidance](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html): 4.5:1 for ordinary text and 3:1 for large text. The browser audit checks solid-background text, alternative-text attributes, control names, form labels, skip targets, keyboard preferences and page overflow. Photo/gradient backgrounds receive a separate visual review. This work does not certify full WCAG conformance or legal compliance; repeat the relevant checks when content, branding or third-party services change.

Restart the account server through `Start-Velora.cmd` after backend updates. Add the real operator information in **Admin → Business details**; saving publishes those fields on the business/contact pages. Existing customer accounts are not assigned invented historical age or terms confirmations. New accounts record the actual confirmations supplied during registration.

## Privacy decisions and evidence

Account service data is used to provide the requested account; security activity supports protection of that service. Optional browser persistence is a separate choice. Keep this division clear rather than asking visitors to agree to all processing at once.

Reviews are optional public submissions associated with their author's account. Public responses show the current account name unless the author chooses anonymous display; they omit account identifiers and email addresses. Anonymous display is not anonymous storage, and text or visible photo content can still identify someone. Review photos use random identifiers, have supported embedded location/descriptive metadata removed, and are stored as protected database records rather than publicly accessible unbound uploads. Each account may have one unattached upload; it expires after 24 hours and is cleaned on startup or subsequent review/upload activity. Deleting a review deletes its associated photo; deleting an account cascades review and photo records. The existing manual-backup limitation continues to apply.

Support chat stores private message text, sender labels, timestamps and read positions. Account names come from the signed-in account; guest names are optional, with no email required. Guest chat starts only when requested and uses the HttpOnly, SameSite=Strict `velora_support` cookie scoped to `/api/support`, with a seven-day lifetime. Guest records expire after 30 days without activity and are cleaned on startup and later support session/message activity. Signed-in conversations remain until the customer deletes the conversation or account. Guest histories are not merged into accounts. Only authorized owner/manager staff can use the support inbox. The online indicator uses a 45-second staff-presence lease; it does not promise immediate replies. Messages remain in this service rather than being emailed or sent to a third-party chat/AI provider.

Once chat is first requested, session storage key `velora-support-panel` remembers an open/closed UI flag per tab so chat can reconnect across navigation. It contains no customer text, name or credentials. Browsing before first opening chat does not create this support session.

The 16+ registration rule is a product choice, not a universal legal-age assertion. The Dutch regulator's [child-consent guidance](https://autoriteitpersoonsgegevens.nl/themas/basis-avg/avg-algemeen/grondslag-toestemming) describes the additional requirements when consent is used for children's information. There is no verified parental-consent workflow in this implementation.

The AP explains that retention must be justified and communicated in its [retention guidance](https://autoriteitpersoonsgegevens.nl/nl/over-privacy/persoonsgegevens/bewaren-van-persoonsgegevens). The privacy page identifies the existing manual-backup limitation rather than claiming deletion reaches every archived copy.

If optional tools are added, revisit the AP's [tracking-cookie guidance](https://autoriteitpersoonsgegevens.nl/themas/internet-slimme-apparaten/cookies/trackingcookies) and ensure refusing/withdrawing stays as easy as accepting. Do not enable a tracking SDK merely because a preference object exists.

Garment composition, sustainability, origin and performance require evidence before factual claims are made. The official [sustainability-claims guidance](https://business.gov.nl/regulations/sustainability-claims-rules/) is relevant if such claims are introduced; the current showcase does not claim certifications.

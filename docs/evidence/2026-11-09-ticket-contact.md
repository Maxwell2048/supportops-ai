# Ticket contact verification

On 2026-11-09, the backend suite passed 315 tests with zero skips against PostgreSQL. New integration cases verify optional phone formatting, idempotent creation, requester and agent object restrictions, rejection of a forged contact email, and exclusion of phone numbers from ticket audit changes. An authorized manager reads the requester's account email and supplied phone.

The full Chromium suite passed 24 desktop and narrow cases, including a requester creating a ticket with a synthetic phone and an authorized manager seeing the contact details. The development migration from 0008 to 0009 preserved previous row fingerprints across 14 tables. Existing tickets retain a null phone number.

The phone field is optional to preserve compatibility with existing tickets and API clients. Email is taken from the authenticated requester account. This feature does not verify phone ownership or deliver notifications.

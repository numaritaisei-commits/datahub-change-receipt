# Security

Do not commit DataHub tokens, cookies, production query text, personal data, or `.env` files.
Use a least-privilege read-only DataHub token for collection. Metadata write-back is optional
and requires explicit approval; use a separate narrowly scoped credential when testing it.

Report vulnerabilities privately to the repository owner rather than publishing secrets in
an issue. Replace any exposed credential at its official issuer immediately.

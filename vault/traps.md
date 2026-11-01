# Traps

Found by auditing `data/raw` before writing any agent code. Every item must end up with a rule in the code and a case in `evals/`. The Eval column names the case in `evals/cases.yaml`; a test fails if a trap has none.

## Contradictions in the policy manual

| ID | Finding | Handling | Eval |
|---|---|---|---|
| T01 | WhatsApp is (67) 3341-4444 on the cover and §1.2, (67) 3321-4500 in §7 | Give the store phone from §1.2, flag the conflict for the team | `store-phone` |
| T02 | E-mail appears as `emporiodamusica` and `empóriodamusica` | Use the ASCII form, document it | `store-email` |
| T03 | Card minimum installment is R$ 100 in the §3 table, tiered in §3.1 | §3.1 is the specific rule and wins; computed in code | `installments-follow-the-tiers` |
| T04 | §3.1 says up to 3x has no minimum "exceto abaixo de R$ 50,00" | Read as a minimum R$ 50 installment; assumption documented | `installments-follow-the-tiers` |

## Catalog

| ID | Finding | Handling | Eval |
|---|---|---|---|
| T05 | Manual sells winds and orchestral strings, categories 6, 7 and 8 have 0 products | Never "we don't sell that": no items in the system right now, hand off to the team | `empty-category-is-not-we-dont-sell` |
| T06 | Manual claims 300+ instruments, the CSV has 65 | Answer only from the CSV, state it as an assumption | `catalog-size-does-not-parrot-the-manual` |
| T07 | 14 acoustic guitars up to R$ 1,000 on file, only 12 can be sold (GF-3D has 0 stock, SN-7C is discontinued) | Availability filter lives in the query, not in the prompt | `brief-acoustic-under-1000` |
| T08 | Ibanez Bass 2X is discontinued with 13 in stock | Status beats stock | `discontinued-offers-equivalents` |
| T09 | Kala KA-ABP-CTG is `coming_soon` with 2 in stock and orders already delivered | Not for sale; report as coming soon; order history stays readable | `coming-soon-is-not-for-sale` |

## Promotions and prices

| ID | Finding | Handling | Eval |
|---|---|---|---|
| T10 | Only 4 of 25 promotions are active (products 90, 94, 121, 127) | `is_active` is the only source | `active-promotions` |
| T11 | Takamine GD20 had a 12% promotion, now inactive; price is R$ 2,199 | Report the current price; never promise the expired discount (§7.3) | `brief-price`, `customer-claims-expired-promotion` |
| T12 | GF-3D has inactive 18% and 40% promotions and no stock | Unavailable; suggest similar items | `out-of-stock-with-expired-promotion` |
| T13 | PIX 5% does not apply over promotional prices (§6.2) | Computed in code | `pix-does-not-stack-on-promotion` |
| T14 | Promotional prices must show original price and percentage (§6.2) | The price block renders all three | `promotional-price-shows-original-and-percent` |

## Orders

| ID | Finding | Handling | Eval |
|---|---|---|---|
| T15 | Totals of orders 3 and 20 do not match the sum of their items | Report the stored total, never recompute it | `stored-total-is-reported` |
| T16 | All PIX orders are at list price, without the 5% discount | Not explained by the data; if asked, hand off | `pix-discount-question-goes-to-team` |
| T17 | Orders 9, 16 and 18 have installments below the §3.1 minimum | Historic data, the agent does not audit it to the customer | `order-history-is-not-audited-to-the-customer` |

## Identity and privacy

| ID | Finding | Handling | Eval |
|---|---|---|---|
| T18 | Customers 11 and 43 share an e-mail | E-mail alone cannot prove identity | `email-is-not-identity` |
| T19 | Order lookup without verification exposes personal data (§9, LGPD) | Order number plus phone match, enforced in code | `brief-regret-asks-before-answering`, `order-without-phone-is-not-looked-up`, `order-with-wrong-phone-reveals-nothing`, `email-is-not-identity` |
| T20 | Asking for a customer's data, or the customer list | No tool exposes it | `asks-for-another-customers-data`, `injection-asks-for-data` |

## Policy application

| ID | Finding | Handling | Eval |
|---|---|---|---|
| T21 | Regret right (§4.1) counts from receipt, and only online; there is no delivery date or sales channel in the data | Ask the channel; use the data available and say what is unknown | `brief-regret-asks-before-answering`, `regret-online-past-window`, `regret-within-window-with-reported-date`, `regret-store-purchase-has-no-such-right` |
| T22 | No rule for cancelling an order that has not shipped | Hand off instead of inventing | `cancel-unshipped-goes-to-team` |
| T23 | §7.1 says to suggest partner stores, no partner is listed | Do not invent one | `accessories-without-invented-partners` |
| T24 | Defect exchange 30 days, legal warranty 90 days | Both are cited, they answer different questions | `defect-after-exchange-window-is-warranty` |
| T25 | Outside business hours the assistant must state when service returns (§7.1) | Clock tool, computed in code | `closed-store-says-when-it-returns` |
| T26 | The manual is internal, restricted use | Answers cite it, no tool dumps it whole | `refuses-to-dump-the-manual` |

## Adversarial

| ID | Finding | Handling | Eval |
|---|---|---|---|
| T27 | Prompt injection and persona breaking | Tools hold the guarantees, so a jailbroken prompt still cannot reach data | `injection-changes-a-price`, `injection-asks-for-data` |
| T28 | Customer states a false price or promotion | The system's value wins | `customer-claims-a-false-price` |

# New-York Shipping and Commercial List — transcription methodology

**This is the single running document for the project.** Everything about the
source, the transcription, the accuracy, and the identifier scheme belongs here;
add to it rather than starting a second note. `README.md` is a pointer only.

Last updated August 2026.

Covers how the price data in this directory was obtained, what the source actually
contains, how accurate the result is, and how it joins to the two existing
security databases.

---

## 1. Source and access

The **New-York Shipping and Commercial List** ran twice weekly from February 1815
into the 1890s under seven successive mastheads (*General Shipping & Commercial
List*, *Turner's New-York Shipping and Commercial List*, *Shipping & Commercial
List and New-York Price Current*, and so on). It is one continuous publication.

**FRASER**, the Federal Reserve Bank of St. Louis digital library, holds
**3,673 issues, 1815–1895**, at roughly 100–105 per year through 1849, thinning
sharply thereafter (104 issues in the 1850s, 2 in the 1890s). Rights are
`rightsstatements.org/vocab/NoC-US` — no copyright, United States. Cite the
Federal Reserve Bank of St. Louis.

**It is not on HathiTrust** (checked against their Bib API for every LCCN of the
title's variants) and **not in Chronicling America** (no digitised issues; the
Library of Congress holds catalogue and microfilm records only).

Access notes, which matter for anyone repeating this:

- `fraser.stlouisfed.org` **HTML pages sit behind Akamai bot protection**. Plain
  `curl`/`requests` complete the TLS handshake, open the HTTP/2 stream, then hang.
  The issue index therefore has to come from a real browser (`fraser_scl.py index`
  drives Playwright).
- The **IIIF endpoints are not protected** and work over plain HTTP:
  `iiif.slf.digirati.io/presentation/item/{id}` for the manifest,
  `dlcs.slf.digirati.io/iiif-img/2/3/{id}_0_{page:04d}/{region}/{size}/0/default.jpg`
  for images. IIIF Image API **3.0**: size must be `max`, not `full`.
- `/files/` paths are also unprotected, and predictable from the date:
  `/files/docs/publications/scl/scl_YYYYMMDD.pdf` and
  `/files/text/publications/scl/scl_YYYYMMDD.txt`.
- **FRASER's own OCR text layer is unusable** for these tables. The 1832 file
  reads `HOPS:`, `gpella`, `trar:::`. It was not used.

Scan resolution varies **4.2×** across the run — 9.8 MP in 1815, 14.7 in 1822,
31.4 in 1836, 41.2 in 1848 — so FRASER evidently filmed different physical
volumes for different year ranges. Higher resolution did **not** improve
transcription accuracy (§4).

---

## 2. What the source actually contains

The securities table moves page and changes format across the period. There is no
single extractor.

| Era | Pages/issue | Page | Heading | Content |
|---|---|---|---|---|
| 1817 | 2–4 | **p1** | `PRICE OF STOCKS` | single price column |
| 1822 | 3–6 | **last** | `NEW-YORK STOCKS, &c.`<br>"Corrected yesterday by the New-York Stock and Exchange Board" | **bid and ask** |
| 1839 | 4 | p2 | `Corrected yesterday by Lewis Forman, Stock and Exchange Broker, 47½ Wall-street` | bid/ask, ~100 listed of which <half priced |
| 1848 | 4 | **p2** | `STOCKS — Sales at the Stock and Exchange Board` | **actual transactions with volume** |

In the quotation eras the table is a **standing list**: US government loans (Six
per cents Old and Deferred, Louisiana, War Loans 1812–15, Sevens, Threes, Treasury
Notes), then state, canal and city stocks, then BANKS, then INSURANCE COMPANIES
(split MARINE / FIRE from the 1820s). A cell may carry a word instead of a number
— `none`, `sales`, `par`, `nominal`, `n.s.` — and those are recorded as notes, not
silently dropped. In 1817 a single column sometimes holds a range printed as
`99 a 99 1/2`.

The 1848 table is a different object. Each line is an actual sale, grouped under a
weekday heading:

    SATURDAY, February 26.
    $65,000 U. S. Treasury Notes (B. 3 days) .... 101 1/4
    $11,000 Reading R. R. Bonds ................. 63 @ 63 1/2
       850 do.  Morris Canal Co. ............... 10 1/4 @ 11
      2400 do.  Harlem R. R. .................... 43 1/2 @ 43 1/2

so the fields are session date, quantity, unit (**dollars** where the figure is a
par amount, **shares** where it is a share count), security, `price_low` /
`price_high` — a `@` range means the day's sales ran between those prices — and a
qualifier such as `B. 3 days` (buyer's option, three days) or `cash`. Here too
`do.` is ditto: it repeats the *quantity unit* of the line above, not the security
name. By 1848 the securities themselves have changed: railroads, canals, trust
companies and state bonds rather than the banks and marine insurers of the 1810s–20s.

Three consequences:

1. **Only the quotation eras give a bid-ask spread.** 1848 gives traded prices and
   volumes but no spread — the reverse of 1822.
2. **The 1839 quotes are one named broker's**, not the Board's official list. That
   is a change in what the numbers are, not merely who printed them.
3. Some issues (e.g. 29 April 1817) **typeset the table sideways** across the foot
   of the page. Those transcribe far worse (§4).

### Bid, ask, and "final"

The 1822 columns are `off'd` and `ask'd`. Offered runs consistently below asked
(War Loans 1814 104¼ / 105¼; Seven per cents 104¾ / 105; Manhattan 121 / 123), so

    off'd = bid      ask'd = ask      neither is a transaction price

A row annotated **"sales"** marks that a trade actually occurred — the nearest
thing to a closing price in the quotation era. This reading is confirmed
independently by Jack Wilson's 2000 memo (§6), which states that *"'s' following
a price means that SALES were executed at that price."*

**Construction rule** (as used for the existing ICF database): final price = the
transaction price where printed, otherwise the **average of bid and ask**; where a
month has no quotation at all, the ICF Final Data interpolate the average of the
previous and next observed prices.

Capturing **both** columns is therefore mandatory. An early version of the
extractor cropped too narrowly, returned only `off'd`, and would have biased every
mid-quote downward.

### Typographic conventions (essential to correct transcription)

- **"do." means ditto.** It repeats wording from the row above, positionally.
  `U. S. Six per cent. Old and Deferred` / `do. War Loans, 1812` / `do. do. 1813`
  is three securities, the last being *U.S. Six per cent, War Loans, 1813*.
- **A leading horizontal rule is also a ditto, and its LENGTH says how much of the
  name above is repeated.** Under `N. Y. State Sixes`, a rule spanning "N. Y."
  gives *N.Y. Canal Sixes*; a longer rule spanning "N. Y. Canal" gives *N.Y. Canal
  Fives*. Under `City Loan Sixes`, a rule spanning "City Loan" gives *City Loan
  Old Fives*.
- **A brace joining several rows to one price** means that price applies to every
  row it spans — e.g. Old and Deferred, Louisiana and War Loans all at 99¾ in
  April 1817.
- **Section headings carry down.** `BANKS, United States` begins the banks;
  `INSURANCE COMPANIES` then `MARINE,` and `FIRE,` begin the insurers. The list
  ends at the specie and exchange entries (Doubloons, Spanish Dollars, Bills on
  London), which are not securities.

The headings are not decoration. **Six or seven names exist in two sections at
once** — Mechanics, Merchants, Manhattan, Franklin, Globe, Union, Phenix each
denote both a bank and an insurance company. Without the governing heading any
panel built from this source silently splices two different firms. An earlier run
did exactly that, tagging Merchants' Bank as fire insurance.

---

## 3. Extraction procedure

Per issue:

1. **Locate** — a cheap low-resolution pass identifies which page holds the table,
   returns its bounding box as page fractions, and reports rotation (0/90/270).
   Pages are tried in likelihood order for the era.
2. **Crop** — the table is cut out, rotated upright, and resized. This matters:
   the vision encoder works at ~1568 px on the long edge, so cropping spends that
   budget on the table instead of on shipping notices. A crop wider than ~1.6:1 is
   split into near-square tiles with overlap, because resizing a wide strip by its
   long edge destroys vertical detail.
3. **Transcribe** — three independent passes at low reasoning effort, streaming,
   with a JSON schema. Prices are kept **as printed** ("104 1/4"), never converted
   during transcription.
4. **Vote** — modal value per cell. Cells where the passes disagree are flagged and
   their alternatives retained.

Settings that were tested and rejected: **five votes instead of three** (identical
23% → 22% flag rate for 1.6× the cost); **higher-resolution source years** (1839 at
39 MP scored *worse* than 1822 at 14.7 MP); **slicing the table into three
overlapping vertical bands** (did not fix the fractions and duplicated rows in the
overlap regions). Tiling is retained only for the wide sideways tables of §2, where
it addresses geometry rather than legibility.

---

## 4. Accuracy — measured, not assumed

| Test | Result |
|---|---|
| Two runs, same image, 36 rows | 29 identical, **7 differing (19%)** |
| Cells unanimous in *both* a 3-vote and a 5-vote run | **5% still disagree** |
| Agreement on the whole number | **93–95%** |
| Agreement within 1 point | **95%** |
| **Bid-ask spread identical across runs** | **78%, median difference 0.000** |
| Flagged share of priced cells (1822 full year) | **29%** |

**Unanimity is not evidence of correctness.** The model misreads fractions
*consistently within a run*, so voting detects disagreement but not confident
error. 56% of all disagreements are ≤ 0.5 point — a misread fraction.

The remainder are worse than fraction slips: some are **row misalignments against
the price columns** in a dot-leader table. Manhattan was read once as 104 / 106½
and once as 121 / 123 on the same image (the latter correct), and Canal Sixes
returned 105¼, 105⅛ and 105⅝ on three separate attempts. Any row where the passes
disagree needs adjudication against the image, not a tie-break rule.

Hand-checking by WNG of two 1817 issues (59 cells) gave the only external
measure: **12 cells changed (20%)**, of which 7 were flagged red and **5 were not**.
That is ~88% accuracy on cells the OCR was confident about — but split by page
type it is **95% on the upright 28 March page and 54% on the sideways 29 April
page**. The two are different problems and should not be averaged.

**Practical position: prices are reliable to about ±½ point, not to the fraction.**
Spreads survive because both numbers are read from one image and fraction errors
partly cancel in the difference. High-frequency price *changes* do not survive:
change autocorrelations near −0.5 for several securities indicate measurement
error dominating.

**The OCR output is a drafting aid, not finished data.** It is issued as
pre-filled hand-entry workbooks (§7), not as a series.

---

## 5. Identifiers and the crosswalk

### The three systems

| System | Identifier | Coverage |
|---|---|---|
| **ICF Old NYSE** | `ID2020nnnn` + `Unique.number` | 671 securities, 1815–1925 |
| **SWW** (ICPSR 4053 DS0007) | `F-1500` etc. | 1,997 securities, 1790–1860 |
| **SCL** (this project) | security name + section | 1822 and gap months |

**SWW format**, reverse-engineered from the codebook and data:

- dates `YYYY.MMDD` — `1812.1205` = 5 December 1812
- **two columns per security: `CODE` = bid, `CODEa` = ask.** Verified empirically:
  across 33,374 paired observations the `a` column is greater 95.6% of the time,
  equal 4.1%, smaller 0.3%
- NY equities quoted as percentage of par
- class prefixes: `F` banks, `I` insurance, `S` US states, `C` cities,
  `T` transportation, `B` corporate bonds, `M` miscellaneous

The **prefix is what disambiguates the colliding names**: Manhattan Company
`F-1390` vs Manhattan Fire `I-0980`; Mechanics `F-1500` vs Mechanics `I-1060`.
Our section heading maps directly onto their prefix, which is why reading the
headings correctly (§2) is a prerequisite for correct identification.

### US federal debt — our own codes

**SWW's New York set carries no federal debt.** Its `S-` prefix is US *states*
(Alabama, Indiana, Maryland); `C-` is cities. Yet the federal loans are the most
heavily quoted instruments of the 1810s–20s.

We therefore assign a **`U-` prefix**, four digits spaced by 10 in the SWW manner,
ordered by statute date, each entry tied to the loan as described in the ICF
project's own *Description of Loans*, which was matched against **Bayley, *The
National Loans of the United States from July 4, 1776 to June 30, 1880* (1882)**.
The codes rest on the statutory record, not on masthead wording.

Two deliberate choices:

- **The 1790 funding-act debt is split**: `U-0010` sixes, `U-0020` **deferred**
  sixes, `U-0040` threes — economically distinct instruments, the deferred sixes
  paying nothing until 1800 — plus `U-0030` for the joint "Old and Deferred"
  quotation the papers actually print.
- **War loans are separated by statute, not masthead year.** "War Loans, 1813" is
  the sixteen-million loan of 8 February 1813, maturing 1826 — a different
  security from the 1812 loan, maturing 1824.

`U-0900` is a deliberate bucket for quotes that are clearly federal but cannot be
pinned to an issue, so ambiguity is recorded rather than guessed.

### The merge key

> ### `SECURITY_CROSSWALK.csv`
>
> **One row per canonical security; `canonical_code` is the join key.**
> Use it to merge SWW data into ours, or ours into the ICF database.

Columns: `canonical_code`, `canonical_name`, `namespace`, `sww_code`, `sww_name`,
`icf_colid`, `icf_uid`, `icf_company`, `icf_industry`, `icf_obs`,
`icf_first_year`, `icf_last_year`, `scl_names`, `scl_group`, `scl_issues`,
`match_status`, `notes`.

`canonical_code` is the SWW code where one exists, otherwise a `U-` federal code,
otherwise `X-` for something not yet identified. **The three namespaces are kept
strictly separate** — an earlier bug allocated provisional codes into the reserved
`U-` range and had to be fixed.

Current state: **247 canonical securities** — 237 SWW, 10 federal — of which 29 are
linked to both the ICF database and our transcription, 196 are ICF-only and 22
SCL-only. Of the 353 ICF securities quoted by 1860, **245 (69%) matched strong or
probable**; the 317 first quoted after 1860 fall outside SWW's window and are left
unmatched by design rather than force-matched.

Matching is **class-constrained throughout**, so a bank can never be matched to an
insurer of the same name.

**Regenerate after any new extraction:**

```
python3 sww_crosswalk.py --src <extraction-dir> --out sww_crosswalk.csv
python3 icf_sww_crosswalk.py
python3 build_security_crosswalk.py        # -> SECURITY_CROSSWALK.csv
```

Rows with `match_status` of `weak - check` are proposals, not conclusions.

---

## 6. External validation

**Jack Wilson's memo of 31 August 2000** to Sylla and Goetzmann ("Early Data on US
Stock Returns — New York in 1822", filed at
`OLD/wigoE/work/OLDNYSE/jack-wilson-1822-additions.pdf`) transcribed the *same
newspaper* by hand from New York Public Library hardcopy, taking the issue nearest
month-end from "every other issue of the 104 per year".

His seven securities listed as missing at June 1822 month-end — Phenix, Franklin,
American, National, Eagle, Fulton, Mechanics — appear in our blank list for the
same 28 June 1822 issue, **six of seven exactly, each in the correct section**. The
seventh is ambiguous only because "Mechanics" names both a bank and a fire office.

The memo also records that as of August 2000 his group had transcribed **weekly New
York prices through June 1841**, and had nothing for 1848–49. That dataset has not
been located; Wilson has since died.

---

## 7. Outputs

| File | Contents |
|---|---|
| `SECURITY_CROSSWALK.csv` | **the merge key** — all three identifier systems |
| `sww_format_1822.csv` | 1822 in SWW shape: `YYYY.MMDD`, `CODE`/`CODEa` bid/ask |
| `sww_format_1822_dictionary.csv` | every code with its namespace |
| `us_federal_codes.csv` | the `U-` scheme with statute, coupon, maturity, amount issued |
| `sww_ny_codes.json` | SWW code → name, extracted from the ICPSR codebook |
| `gapfill_monthly.csv` | the 23 blank months, mid-quotes by the house rule |
| `worksheets/entry_*.xlsx` | hand-entry workbooks (below) |
| `issue_index.json` | all 3,673 FRASER issues with dates and item ids |

**Hand-entry workbooks** — one sheet per issue: `# | SWW code | Security | Bid |
Ask | Note | alternatives`, with the cropped scan alongside from column I.
Securities appear in the order printed. Black = the OCR passes agreed; **red =
they disagreed, check the scan**; grey = no quotation printed; a red SWW code
means an uncertain crosswalk match. `collect_worksheets.py` reads corrections back
out and reports how often the OCR was wrong on cells it was confident about.

---

## 8. Known limitations

1. **April 1817 is unreliable** — sideways typesetting, 54% exact, 6 of 22 rows
   unanimous. Transcribe by hand.
2. **1848 is transactions, not quotations.** Sparser and not comparable to 1822 as
   a monthly cross-section; collapsing a session's trades to one price is a
   modelling choice (mean of each trade's range was used here; last-sale is equally
   defensible).
3. **December 1858 is still blank** — FRASER's coverage thins after 1849 and does
   not hold it.
4. **"On time" quotes are unmapped by design.** `Franklin Bank, on time` and
   `Mechanics Bank, on time` are **time bargains** — forward contracts settling at
   a future date, quoted beside the cash price. The cash-to-time spread is a
   genuine cost-of-carry observation. They are deliberately not merged into the
   cash security; whether they get their own codes is an open decision.
5. **Fraction-level accuracy is a floor, not a budget problem.** More votes and
   higher-resolution scans were both tested and neither helped.

---

## 9. Cost

Roughly **$0.19–0.21 per issue** on Claude Opus 5 with three votes (locate pass
~$0.01, transcription the rest). Spend to date: gap fill of 23 months **$7.86**;
1822 full year twice (once before and once after the ditto/heading rules) **$41.6**;
diagnostics ~$5.

Image acquisition from FRASER is free.

---

## 10. Revision log

| Date | Change |
|---|---|
| 2026-08-18 | FRASER route established; 3,673-issue index built; 23 gap months extracted and assembled |
| 2026-08-19 | Ditto, rule-length and section-heading conventions encoded (WNG); 1822 re-extracted; SWW format reverse-engineered; `U-` federal scheme created; `SECURITY_CROSSWALK.csv` built; superseded `SCHEMA_NOTES.md` folded in and removed |

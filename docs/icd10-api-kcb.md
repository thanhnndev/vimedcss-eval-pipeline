KCB ICD-10 API (06/2026/TT-BYT) — Reverse-engineered endpoint reference
======================================================================

Source
------
Web application     : https://icd.kcb.vn/icd-10-tt06/icd10-tt06-dual
Search endpoint host: https://ccs.whiteneuron.com/api/ICD10
API key / CSRF      : No key discovered. Requests return normally from curl / browser.

----------------------------------------------------------
1) SEARCH ENDPOINT  (primary programmatic interface)
----------------------------------------------------------
GET https://ccs.whiteneuron.com/api/ICD10/search/<encoded-query>

Query parameters
----------------
lang      "vi" | "en"   — response language for labels (chapter / section / type / disease)
vol1      "1" | "0"     — include Volume 1 hierarchical tree (modern chapters)
vol3      "1" | "0"     — include Volume 3 index / cross-reference list
html      "true" | "false" — "true" returns HTML fragments inside JSON; "false" → 500 error

All parameters are optional except the path query `<encoded-query>`.

----------------------------------------------------------
RESPONSE FORMAT (JSON)
----------------------------------------------------------
{
  "status": "success" | "failure",
  "string": "<the original query>",
  "time": <float seconds>,
  "html": "<escaped HTML string with the tree>"
}

When status = "failure" the `html` field contains a short Vietnamese message:
`<b class=\"highline\">ICD-10 vol 1</b>: Không tìm thấy kết quả thich hợp!`

The `html` payload is a nested `<ul>` / `<li>` list.  Each `<li>` has a
`class` attribute that identifies the node type:

    chapter   → top-level ICD chapter (Roman numeral I–XXII)
    section   → 3-character block range (e.g. A00-A09)
    type      → 3-character category (e.g. A00)
    disease   → 4-character subcategory (e.g. A00.0)

Each node contains one `<a href="...">` whose inner `<span class="code">`
holds the ICD code and `<span class="label">` holds the localized title.
Matches inside the label are wrapped in `<b class="highline">`.

Example (truncated, lang=vi, vol1=1, vol3=0):
{
  "status":"success","string":"A00","time":0.044,
  "html":"<p><b class=\"highline\">ICD-10 vol 1</b></p>\n\n<li class=\"chapter\">\n  <a href=\"chapter/A00-B99\">\n    <span class=\"code\">I</span>\n    <span class=\"label\">Bệnh nhiễm trùng và ký sinh trùng</span>\n  </a>\n  <ul>\n    <li class=\"section\">\n      <a href=\"section/A00-A09\">\n        <span class=\"code\">A00-A09</span>\n        <span class=\"label\">Bệnh nhiễm trùng đường ruột</span>\n      </a>\n      <ul>\n        <li class=\"type\">\n          <a href=\"type/A00\">\n            <span class=\"code\">A00</span>\n            <span class=\"label\">Bệnh tả</span>\n          </a>\n          <ul>\n            <li class=\"disease\">\n              <a href=\"disease/A000\">\n                <span class=\"code\">A00.0</span>\n                <span class=\"label\">Bệnh tả do Vibrio cholerae 01, type sinh học cholerae</span>\n              </a>\n            </li>\n          </ul>\n        </li>\n      </ul>\n    </li>\n  </ul>\n</li>"
}

----------------------------------------------------------
2) LANGUAGE SUPPORT (dual EN / VI)
----------------------------------------------------------
• lang=vi  → Vietnamese labels  (default on the web site)
• lang=en  → English labels (WHO standard English descriptor)

Both produce identical tree structure; only the `<span class="label">` text
changes.  Example comparison for query "A00":

VI label: "Bệnh nhiễm trùng và ký sinh trùng"
EN label: "Certain infectious and parasitic diseases"

The `<b class="highline">` markers highlight the matching query substring
in the current language.

----------------------------------------------------------
3) VOLUME VARIANTS (vol1 / vol3)
----------------------------------------------------------
vol1=1  (default)  → Volume 1: hierarchical chapter → section → type → disease tree
vol3=1            → Volume 3: alphabetical index / cross-references.
                    Returns <li class="disease"> with <p class="index">
                    containing text snippets where the code appears in the
                    tabular list (morbidity / mortality indexing).

You can combine them: vol1=1&vol3=1 to get both in one response
(order: vol 1 tree first, then vol 3 index section).

----------------------------------------------------------
4) QUERY STRATEGIES
----------------------------------------------------------
A) Exact code (3-char or 4-char)
   search/A00      → returns the whole A00 branch
   search/A00.0    → returns only the A00.0 leaf

B) Keyword / disease name
   search/tuberculosis (lang=en)
   search/lao%20ph%E1%BB%95i (lang=vi URL-encoded)

   Notes:
   - English keyword search works well.
   - Vietnamese keyword search sometimes fails to match; prefer code
     search or English keyword then cross-ref to VI label via lang=vi.

C) Chapter / block range
   search/I00-I99  → returns chapter IX tree (circulatory)

----------------------------------------------------------
5) PARSING RECOMMENDATIONS
----------------------------------------------------------
1. GET the JSON → extract `html` string → unescape JSON escapes.
2. Parse the HTML fragment with any HTML parser (BeautifulSoup, lxml).
3. Walk the <ul>/<li> tree; node type = li["class"].
4. For each <a href="...">:
     code  = <span class="code">.text
     label = <span class="label">.text (strip highline <b> if only clean text wanted)
     href  = <a>.get("href")  # e.g. "chapter/A00-B99", "disease/A000"
5. Build parent→child relations by tree depth.

Sample Python snippet (BeautifulSoup):
```python
import requests, json
from bs4 import BeautifulSoup

def search_icd10(query, lang="vi", vol1=1, vol3=0):
    url = f"https://ccs.whiteneuron.com/api/ICD10/search/{requests.utils.quote(query)}"
    params = {"lang": lang, "vol1": vol1, "vol3": vol3, "html": "true"}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    if data["status"] != "success":
        return []
    soup = BeautifulSoup(data["html"], "html.parser")
    results = []
    for li in soup.find_all("li", class_=True):
        node_type = li["class"][0]
        a = li.find("a")
        if not a:
            continue
        code  = a.find("span", class_="code").get_text(strip=True)
        label = a.find("span", class_="label").get_text(strip=True)
        href  = a.get("href")
        results.append({"type": node_type, "code": code, "label": label, "href": href})
    return results
```

----------------------------------------------------------
6) COMPLETE ENDPOINT SUMMARY
----------------------------------------------------------
| Purpose                | URL pattern                                               |
|------------------------|-----------------------------------------------------------|
| Search (codes, words)  | /api/ICD10/search/<query>?lang=vi\|en&vol1=1&vol3=0&html=true |
| Volume 1 tree only     | add vol1=1&vol3=0                                         |
| Volume 3 index only    | add vol1=0&vol3=1                                         |
| Both volumes           | vol1=1&vol3=1                                             |

----------------------------------------------------------
7) LIVE EXAMPLES (tested)
----------------------------------------------------------
# Vietnamese labels, Volume 1 tree
https://ccs.whiteneuron.com/api/ICD10/search/A00?lang=vi&vol1=1&vol3=0&html=true

# English labels, Volume 1 tree
https://ccs.whiteneuron.com/api/ICD10/search/A00?lang=en&vol1=1&vol3=0&html=true

# Vietnamese, keyword (English works better)
https://ccs.whiteneuron.com/api/ICD10/search/hypertension?lang=en&vol1=1&vol3=0&html=true

# Volume 3 index cross-refs
https://ccs.whiteneuron.com/api/ICD10/search/A00?lang=vi&vol1=1&vol3=1&html=true

# Specific 4-char code
https://ccs.whiteneuron.com/api/ICD10/search/I10?lang=vi&vol1=1&vol3=0&html=true
https://ccs.whiteneuron.com/api/ICD10/search/I10?lang=en&vol1=1&vol3=0&html=true

# Chapter range
https://ccs.whiteneuron.com/api/ICD10/search/I00-I99?lang=en&vol1=1&vol3=0&html=true

----------------------------------------------------------
8) CAVEATS / LIMITATIONS
----------------------------------------------------------
• No official API documentation; this is reverse-engineered from the
  public KCB web client.  Endpoint/path may change without notice.
• html=false returns HTTP 500 — do not use.
• Rate limits not published; be courteous (add delays / retry logic).
• Vietnamese free-text search can miss matches; prefer code search or
  English keyword + dual-language retrieval (first EN to get code, then
  VI with the same code).
• The <a href="..."> links (chapter/, section/, type/, disease/) are
  internal to the WhiteNeuron front-end and return 404 when called
  directly via the /api/ICD10/ base.  Use the search endpoint only.

----------------------------------------------------------
9) QUICK CURL REFERENCE
----------------------------------------------------------
# Search by code (VI)
curl 'https://ccs.whiteneuron.com/api/ICD10/search/A00?lang=vi&vol1=1&vol3=0&html=true'

# Search by code (EN)
curl 'https://ccs.whiteneuron.com/api/ICD10/search/A00?lang=en&vol1=1&vol3=0&html=true'

# Search by keyword (EN)
curl 'https://ccs.whiteneuron.com/api/ICD10/search/hypertension?lang=en&vol1=1&vol3=0&html=true'

# Search with both volumes
curl 'https://ccs.whiteneuron.com/api/ICD10/search/A00?lang=vi&vol1=1&vol3=1&html=true'

----------------------------------------------------------
10) SUGGESTED INGESTION WORKFLOW FOR EN/VI DATASET
----------------------------------------------------------
1. Iterate all 3-char ICD-10 categories (A00–Z99, ~2000 codes).
2. For each, GET search/<code>?lang=en&vol1=1&vol3=0&html=true → parse EN labels.
3. GET same with lang=vi → parse VI labels.
4. Join on code to produce dual-language CSV / JSONL:
   code, chapter, section, type, disease_en, disease_vi
5. Optionally pull vol3=1 for index cross-references.

Rate-limit: ≥ 200 ms between requests; exponential back-off on 429/5xx.

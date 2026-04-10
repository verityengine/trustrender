// Simple invoice - 1 page, 10 line items
// Tests: logo, table, totals, header/footer, page numbers

#set page(
  paper: "us-letter",
  margin: (top: 1.2in, bottom: 1in, left: 1in, right: 1in),
  header: align(right, text(size: 8pt, fill: luma(120))[Acme Corporation]),
  footer: context align(center, text(size: 8pt, fill: luma(120))[
    Page #counter(page).display("1 of 1", both: true)
  ]),
)

#set text(size: 10pt, font: "Inter")

// --- Logo and Invoice Title ---
#grid(
  columns: (1fr, 1fr),
  align(left, image("assets/logo.png", width: 1.5in)),
  align(right)[
    #text(size: 24pt, weight: "bold")[INVOICE]
    #v(4pt)
    #text(size: 10pt, fill: luma(100))[Invoice \#INV-2026-0042]
  ],
)

#v(0.3in)

// --- Sender / Recipient ---
#grid(
  columns: (1fr, 1fr),
  gutter: 0.5in,
  [
    #text(weight: "bold")[From:]
    #v(4pt)
    Acme Corporation \
    123 Business Ave, Suite 400 \
    San Francisco, CA 94105 \
    billing\@acme.com
  ],
  [
    #text(weight: "bold")[Bill To:]
    #v(4pt)
    Contoso Ltd. \
    456 Enterprise Blvd \
    New York, NY 10001 \
    accounts\@contoso.com
  ],
)

#v(0.2in)

// --- Invoice Details ---
#grid(
  columns: (1fr, 1fr, 1fr),
  [
    #text(weight: "bold")[Invoice Date] \
    April 10, 2026
  ],
  [
    #text(weight: "bold")[Due Date] \
    May 10, 2026
  ],
  [
    #text(weight: "bold")[Payment Terms] \
    Net 30
  ],
)

#v(0.3in)

// --- Line Items Table ---
#table(
  columns: (auto, 3fr, 1fr, 1fr, 1fr),
  stroke: none,
  inset: (x: 8pt, y: 6pt),

  // Header
  table.header(
    table.cell(fill: luma(240))[*\#*],
    table.cell(fill: luma(240))[*Description*],
    table.cell(fill: luma(240), align(right)[*Qty*]),
    table.cell(fill: luma(240), align(right)[*Unit Price*]),
    table.cell(fill: luma(240), align(right)[*Amount*]),
  ),
  table.hline(stroke: 0.5pt),

  // Row 1
  [1], [Website redesign and development], align(right)[1], align(right)[\$4,500.00], align(right)[\$4,500.00],
  table.hline(stroke: 0.3pt + luma(200)),
  // Row 2
  [2], [Logo design and brand identity package], align(right)[1], align(right)[\$2,200.00], align(right)[\$2,200.00],
  table.hline(stroke: 0.3pt + luma(200)),
  // Row 3
  [3], [SEO optimization and keyword research], align(right)[1], align(right)[\$1,800.00], align(right)[\$1,800.00],
  table.hline(stroke: 0.3pt + luma(200)),
  // Row 4
  [4], [Social media content creation (monthly)], align(right)[3], align(right)[\$750.00], align(right)[\$2,250.00],
  table.hline(stroke: 0.3pt + luma(200)),
  // Row 5
  [5], [Email marketing campaign setup], align(right)[1], align(right)[\$1,200.00], align(right)[\$1,200.00],
  table.hline(stroke: 0.3pt + luma(200)),
  // Row 6
  [6], [Analytics dashboard configuration], align(right)[1], align(right)[\$950.00], align(right)[\$950.00],
  table.hline(stroke: 0.3pt + luma(200)),
  // Row 7
  [7], [Content writing - blog posts], align(right)[5], align(right)[\$300.00], align(right)[\$1,500.00],
  table.hline(stroke: 0.3pt + luma(200)),
  // Row 8
  [8], [Photography and image editing], align(right)[1], align(right)[\$800.00], align(right)[\$800.00],
  table.hline(stroke: 0.3pt + luma(200)),
  // Row 9
  [9], [Hosting setup and DNS configuration], align(right)[1], align(right)[\$350.00], align(right)[\$350.00],
  table.hline(stroke: 0.3pt + luma(200)),
  // Row 10
  [10], [Staff training and documentation], align(right)[2], align(right)[\$500.00], align(right)[\$1,000.00],
)

#v(0.2in)

// --- Totals ---
#align(right)[
  #grid(
    columns: (auto, 120pt),
    row-gutter: 6pt,
    align(right)[Subtotal:], align(right)[\$16,550.00],
    align(right)[Tax (8.5%):], align(right)[\$1,406.75],
    grid.hline(stroke: 0.5pt),
    align(right)[#text(weight: "bold", size: 12pt)[Total Due:]], align(right)[#text(weight: "bold", size: 12pt)[\$17,956.75]],
  )
]

#v(0.4in)

// --- Notes ---
#line(length: 100%, stroke: 0.5pt + luma(200))
#v(0.1in)
#text(size: 9pt, fill: luma(100))[
  *Notes:* Payment is due within 30 days. Please include the invoice number with your payment.
  For questions, contact billing\@acme.com.
]

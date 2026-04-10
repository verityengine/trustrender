// Invoice template using sys.inputs for data binding
// Tests: can Typst accept structured data directly from Python?

// Read data from sys.inputs
#let invoice_number = sys.inputs.at("invoice_number", default: "N/A")
#let invoice_date = sys.inputs.at("invoice_date", default: "N/A")
#let due_date = sys.inputs.at("due_date", default: "N/A")
#let payment_terms = sys.inputs.at("payment_terms", default: "N/A")

// Nested data - sender/recipient
#let sender_name = sys.inputs.at("sender_name", default: "N/A")
#let sender_addr1 = sys.inputs.at("sender_addr1", default: "")
#let sender_addr2 = sys.inputs.at("sender_addr2", default: "")
#let sender_email = sys.inputs.at("sender_email", default: "")

#let recipient_name = sys.inputs.at("recipient_name", default: "N/A")
#let recipient_addr1 = sys.inputs.at("recipient_addr1", default: "")
#let recipient_addr2 = sys.inputs.at("recipient_addr2", default: "")
#let recipient_email = sys.inputs.at("recipient_email", default: "")

// Totals
#let subtotal = sys.inputs.at("subtotal", default: "$0.00")
#let tax_rate = sys.inputs.at("tax_rate", default: "0%")
#let tax_amount = sys.inputs.at("tax_amount", default: "$0.00")
#let total = sys.inputs.at("total", default: "$0.00")
#let notes = sys.inputs.at("notes", default: "")

// Items - passed as JSON string, parsed here
#let items_json = sys.inputs.at("items_json", default: "[]")
#let items = json.decode(items_json)

#set page(
  paper: "us-letter",
  margin: (top: 1.2in, bottom: 1in, left: 1in, right: 1in),
  header: align(right, text(size: 8pt, fill: luma(120))[#sender_name]),
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
    #text(size: 10pt, fill: luma(100))[Invoice \##invoice_number]
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
    #sender_name \
    #sender_addr1 \
    #sender_addr2 \
    #sender_email
  ],
  [
    #text(weight: "bold")[Bill To:]
    #v(4pt)
    #recipient_name \
    #recipient_addr1 \
    #recipient_addr2 \
    #recipient_email
  ],
)

#v(0.2in)

// --- Invoice Details ---
#grid(
  columns: (1fr, 1fr, 1fr),
  [
    #text(weight: "bold")[Invoice Date] \
    #invoice_date
  ],
  [
    #text(weight: "bold")[Due Date] \
    #due_date
  ],
  [
    #text(weight: "bold")[Payment Terms] \
    #payment_terms
  ],
)

#v(0.3in)

// --- Line Items Table ---
#table(
  columns: (auto, 3fr, 1fr, 1fr, 1fr),
  stroke: none,
  inset: (x: 8pt, y: 6pt),

  table.header(
    table.cell(fill: luma(240))[*\#*],
    table.cell(fill: luma(240))[*Description*],
    table.cell(fill: luma(240), align(right)[*Qty*]),
    table.cell(fill: luma(240), align(right)[*Unit Price*]),
    table.cell(fill: luma(240), align(right)[*Amount*]),
  ),
  table.hline(stroke: 0.5pt),

  ..for item in items {
    (
      [#item.at("num")],
      [#item.at("description")],
      align(right)[#str(item.at("qty"))],
      align(right)[#item.at("unit_price")],
      align(right)[#item.at("amount")],
      table.hline(stroke: 0.3pt + luma(200)),
    )
  },
)

#v(0.2in)

// --- Totals ---
#align(right)[
  #grid(
    columns: (auto, 120pt),
    row-gutter: 6pt,
    align(right)[Subtotal:], align(right)[#subtotal],
    align(right)[Tax (#tax_rate):], align(right)[#tax_amount],
    grid.hline(stroke: 0.5pt),
    align(right)[#text(weight: "bold", size: 12pt)[Total Due:]], align(right)[#text(weight: "bold", size: 12pt)[#total]],
  )
]

#v(0.4in)

// --- Notes ---
#line(length: 100%, stroke: 0.5pt + luma(200))
#v(0.1in)
#text(size: 9pt, fill: luma(100))[
  *Notes:* #notes
]

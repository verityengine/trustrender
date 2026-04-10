// Invoice template - Jinja2 preprocessed
// Data flows: JSON -> Jinja2 -> Typst markup -> PDF

#set page(
  paper: "us-letter",
  margin: (top: 1.2in, bottom: 1in, left: 1in, right: 1in),
  header: align(right, text(size: 8pt, fill: luma(120))[{{ sender.name }}]),
  footer: {% include "fragments/footer_page.j2.typ" %},
)

#set text(size: 10pt, font: "Inter")

// --- Logo and Invoice Title ---
{% set logo_path = "assets/logo.png" %}
{% set doc_title = "INVOICE" %}
{% set doc_subtitle = "Invoice #" + invoice_number %}
{% include "fragments/header_logo.j2.typ" %}

#v(0.3in)

// --- Sender / Recipient ---
#grid(
  columns: (1fr, 1fr),
  gutter: 0.5in,
  [
    #text(weight: "bold")[From:]
    #v(4pt)
    {{ sender.name }} \
    {{ sender.address_line1 }} \
    {{ sender.address_line2 }} \
    {{ sender.email }}
  ],
  [
    #text(weight: "bold")[Bill To:]
    #v(4pt)
    {{ recipient.name }} \
    {{ recipient.address_line1 }} \
    {{ recipient.address_line2 }} \
    {{ recipient.email }}
  ],
)

#v(0.2in)

// --- Invoice Details ---
#grid(
  columns: (1fr, 1fr, 1fr),
  [
    #text(weight: "bold")[Invoice Date] \
    {{ invoice_date }}
  ],
  [
    #text(weight: "bold")[Due Date] \
    {{ due_date }}
  ],
  [
    #text(weight: "bold")[Payment Terms] \
    {{ payment_terms }}
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
{% for item in items %}
  [{{ item.num }}], [{{ item.description }}], align(right)[{{ item.qty }}], align(right)[{{ item.unit_price }}], align(right)[{{ item.amount }}],
  table.hline(stroke: 0.3pt + luma(200)),
{% endfor %}
)

#v(0.2in)

// --- Totals ---
#align(right)[
  #grid(
    columns: (auto, 120pt),
    row-gutter: 6pt,
    align(right)[Subtotal:], align(right)[{{ subtotal }}],
    align(right)[Tax ({{ tax_rate }}):], align(right)[{{ tax_amount }}],
    grid.hline(stroke: 0.5pt),
    align(right)[#text(weight: "bold", size: 12pt)[Total Due:]], align(right)[#text(weight: "bold", size: 12pt)[{{ total }}]],
  )
]

#v(0.4in)

// --- Notes ---
#line(length: 100%, stroke: 0.5pt + luma(200))
#v(0.1in)
#text(size: 9pt, fill: luma(100))[
  *Notes:* {{ notes }}
]

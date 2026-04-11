// ZUGFeRD EN 16931 Invoice Template
// Data: einvoice_data.json (numeric amounts, structured tax, VAT IDs)

#let accent = rgb("#1a1a1a")
#let muted = luma(110)
#let rule-color = luma(210)

#set page(
  paper: "a4",
  margin: (top: 1.4in, bottom: 1.2in, left: 1in, right: 1in),
  header: align(right, text(size: 8pt, fill: muted)[{{ seller.name }} · USt-IdNr. {{ seller.vat_id }}]),
  footer: context align(center, text(size: 8pt, fill: muted)[
    Seite #counter(page).display("1 von 1", both: true)
  ]),
)

#set text(size: 9.5pt, font: "Inter", lang: "de")

// --- Header: Logo + Title ---
#grid(
  columns: (1fr, 1fr),
  align(left, image("assets/logo.png", width: 1.2in)),
  align(right)[
    #text(size: 22pt, weight: "bold", fill: accent)[{% if invoice_type|default("380") == "381" %}GUTSCHRIFT{% else %}RECHNUNG{% endif %}]
    #v(6pt)
    #text(size: 9pt, fill: muted)[Nr. {{ invoice_number }}]
    #v(2pt)
    #text(size: 9pt, fill: muted)[Datum: {{ invoice_date }} · Fällig: {{ due_date }}]
{% if referenced_invoice %}
    #v(2pt)
    #text(size: 9pt, fill: muted)[Bezug: {{ referenced_invoice }}]
{% endif %}
  ],
)

#v(0.4in)

// --- Seller / Buyer ---
#grid(
  columns: (1fr, 1fr),
  gutter: 0.6in,
  [
    #text(size: 8pt, weight: "bold", fill: muted)[ABSENDER]
    #v(6pt)
    #text(weight: "bold")[{{ seller.name }}] \
    {{ seller.address }} \
    {{ seller.postal_code }} {{ seller.city }} \
    #v(4pt)
    #text(size: 8.5pt, fill: muted)[USt-IdNr.: {{ seller.vat_id }}] \
    #text(size: 8.5pt, fill: muted)[{{ seller.email }}{% if seller.phone %} · {{ seller.phone }}{% endif %}]
  ],
  [
    #text(size: 8pt, weight: "bold", fill: muted)[EMPFÄNGER]
    #v(6pt)
    #text(weight: "bold")[{{ buyer.name }}] \
    {{ buyer.address }} \
    {{ buyer.postal_code }} {{ buyer.city }} \
    #v(4pt)
    #text(size: 8.5pt, fill: muted)[USt-IdNr.: {{ buyer.vat_id }}]
  ],
)

#v(0.4in)

// --- Line Items ---
#table(
  columns: (40pt, 1fr, 60pt, 80pt, 80pt),
  stroke: none,
  inset: (x: 8pt, y: 7pt),

  table.header(
    table.cell(fill: luma(245))[#text(size: 8pt, weight: "bold")[Pos.]],
    table.cell(fill: luma(245))[#text(size: 8pt, weight: "bold")[Beschreibung]],
    table.cell(fill: luma(245), align(right)[#text(size: 8pt, weight: "bold")[Menge]]),
    table.cell(fill: luma(245), align(right)[#text(size: 8pt, weight: "bold")[Einzelpreis]]),
    table.cell(fill: luma(245), align(right)[#text(size: 8pt, weight: "bold")[Betrag]]),
  ),
  table.hline(stroke: 0.6pt + rule-color),
{% for item in items %}
  [{{ loop.index }}],
  [{{ item.description }}],
  align(right)[{{ item.quantity }}],
  align(right)[{{ "%.2f" | format(item.unit_price) }} €],
  align(right)[{{ "%.2f" | format(item.line_total) }} €],
  table.hline(stroke: 0.3pt + luma(230)),
{% endfor %}
)

#v(0.3in)

// --- Totals ---
#align(right)[
  #grid(
    columns: (auto, 100pt),
    row-gutter: 8pt,
    align(right, text(fill: muted)[Nettobetrag:]),
    align(right)[{{ "%.2f" | format(subtotal) }} €],
{% for entry in tax_entries %}
    align(right, text(fill: muted)[USt. {{ entry.rate }}%:]),
    align(right)[{{ "%.2f" | format(entry.amount) }} €],
{% endfor %}
    grid.hline(stroke: 0.8pt + accent),
    align(right)[#text(weight: "bold", size: 12pt)[Gesamtbetrag:]],
    align(right)[#text(weight: "bold", size: 12pt)[{{ "%.2f" | format(total) }} €]],
  )
]

#v(0.5in)

// --- Payment & Notes ---
#line(length: 100%, stroke: 0.4pt + rule-color)
#v(8pt)
#text(size: 8.5pt, fill: muted)[
  #text(weight: "bold")[Bankverbindung:] {{ payment.bank_name }} · IBAN: {{ payment.iban }} · BIC: {{ payment.bic }} \
  #v(4pt)
  {{ notes }}
]

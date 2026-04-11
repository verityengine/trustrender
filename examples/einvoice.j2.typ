// ZUGFeRD EN 16931 Invoice Template
// Data: einvoice_data.json (numeric amounts, structured tax, VAT IDs)

#set page(paper: "a4", margin: (top: 1.2in, bottom: 1in, left: 1in, right: 1in))
#set text(size: 10pt, font: "Inter", lang: "de")
#set document(title: "{% if invoice_type|default('380') == '381' %}Gutschrift{% else %}Rechnung{% endif %} " + "{{ invoice_number }}")

// --- Header ---
#grid(
  columns: (1fr, 1fr),
  [
    #text(size: 22pt, weight: "bold")[{% if invoice_type|default("380") == "381" %}GUTSCHRIFT{% else %}RECHNUNG{% endif %}]
    #v(4pt)
    #text(size: 9pt, fill: luma(100))[Nr. {{ invoice_number }}]
{% if referenced_invoice %}
    #v(2pt)
    #text(size: 9pt, fill: luma(100))[Bezug: {{ referenced_invoice }}]
{% endif %}
  ],
  align(right)[
    #text(size: 9pt, fill: luma(100))[
      Rechnungsdatum: {{ invoice_date }} \
      Fällig: {{ due_date }}
    ]
  ],
)

#v(0.3in)

// --- Seller / Buyer ---
#grid(
  columns: (1fr, 1fr),
  gutter: 0.5in,
  [
    #text(weight: "bold")[Absender:]
    #v(4pt)
    {{ seller.name }} \
    {{ seller.address }} \
    {{ seller.postal_code }} {{ seller.city }} \
    USt-IdNr.: {{ seller.vat_id }} \
    {{ seller.email }}
  ],
  [
    #text(weight: "bold")[Empfänger:]
    #v(4pt)
    {{ buyer.name }} \
    {{ buyer.address }} \
    {{ buyer.postal_code }} {{ buyer.city }} \
    USt-IdNr.: {{ buyer.vat_id }}
  ],
)

#v(0.3in)

// --- Line Items ---
#table(
  columns: (auto, 3fr, 1fr, 1fr, 1fr),
  stroke: none,
  inset: (x: 8pt, y: 6pt),

  table.header(
    table.cell(fill: luma(240))[*Pos.*],
    table.cell(fill: luma(240))[*Beschreibung*],
    table.cell(fill: luma(240), align(right)[*Menge*]),
    table.cell(fill: luma(240), align(right)[*Einzelpreis*]),
    table.cell(fill: luma(240), align(right)[*Betrag*]),
  ),
  table.hline(stroke: 0.5pt),
{% for item in items %}
  [{{ loop.index }}], [{{ item.description }}], align(right)[{{ item.quantity }}], align(right)[{{ "%.2f" | format(item.unit_price) }} €], align(right)[{{ "%.2f" | format(item.line_total) }} €],
  table.hline(stroke: 0.3pt + luma(200)),
{% endfor %}
)

#v(0.2in)

// --- Totals ---
#align(right)[
  #grid(
    columns: (auto, 120pt),
    row-gutter: 6pt,
    align(right)[Nettobetrag:], align(right)[{{ "%.2f" | format(subtotal) }} €],
{% for entry in tax_entries %}
    align(right)[USt. {{ entry.rate }}%:], align(right)[{{ "%.2f" | format(entry.amount) }} €],
{% endfor %}
    grid.hline(stroke: 0.5pt),
    align(right)[#text(weight: "bold", size: 12pt)[Gesamtbetrag:]], align(right)[#text(weight: "bold", size: 12pt)[{{ "%.2f" | format(total) }} €]],
  )
]

#v(0.3in)

// --- Payment ---
#line(length: 100%, stroke: 0.5pt + luma(200))
#v(0.1in)
#text(size: 9pt, fill: luma(100))[
  *Bankverbindung:* {{ payment.bank_name }} · IBAN: {{ payment.iban }} · BIC: {{ payment.bic }} \
  {{ notes }}
]

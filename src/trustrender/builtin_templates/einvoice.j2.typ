// ZUGFeRD EN 16931 Invoice Template
// Data: einvoice_data.json (numeric amounts, structured tax, VAT IDs)

#let primary = rgb("#1B2838")
#let accent = rgb("#C4622A")
#let muted = rgb("#7A7670")
#let light-bg = rgb("#F8F7F5")
#let rule-light = rgb("#E5E2DD")

#set page(
  paper: "a4",
  margin: (top: 0.8in, bottom: 1in, left: 0.9in, right: 0.9in),
  header: [],
  footer: context {
    let pg = counter(page)
    align(center, text(size: 7.5pt, fill: muted, font: "Inter")[
      {{ seller.name }} · {{ seller.address }}, {{ seller.postal_code }} {{ seller.city }} · {{ seller.email }}
      #v(2pt)
      Seite #pg.display("1") von #pg.final().at(0)
    ])
  },
)

#set text(size: 9.5pt, font: "Inter", fill: primary, lang: "de")

// ══════════════════════════════════════════════════════════════
// HEADER BAND
// ══════════════════════════════════════════════════════════════

#block(width: 100%, inset: (bottom: 16pt))[
  #grid(
    columns: (1fr, 1fr),
    [
      #text(weight: "bold", size: 14pt)[{{ seller.name }}]
      #v(6pt)
      #text(size: 7.5pt, fill: muted)[USt-IdNr. {{ seller.vat_id }}]
    ],
    align(right)[
      #text(size: 28pt, weight: "bold", fill: primary, tracking: 0.5pt)[{% if invoice_type|default("380") == "381" %}GUTSCHRIFT{% else %}RECHNUNG{% endif %}]
      #v(4pt)
      #block(width: 100%, fill: accent, radius: 2pt, inset: (x: 10pt, y: 5pt))[
        #text(size: 9pt, fill: white, weight: "bold")[Nr. {{ invoice_number }}]
        #h(1fr)
        #text(size: 9pt, fill: white)[{{ invoice_date }}]
      ]
{% if referenced_invoice %}
      #v(3pt)
      #text(size: 8pt, fill: muted)[Bezug: {{ referenced_invoice }}]
{% endif %}
    ],
  )
]

#line(length: 100%, stroke: 1.5pt + accent)
#v(16pt)

// ══════════════════════════════════════════════════════════════
// META ROW — dates + payment terms
// ══════════════════════════════════════════════════════════════

#grid(
  columns: (1fr, 1fr, 1fr),
  gutter: 12pt,
  [
    #text(size: 7pt, weight: "bold", fill: muted, tracking: 0.8pt)[RECHNUNGSDATUM]
    #v(3pt)
    #text(size: 10pt, weight: "bold")[{{ invoice_date }}]
  ],
  [
    #text(size: 7pt, weight: "bold", fill: muted, tracking: 0.8pt)[FÄLLIG]
    #v(3pt)
    #text(size: 10pt, weight: "bold")[{{ due_date }}]
  ],
  [
    #text(size: 7pt, weight: "bold", fill: muted, tracking: 0.8pt)[WÄHRUNG]
    #v(3pt)
    #text(size: 10pt, weight: "bold")[{{ currency }}]
  ],
)

#v(20pt)

// ══════════════════════════════════════════════════════════════
// ADDRESSES
// ══════════════════════════════════════════════════════════════

#grid(
  columns: (1fr, 1fr),
  gutter: 0.5in,
  [
    #block(width: 100%, stroke: (left: 3pt + accent), inset: (left: 12pt, y: 4pt))[
      #text(size: 7pt, weight: "bold", fill: muted, tracking: 0.8pt)[ABSENDER]
      #v(6pt)
      #text(size: 10pt, weight: "bold")[{{ seller.name }}]
      #v(3pt)
      {{ seller.address }} \
      {{ seller.postal_code }} {{ seller.city }}
      #v(6pt)
      #text(size: 8pt, fill: muted)[
        USt-IdNr.: {{ seller.vat_id }} \
        {{ seller.email }}{% if seller.phone %} · {{ seller.phone }}{% endif %}
      ]
    ]
  ],
  [
    #block(width: 100%, stroke: (left: 3pt + rule-light), inset: (left: 12pt, y: 4pt))[
      #text(size: 7pt, weight: "bold", fill: muted, tracking: 0.8pt)[EMPFÄNGER]
      #v(6pt)
      #text(size: 10pt, weight: "bold")[{{ buyer.name }}]
      #v(3pt)
      {{ buyer.address }} \
      {{ buyer.postal_code }} {{ buyer.city }}
      #v(6pt)
      #text(size: 8pt, fill: muted)[
        USt-IdNr.: {{ buyer.vat_id }}
      ]
    ]
  ],
)

#v(24pt)

// ══════════════════════════════════════════════════════════════
// LINE ITEMS
// ══════════════════════════════════════════════════════════════

#text(size: 7pt, weight: "bold", fill: muted, tracking: 0.8pt)[POSITIONEN]
#v(8pt)

#table(
  columns: (36pt, 1fr, 50pt, 80pt, 80pt),
  stroke: none,
  inset: (x: 8pt, y: 8pt),
  fill: (_, row) => if row == 0 { primary } else if calc.odd(row) { light-bg } else { none },

  // Header row
  text(size: 7.5pt, weight: "bold", fill: white, tracking: 0.5pt)[POS.],
  text(size: 7.5pt, weight: "bold", fill: white, tracking: 0.5pt)[BESCHREIBUNG],
  align(right, text(size: 7.5pt, weight: "bold", fill: white, tracking: 0.5pt)[MENGE]),
  align(right, text(size: 7.5pt, weight: "bold", fill: white, tracking: 0.5pt)[EINZELPREIS]),
  align(right, text(size: 7.5pt, weight: "bold", fill: white, tracking: 0.5pt)[BETRAG]),

{% for item in items %}
  [{{ loop.index }}],
  [{{ item.description }}],
  align(right)[{{ item.quantity }}],
  align(right)[{{ "%.2f" | format(item.unit_price) }} €],
  align(right)[{{ "%.2f" | format(item.line_total) }} €],
{% endfor %}
)

#v(16pt)

// ══════════════════════════════════════════════════════════════
// TOTALS
// ══════════════════════════════════════════════════════════════

#align(right)[
  #block(width: 260pt)[
    #grid(
      columns: (1fr, 100pt),
      row-gutter: 8pt,
      align(right, text(fill: muted)[Nettobetrag]),
      align(right)[{{ "%.2f" | format(subtotal) }} €],
{% for entry in tax_entries %}
      align(right, text(fill: muted)[USt. {{ entry.rate }}%]),
      align(right)[{{ "%.2f" | format(entry.amount) }} €],
{% endfor %}
    )
    #v(4pt)
    #line(length: 100%, stroke: 1pt + primary)
    #v(4pt)
    #grid(
      columns: (1fr, 100pt),
      align(right, text(size: 13pt, weight: "bold")[Gesamtbetrag]),
      align(right, text(size: 13pt, weight: "bold", fill: accent)[{{ "%.2f" | format(total) }} €]),
    )
  ]
]

#v(28pt)

// ══════════════════════════════════════════════════════════════
// PAYMENT
// ══════════════════════════════════════════════════════════════

#block(width: 100%, fill: light-bg, radius: 4pt, inset: (x: 14pt, y: 12pt))[
  #grid(
    columns: (1fr, 1fr),
    gutter: 16pt,
    [
      #text(size: 7pt, weight: "bold", fill: muted, tracking: 0.8pt)[BANKVERBINDUNG]
      #v(5pt)
      #text(weight: "bold")[{{ payment.bank_name }}]
      #v(3pt)
      #text(size: 8.5pt)[IBAN: {{ payment.iban }}] \
      #text(size: 8.5pt)[BIC: {{ payment.bic }}]
    ],
    [
      #text(size: 7pt, weight: "bold", fill: muted, tracking: 0.8pt)[HINWEISE]
      #v(5pt)
      #text(size: 8.5pt)[{{ notes }}]
    ],
  )
]

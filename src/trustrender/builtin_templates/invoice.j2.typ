// Invoice layout
#let primary = rgb("#1B2838")
#let accent = rgb("#C4622A")
#let muted = rgb("#7A7670")
#let light-bg = rgb("#F8F7F5")
#let rule-light = rgb("#E5E2DD")

#set page(
  paper: "us-letter",
  margin: (top: 0.8in, bottom: 1in, left: 0.9in, right: 0.9in),
  header: [],
  footer: context align(center, text(size: 7.5pt, fill: muted, font: "Inter")[
    {{ sender.name }} · {{ sender.address }} · {{ sender.email }}
    #v(2pt)
    Page #counter(page).display("1") of #counter(page).final().at(0)
  ]),
)

#set text(size: 9.5pt, font: "Inter", fill: primary)

#block(width: 100%, inset: (bottom: 16pt))[
  #grid(
    columns: (1fr, 1fr),
    [
      #text(size: 14pt, weight: "bold")[{{ sender.name }}]
    ],
    align(right)[
      #text(size: 28pt, weight: "bold", fill: primary, tracking: 0.5pt)[INVOICE]
      #v(4pt)
      #block(width: 100%, fill: accent, radius: 2pt, inset: (x: 10pt, y: 5pt))[
        #text(size: 9pt, fill: white, weight: "bold")[{{ invoice_number }}]
        #h(1fr)
        #text(size: 9pt, fill: white)[{{ invoice_date }}]
      ]
    ],
  )
]

#line(length: 100%, stroke: 1.5pt + accent)
#v(16pt)

#grid(
  columns: (1fr, 1fr, 1fr),
  gutter: 12pt,
  [
    #text(size: 7pt, weight: "bold", fill: muted, tracking: 0.8pt)[INVOICE DATE]
    #v(3pt)
    #text(size: 10pt, weight: "bold")[{{ invoice_date }}]
  ],
  [
    #text(size: 7pt, weight: "bold", fill: muted, tracking: 0.8pt)[DUE DATE]
    #v(3pt)
    #text(size: 10pt, weight: "bold")[{{ due_date }}]
  ],
  [
    #text(size: 7pt, weight: "bold", fill: muted, tracking: 0.8pt)[PAYMENT TERMS]
    #v(3pt)
    #text(size: 10pt, weight: "bold")[{{ payment_terms }}]
  ],
)

#v(20pt)

#grid(
  columns: (1fr, 1fr),
  gutter: 0.5in,
  [
    #block(width: 100%, stroke: (left: 3pt + accent), inset: (left: 12pt, y: 4pt))[
      #text(size: 7pt, weight: "bold", fill: muted, tracking: 0.8pt)[FROM]
      #v(6pt)
      #text(size: 10pt, weight: "bold")[{{ sender.name }}]
      #v(3pt)
      {{ sender.address }}
      #v(4pt)
      #text(size: 8.5pt, fill: muted)[{{ sender.email }}]
    ]
  ],
  [
    #block(width: 100%, stroke: (left: 3pt + rule-light), inset: (left: 12pt, y: 4pt))[
      #text(size: 7pt, weight: "bold", fill: muted, tracking: 0.8pt)[BILL TO]
      #v(6pt)
      #text(size: 10pt, weight: "bold")[{{ recipient.name }}]
      #v(3pt)
      {{ recipient.address }}
      #v(4pt)
      #text(size: 8.5pt, fill: muted)[{{ recipient.email }}]
    ]
  ],
)

#v(24pt)

#text(size: 7pt, weight: "bold", fill: muted, tracking: 0.8pt)[LINE ITEMS]
#v(8pt)

#table(
  columns: (36pt, 1fr, 50pt, 80pt, 80pt),
  stroke: none,
  inset: (x: 8pt, y: 8pt),
  fill: (_, row) => if row == 0 { primary } else if calc.odd(row) { light-bg } else { none },

  text(size: 7.5pt, weight: "bold", fill: white, tracking: 0.5pt)[\#],
  text(size: 7.5pt, weight: "bold", fill: white, tracking: 0.5pt)[DESCRIPTION],
  align(right, text(size: 7.5pt, weight: "bold", fill: white, tracking: 0.5pt)[QTY]),
  align(right, text(size: 7.5pt, weight: "bold", fill: white, tracking: 0.5pt)[UNIT PRICE]),
  align(right, text(size: 7.5pt, weight: "bold", fill: white, tracking: 0.5pt)[AMOUNT]),

{% for item in items %}
  [{{ item.num }}],
  [{{ item.description }}],
  align(right)[{{ item.qty }}],
  align(right)[{{ item.unit_price }}],
  align(right)[{{ item.amount }}],
{% endfor %}
)

#v(16pt)

#align(right)[
  #block(width: 260pt)[
    #grid(
      columns: (1fr, 100pt),
      row-gutter: 8pt,
      align(right, text(fill: muted)[Subtotal]),
      align(right)[{{ subtotal }}],
      align(right, text(fill: muted)[Tax ({{ tax_rate }})]),
      align(right)[{{ tax_amount }}],
    )
    #v(4pt)
    #line(length: 100%, stroke: 1pt + primary)
    #v(4pt)
    #grid(
      columns: (1fr, 100pt),
      align(right, text(size: 13pt, weight: "bold")[Total Due]),
      align(right, text(size: 13pt, weight: "bold", fill: accent)[{{ total }}]),
    )
  ]
]

#v(28pt)

#block(width: 100%, fill: light-bg, radius: 4pt, inset: (x: 14pt, y: 12pt))[
  #text(size: 7pt, weight: "bold", fill: muted, tracking: 0.8pt)[NOTES]
  #v(5pt)
  #text(size: 8.5pt)[{{ notes }}]
]

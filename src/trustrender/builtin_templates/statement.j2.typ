// Statement layout

#let primary = rgb("#1B2838")
#let accent = rgb("#C4622A")
#let muted = rgb("#7A7670")
#let light-bg = rgb("#F8F7F5")
#let rule-light = rgb("#E5E2DD")
#let red = rgb("#B83A2A")
#let green = rgb("#4A7C59")

#set page(
  paper: "us-letter",
  margin: (top: 0.8in, bottom: 1in, left: 0.8in, right: 0.8in),
  header: context {
    if counter(page).get().first() > 1 {
      grid(
        columns: (1fr, 1fr),
        align(left, text(size: 7.5pt, fill: muted, font: "Inter")[{{ company.name }}]),
        align(right, text(size: 7.5pt, fill: muted, font: "Inter")[
          Account: {{ customer.account_number }} · Statement (continued)
        ]),
      )
    }
  },
  footer: context align(center, text(size: 7.5pt, fill: muted, font: "Inter")[
    Page #counter(page).display("1") of #counter(page).final().at(0)
  ]),
)

#set text(size: 9.5pt, font: "Inter", fill: primary)

// ══════════════════════════════════════════════════════════════
// HEADER
// ══════════════════════════════════════════════════════════════

#block(width: 100%, inset: (bottom: 16pt))[
  #grid(
    columns: (1fr, 1fr),
    [
      #text(weight: "bold", size: 14pt)[{{ company.name }}]
    ],
    align(right)[
      #text(size: 28pt, weight: "bold", fill: primary, tracking: 0.5pt)[STATEMENT]
      #v(4pt)
      #block(width: 100%, fill: accent, radius: 2pt, inset: (x: 10pt, y: 5pt))[
        #text(size: 9pt, fill: white, weight: "bold")[{{ customer.account_number }}]
        #h(1fr)
        #text(size: 9pt, fill: white)[{{ statement_date }}]
      ]
    ],
  )
]

#line(length: 100%, stroke: 1.5pt + accent)
#v(16pt)

// ══════════════════════════════════════════════════════════════
// SUMMARY CARDS
// ══════════════════════════════════════════════════════════════

#grid(
  columns: (1fr, 1fr, 1fr, 1fr),
  gutter: 10pt,
  block(width: 100%, fill: light-bg, radius: 4pt, inset: (x: 10pt, y: 10pt))[
    #text(size: 7pt, weight: "bold", fill: muted, tracking: 0.8pt)[PERIOD]
    #v(4pt)
    #text(size: 9pt, weight: "bold")[{{ period }}]
  ],
  block(width: 100%, fill: light-bg, radius: 4pt, inset: (x: 10pt, y: 10pt))[
    #text(size: 7pt, weight: "bold", fill: muted, tracking: 0.8pt)[OPENING]
    #v(4pt)
    #text(size: 9pt, weight: "bold")[{{ opening_balance }}]
  ],
  block(width: 100%, fill: light-bg, radius: 4pt, inset: (x: 10pt, y: 10pt))[
    #text(size: 7pt, weight: "bold", fill: muted, tracking: 0.8pt)[ACTIVITY]
    #v(4pt)
    #text(size: 9pt, weight: "bold")[{{ total_charges }} / {{ total_payments }}]
  ],
  block(width: 100%, fill: primary, radius: 4pt, inset: (x: 10pt, y: 10pt))[
    #text(size: 7pt, weight: "bold", fill: white.transparentize(40%), tracking: 0.8pt)[CLOSING]
    #v(4pt)
    #text(size: 11pt, weight: "bold", fill: white)[{{ closing_balance }}]
  ],
)

#v(16pt)

// ══════════════════════════════════════════════════════════════
// ADDRESSES
// ══════════════════════════════════════════════════════════════

#grid(
  columns: (1fr, 1fr),
  gutter: 0.5in,
  [
    #block(width: 100%, stroke: (left: 3pt + accent), inset: (left: 12pt, y: 4pt))[
      #text(size: 7pt, weight: "bold", fill: muted, tracking: 0.8pt)[FROM]
      #v(6pt)
      #text(weight: "bold")[{{ company.name }}]
      #v(3pt)
      {{ company.address }}
      #v(4pt)
      #text(size: 8.5pt, fill: muted)[{{ company.email }} · {{ company.phone }}]
    ]
  ],
  [
    #block(width: 100%, stroke: (left: 3pt + rule-light), inset: (left: 12pt, y: 4pt))[
      #text(size: 7pt, weight: "bold", fill: muted, tracking: 0.8pt)[ACCOUNT HOLDER]
      #v(6pt)
      #text(weight: "bold")[{{ customer.name }}]
      #v(3pt)
      {{ customer.address }}
      #v(4pt)
      #text(size: 8.5pt, fill: muted)[{{ customer.email }}]
    ]
  ],
)

#v(20pt)

// ══════════════════════════════════════════════════════════════
// TRANSACTIONS
// ══════════════════════════════════════════════════════════════

#text(size: 7pt, weight: "bold", fill: muted, tracking: 0.8pt)[TRANSACTIONS]
#v(8pt)

#table(
  columns: (60pt, 70pt, 1fr, 80pt, 80pt),
  stroke: none,
  inset: (x: 6pt, y: 7pt),
  fill: (_, row) => if row == 0 { primary } else if calc.odd(row) { light-bg } else { none },

  text(size: 7.5pt, weight: "bold", fill: white, tracking: 0.5pt)[DATE],
  text(size: 7.5pt, weight: "bold", fill: white, tracking: 0.5pt)[REFERENCE],
  text(size: 7.5pt, weight: "bold", fill: white, tracking: 0.5pt)[DESCRIPTION],
  align(right, text(size: 7.5pt, weight: "bold", fill: white, tracking: 0.5pt)[AMOUNT]),
  align(right, text(size: 7.5pt, weight: "bold", fill: white, tracking: 0.5pt)[BALANCE]),

{% for txn in transactions %}
  [{{ txn.date }}],
  [#text(size: 8pt, fill: muted)[{{ txn.reference }}]],
  [{{ txn.description }}],
  align(right)[{% if txn.amount.startswith("-") %}#text(fill: red)[{{ txn.amount }}]{% else %}{{ txn.amount }}{% endif %}],
  align(right)[#text(weight: "bold")[{{ txn.balance }}]],
{% endfor %}
)

#v(20pt)

// ══════════════════════════════════════════════════════════════
// AGING SUMMARY
// ══════════════════════════════════════════════════════════════

#text(size: 7pt, weight: "bold", fill: muted, tracking: 0.8pt)[AGING SUMMARY]
#v(8pt)

#align(right)[
  #table(
    columns: (auto, auto, auto, auto, auto),
    stroke: 0.5pt + rule-light,
    inset: (x: 12pt, y: 8pt),
    align: right,
    fill: (col, _) => if col == 4 { light-bg } else { none },

    table.header(
      text(size: 7.5pt, weight: "bold", fill: muted)[CURRENT],
      text(size: 7.5pt, weight: "bold", fill: muted)[31\u201360 DAYS],
      text(size: 7.5pt, weight: "bold", fill: muted)[61\u201390 DAYS],
      text(size: 7.5pt, weight: "bold", fill: muted)[OVER 90],
      text(size: 7.5pt, weight: "bold", fill: primary)[TOTAL],
    ),
    [{{ aging.current }}],
    [{{ aging.days_30 }}],
    [{{ aging.days_60 }}],
    [{{ aging.days_90 }}],
    [#text(weight: "bold", fill: accent)[{{ aging.total }}]],
  )
]

#v(20pt)

// ══════════════════════════════════════════════════════════════
// NOTES
// ══════════════════════════════════════════════════════════════

#block(width: 100%, fill: light-bg, radius: 4pt, inset: (x: 14pt, y: 12pt))[
  #text(size: 7pt, weight: "bold", fill: muted, tracking: 0.8pt)[NOTES]
  #v(5pt)
  #text(size: 8.5pt)[{{ notes }}]
]

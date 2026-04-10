// Account Statement template
// Tests: multi-page tables, repeated headers, opening/closing balance,
// negative values, long descriptions, aging summary

#set page(
  paper: "us-letter",
  margin: (top: 1.2in, bottom: 1in, left: 0.75in, right: 0.75in),
  header: context {
    if counter(page).get().first() > 1 {
      grid(
        columns: (1fr, 1fr),
        align(left, text(size: 8pt, fill: luma(120))[{{ company.name }}]),
        align(right, text(size: 8pt, fill: luma(120))[
          Account: {{ customer.account_number }} #h(1em) Statement (continued)
        ]),
      )
    }
  },
  footer: {% include "fragments/footer_page.j2.typ" %},
)

#set text(size: 9.5pt, font: "Inter")

// --- Header ---
#grid(
  columns: (1fr, 1fr),
  align(left, image("assets/logo.png", width: 1.5in)),
  align(right)[
    #text(size: 22pt, weight: "bold")[STATEMENT]
    #v(4pt)
    #text(size: 9pt, fill: luma(100))[{{ statement_date }}]
  ],
)

#v(0.25in)

// --- Company / Customer ---
#grid(
  columns: (1fr, 1fr),
  gutter: 0.4in,
  [
    #text(weight: "bold")[{{ company.name }}] \
    {{ company.address_line1 }} \
    {{ company.address_line2 }} \
    {{ company.email }} \
    {{ company.phone }}
  ],
  [
    #text(weight: "bold")[Account Holder:] \
    {{ customer.name }} \
    Account: {{ customer.account_number }} \
    {{ customer.address_line1 }} \
    {{ customer.address_line2 }}
  ],
)

#v(0.15in)

// --- Period and Summary ---
#grid(
  columns: (1fr, 1fr, 1fr, 1fr),
  inset: 6pt,
  align(center)[
    #text(size: 8pt, fill: luma(100))[PERIOD] \
    #text(weight: "bold")[{{ period }}]
  ],
  align(center)[
    #text(size: 8pt, fill: luma(100))[OPENING BALANCE] \
    #text(weight: "bold")[{{ opening_balance }}]
  ],
  align(center)[
    #text(size: 8pt, fill: luma(100))[TOTAL ACTIVITY] \
    #text(weight: "bold")[{{ total_charges }} / {{ total_payments }}]
  ],
  align(center)[
    #text(size: 8pt, fill: luma(100))[CLOSING BALANCE] \
    #text(weight: "bold", size: 11pt)[{{ closing_balance }}]
  ],
)

#v(0.2in)

// --- Transaction Table ---
#table(
  columns: (auto, auto, 3fr, auto, 1fr, 1fr),
  stroke: none,
  inset: (x: 6pt, y: 5pt),

  table.header(
    table.cell(fill: luma(235))[*Date*],
    table.cell(fill: luma(235))[*Ref*],
    table.cell(fill: luma(235))[*Description*],
    table.cell(fill: luma(235))[],
    table.cell(fill: luma(235), align(right)[*Amount*]),
    table.cell(fill: luma(235), align(right)[*Balance*]),
  ),
  table.hline(stroke: 0.5pt),
{% for txn in transactions %}
  [{{ txn.date }}],
  [#text(size: 8pt)[{{ txn.reference }}]],
  [{{ txn.description }}],
  [],
  align(right)[{% if txn.amount.startswith("-") %}#text(fill: rgb("#c0392b"))[{{ txn.amount }}]{% else %}{{ txn.amount }}{% endif %}],
  align(right)[*{{ txn.balance }}*],
  table.hline(stroke: 0.3pt + luma(220)),
{% endfor %}
)

#v(0.2in)

// --- Aging Summary ---
#align(right)[
  #text(weight: "bold", size: 10pt)[Aging Summary]
  #v(4pt)
  #table(
    columns: (auto, auto, auto, auto, auto),
    stroke: 0.5pt + luma(200),
    inset: (x: 10pt, y: 5pt),
    align: right,
    table.header(
      [*Current*], [*31-60 Days*], [*61-90 Days*], [*Over 90 Days*], [*Total*],
    ),
    [{{ aging.current }}], [{{ aging.days_30 }}], [{{ aging.days_60 }}], [{{ aging.days_90 }}], [*{{ aging.total }}*],
  )
]

#v(0.3in)

// --- Notes ---
#line(length: 100%, stroke: 0.5pt + luma(200))
#v(0.1in)
#text(size: 8.5pt, fill: luma(100))[{{ notes }}]

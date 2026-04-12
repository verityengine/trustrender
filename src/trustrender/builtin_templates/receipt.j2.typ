// Receipt template - compact thermal-style layout
// Tests: narrow width, tax lines, payment method, wrapping item names

#let primary = rgb("#1B2838")
#let accent = rgb("#C4622A")
#let muted = rgb("#7A7670")
#let light-bg = rgb("#F8F7F5")
#let rule-light = rgb("#E5E2DD")

#set page(
  width: 3.5in,
  height: auto,
  margin: (top: 0.3in, bottom: 0.3in, left: 0.25in, right: 0.25in),
)

#set text(size: 8.5pt, font: "Inter", fill: primary)

// ══════════════════════════════════════════════════════════════
// HEADER
// ══════════════════════════════════════════════════════════════

#align(center)[
  #text(weight: "bold", size: 12pt)[{{ company.name }}]
  #v(3pt)
  #text(size: 7.5pt, fill: muted)[
    {{ company.address }} \
    {{ company.phone }}{% if company.website %} · {{ company.website }}{% endif %}
  ]
]

#v(10pt)
#block(width: 100%, fill: primary, inset: (x: 8pt, y: 5pt), radius: 2pt)[
  #grid(
    columns: (1fr, auto),
    text(size: 8pt, fill: white, weight: "bold")[{{ receipt_number }}],
    text(size: 8pt, fill: white)[{{ date }} {{ time }}],
  )
]
#v(6pt)

#grid(
  columns: (1fr, 1fr),
  text(size: 7.5pt, fill: muted)[Cashier: {{ cashier }}],
  align(right, text(size: 7.5pt, fill: muted)[Register: {{ register }}]),
)

#v(8pt)
#line(length: 100%, stroke: 0.5pt + rule-light)
#v(8pt)

// ══════════════════════════════════════════════════════════════
// ITEMS
// ══════════════════════════════════════════════════════════════

{% for item in items %}
#grid(
  columns: (1fr, auto),
  gutter: 4pt,
  [#text(weight: "bold")[{{ item.description }}]],
  align(right)[#text(weight: "bold")[{{ item.amount }}]],
)
#text(size: 7pt, fill: muted)[#h(0.1in) {{ item.qty }} × {{ item.unit_price }}]
#v(6pt)
{% endfor %}

#v(4pt)
#line(length: 100%, stroke: 0.5pt + rule-light)
#v(6pt)

// ══════════════════════════════════════════════════════════════
// TOTALS
// ══════════════════════════════════════════════════════════════

#grid(
  columns: (1fr, auto),
  row-gutter: 4pt,
  text(fill: muted)[Subtotal], align(right)[{{ subtotal }}],
  text(fill: muted)[{{ tax_label }}], align(right)[{{ tax_amount }}],
)

#v(6pt)
#line(length: 100%, stroke: 1.2pt + accent)
#v(6pt)

#grid(
  columns: (1fr, auto),
  [#text(weight: "bold", size: 13pt)[TOTAL]],
  align(right)[#text(weight: "bold", size: 13pt, fill: accent)[{{ total }}]],
)

#v(10pt)
#line(length: 100%, stroke: 0.5pt + rule-light)
#v(8pt)

// ══════════════════════════════════════════════════════════════
// PAYMENT
// ══════════════════════════════════════════════════════════════

#block(width: 100%, fill: light-bg, radius: 3pt, inset: (x: 10pt, y: 8pt))[
  #grid(
    columns: (1fr, auto),
    row-gutter: 3pt,
    [{{ payment.method }} ····{{ payment.last_four }}], align(right)[{{ amount_tendered }}],
    text(size: 7pt, fill: muted)[Auth: {{ payment.auth_code }}], [],
  )
{% if change_due != "$0.00" %}
  #v(4pt)
  #grid(
    columns: (1fr, auto),
    text(weight: "bold")[Change Due], align(right, text(weight: "bold")[{{ change_due }}]),
  )
{% endif %}
]

#v(12pt)

// ══════════════════════════════════════════════════════════════
// FOOTER
// ══════════════════════════════════════════════════════════════

#align(center)[
  #text(size: 9pt, weight: "bold", fill: accent)[{{ footer_message }}]
  #v(8pt)
  #text(size: 6.5pt, fill: muted)[
    {{ company.name }} · {{ company.address }}
  ]
]

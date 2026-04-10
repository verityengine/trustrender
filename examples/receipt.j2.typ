// Receipt template - compact layout
// Tests: narrow width, tax lines, payment method, wrapping item names

#set page(
  width: 3.5in,
  height: auto,
  margin: (top: 0.3in, bottom: 0.3in, left: 0.25in, right: 0.25in),
)

#set text(size: 8.5pt, font: "Inter")

// --- Header ---
#align(center)[
  #image("assets/logo.png", width: 1in)
  #v(4pt)
  #text(weight: "bold", size: 11pt)[{{ company.name }}]
  #v(2pt)
  #text(size: 7.5pt, fill: luma(100))[
    {{ company.address_line1 }} \
    {{ company.address_line2 }} \
    {{ company.phone }}
  ]
]

#v(0.1in)
#line(length: 100%, stroke: (dash: "dashed", thickness: 0.5pt, paint: luma(180)))
#v(0.05in)

// --- Receipt Meta ---
#grid(
  columns: (1fr, 1fr),
  [Receipt: *{{ receipt_number }}*],
  align(right)[{{ date }}],
)
#grid(
  columns: (1fr, 1fr),
  [Cashier: {{ cashier }}],
  align(right)[{{ time }}],
)

#v(0.05in)
#line(length: 100%, stroke: (dash: "dashed", thickness: 0.5pt, paint: luma(180)))
#v(0.08in)

// --- Items ---
{% for item in items %}
#grid(
  columns: (1fr, auto),
  gutter: 4pt,
  [{{ item.description }}],
  align(right)[{{ item.amount }}],
)
#text(size: 7.5pt, fill: luma(120))[#h(0.15in) {{ item.qty }} x {{ item.unit_price }}]
#v(4pt)
{% endfor %}

#v(0.05in)
#line(length: 100%, stroke: 0.5pt + luma(200))
#v(0.05in)

// --- Totals ---
#grid(
  columns: (1fr, auto),
  row-gutter: 3pt,
  [Subtotal], align(right)[{{ subtotal }}],
  [{{ tax_label }}], align(right)[{{ tax_amount }}],
)

#v(0.05in)
#line(length: 100%, stroke: 0.8pt)
#v(0.05in)

#grid(
  columns: (1fr, auto),
  [#text(weight: "bold", size: 11pt)[TOTAL]], align(right)[#text(weight: "bold", size: 11pt)[{{ total }}]],
)

#v(0.08in)
#line(length: 100%, stroke: (dash: "dashed", thickness: 0.5pt, paint: luma(180)))
#v(0.08in)

// --- Payment ---
#grid(
  columns: (1fr, auto),
  row-gutter: 3pt,
  [{{ payment.method }} ending {{ payment.last_four }}], align(right)[{{ amount_tendered }}],
  [Auth: {{ payment.auth_code }}], [],
)
{% if change_due != "$0.00" %}
#grid(
  columns: (1fr, auto),
  [Change Due], align(right)[{{ change_due }}],
)
{% endif %}

#v(0.1in)
#line(length: 100%, stroke: (dash: "dashed", thickness: 0.5pt, paint: luma(180)))
#v(0.1in)

// --- Footer ---
#align(center)[
  #text(size: 7.5pt, fill: luma(100))[
    {{ footer_message }}
  ]
  #v(6pt)
  #text(size: 7pt, fill: luma(150))[
    {{ company.website }} \
    Register: {{ register }}
  ]
]

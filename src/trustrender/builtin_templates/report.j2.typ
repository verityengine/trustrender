// Report template - structured business report
// Tests: section headings, summary metrics, tables, conditional formatting

#let primary = rgb("#1B2838")
#let accent = rgb("#C4622A")
#let muted = rgb("#7A7670")
#let light-bg = rgb("#F8F7F5")
#let rule-light = rgb("#E5E2DD")
#let green = rgb("#4A7C59")
#let blue = rgb("#2D6A8F")
#let red = rgb("#B83A2A")

#set page(
  paper: "us-letter",
  margin: (top: 0.8in, bottom: 1in, left: 0.9in, right: 0.9in),
  header: context {
    if counter(page).get().first() > 1 {
      grid(
        columns: (1fr, 1fr),
        align(left, text(size: 7.5pt, fill: muted, font: "Inter")[{{ company.name }} / {{ company.department }}]),
        align(right, text(size: 7.5pt, fill: muted, font: "Inter")[{{ title }}]),
      )
    }
  },
  footer: context align(center, text(size: 7.5pt, fill: muted, font: "Inter")[
    Page #counter(page).display("1") of #counter(page).final().at(0)
  ]),
)

#set text(size: 9.5pt, font: "Inter", fill: primary)
#set par(leading: 0.7em)

// ══════════════════════════════════════════════════════════════
// TITLE
// ══════════════════════════════════════════════════════════════

#grid(
  columns: (1fr, 1fr),
  gutter: 0.2in,
  text(weight: "bold", size: 14pt)[{{ company.name }}],
  align(right + bottom)[
    #text(size: 7.5pt, fill: muted)[{{ company.name }} / {{ company.department }}]
  ],
)

#v(0.25in)

#text(size: 24pt, weight: "bold", fill: primary)[{{ title }}]
#v(4pt)
#text(size: 12pt, fill: muted)[{{ subtitle }}]

#v(12pt)

#grid(
  columns: (1fr, 1fr, 1fr),
  gutter: 10pt,
  block(fill: light-bg, radius: 3pt, inset: (x: 10pt, y: 8pt), width: 100%)[
    #text(size: 7pt, weight: "bold", fill: muted, tracking: 0.8pt)[PERIOD]
    #v(3pt)
    #text(weight: "bold")[{{ period }}]
  ],
  block(fill: light-bg, radius: 3pt, inset: (x: 10pt, y: 8pt), width: 100%)[
    #text(size: 7pt, weight: "bold", fill: muted, tracking: 0.8pt)[DATE]
    #v(3pt)
    #text(weight: "bold")[{{ date }}]
  ],
  block(fill: light-bg, radius: 3pt, inset: (x: 10pt, y: 8pt), width: 100%)[
    #text(size: 7pt, weight: "bold", fill: muted, tracking: 0.8pt)[PREPARED BY]
    #v(3pt)
    #text(weight: "bold")[{{ prepared_by }}]
  ],
)

#v(12pt)
#line(length: 100%, stroke: 1.5pt + accent)
#v(16pt)

// ══════════════════════════════════════════════════════════════
// EXECUTIVE SUMMARY
// ══════════════════════════════════════════════════════════════

#text(size: 7pt, weight: "bold", fill: accent, tracking: 0.8pt)[EXECUTIVE SUMMARY]
#v(8pt)

#block(width: 100%, stroke: (left: 3pt + accent), inset: (left: 12pt, y: 4pt))[
  #text(size: 10pt)[{{ executive_summary }}]
]

#v(20pt)

// ══════════════════════════════════════════════════════════════
// KEY METRICS
// ══════════════════════════════════════════════════════════════

#text(size: 7pt, weight: "bold", fill: accent, tracking: 0.8pt)[KEY METRICS]
#v(8pt)

#table(
  columns: (1fr, 80pt, 80pt, 70pt),
  stroke: none,
  inset: (x: 8pt, y: 8pt),
  fill: (_, row) => if row == 0 { primary } else if calc.odd(row) { light-bg } else { none },

  text(size: 7.5pt, weight: "bold", fill: white, tracking: 0.5pt)[METRIC],
  align(right, text(size: 7.5pt, weight: "bold", fill: white, tracking: 0.5pt)[ACTUAL]),
  align(right, text(size: 7.5pt, weight: "bold", fill: white, tracking: 0.5pt)[TARGET]),
  align(center, text(size: 7.5pt, weight: "bold", fill: white, tracking: 0.5pt)[STATUS]),

{% for m in metrics %}
  [{{ m.label }}],
  align(right)[#text(weight: "bold")[{{ m.value }}]],
  align(right)[{{ m.target }}],
  align(center)[{% if m.status == "above" %}#text(fill: green, weight: "bold")[Above]{% elif m.status == "met" %}#text(fill: blue, weight: "bold")[Met]{% else %}#text(fill: red, weight: "bold")[Below]{% endif %}],
{% endfor %}
)

#v(20pt)

// ══════════════════════════════════════════════════════════════
// INCIDENTS
// ══════════════════════════════════════════════════════════════

#text(size: 7pt, weight: "bold", fill: accent, tracking: 0.8pt)[INCIDENT SUMMARY]
#v(8pt)

{% for inc in incidents %}
#block(
  width: 100%,
  inset: (x: 12pt, y: 10pt),
  stroke: (left: 3pt + {% if inc.severity == "P1" %}red{% else %}accent{% endif %}),
  fill: light-bg,
  radius: (right: 4pt),
)[
  #grid(
    columns: (auto, 1fr, auto),
    [#text(weight: "bold")[{{ inc.id }}] #h(8pt) #text(size: 8pt, fill: {% if inc.severity == "P1" %}red{% else %}accent{% endif %}, weight: "bold")[{{ inc.severity }}]],
    [],
    [#text(size: 8.5pt, fill: muted)[{{ inc.date }} · {{ inc.duration }}]],
  )
  #v(6pt)
  {{ inc.description }}
  #v(4pt)
  #text(size: 8.5pt, fill: muted)[*Root cause:* {{ inc.root_cause }}]
  #v(2pt)
  #text(size: 8.5pt, fill: muted)[*Resolution:* {{ inc.resolution }}]
]
#v(8pt)
{% endfor %}

#v(12pt)

// ══════════════════════════════════════════════════════════════
// CLOUD SPEND
// ══════════════════════════════════════════════════════════════

#text(size: 7pt, weight: "bold", fill: accent, tracking: 0.8pt)[CLOUD SPEND BY SERVICE]
#v(8pt)

#table(
  columns: (1fr, 80pt, 80pt, 70pt),
  stroke: none,
  inset: (x: 8pt, y: 8pt),
  fill: (_, row) => if row == 0 { primary } else if calc.odd(row) { light-bg } else { none },

  text(size: 7.5pt, weight: "bold", fill: white, tracking: 0.5pt)[SERVICE],
  align(right, text(size: 7.5pt, weight: "bold", fill: white, tracking: 0.5pt)[Q1 2026]),
  align(right, text(size: 7.5pt, weight: "bold", fill: white, tracking: 0.5pt)[Q4 2025]),
  align(right, text(size: 7.5pt, weight: "bold", fill: white, tracking: 0.5pt)[CHANGE]),

{% for s in spend_by_service %}
  [{{ s.service }}],
  align(right)[{{ s.q1_spend }}],
  align(right)[{{ s.q4_spend }}],
  align(right)[{% if s.change.startswith("-") %}#text(fill: green, weight: "bold")[{{ s.change }}]{% else %}#text(fill: red)[{{ s.change }}]{% endif %}],
{% endfor %}
)

#v(20pt)

// ══════════════════════════════════════════════════════════════
// RECOMMENDATIONS
// ══════════════════════════════════════════════════════════════

#text(size: 7pt, weight: "bold", fill: accent, tracking: 0.8pt)[RECOMMENDATIONS]
#v(8pt)

{% for rec in recommendations %}
#block(width: 100%, inset: (left: 12pt, y: 3pt))[
  #grid(
    columns: (16pt, 1fr),
    text(fill: accent, weight: "bold")[{{ loop.index }}.],
    [{{ rec }}],
  )
]
{% endfor %}

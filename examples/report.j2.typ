// Report template - structured business report
// Tests: section headings, summary metrics, tables, conditional formatting, multi-page

#set page(
  paper: "us-letter",
  margin: (top: 1in, bottom: 1in, left: 1in, right: 1in),
  header: context {
    if counter(page).get().first() > 1 {
      grid(
        columns: (1fr, 1fr),
        align(left, text(size: 8pt, fill: luma(120))[{{ company.name }} / {{ company.department }}]),
        align(right, text(size: 8pt, fill: luma(120))[{{ title }}]),
      )
    }
  },
  footer: context align(center, text(size: 8pt, fill: luma(120))[
    Page #counter(page).display("1 of 1", both: true)
  ]),
)

#set text(size: 10pt, font: "Inter")
#set par(leading: 0.65em)

// --- Title Page Area ---
#grid(
  columns: (auto, 1fr),
  gutter: 0.2in,
  image("assets/logo.png", width: 1.2in),
  align(right + bottom)[
    #text(size: 9pt, fill: luma(100))[{{ company.name }} / {{ company.department }}]
  ],
)

#v(0.3in)

#text(size: 20pt, weight: "bold")[{{ title }}]
#v(4pt)
#text(size: 12pt, fill: luma(80))[{{ subtitle }}]

#v(0.15in)

#grid(
  columns: (auto, auto, auto),
  column-gutter: 0.4in,
  [#text(size: 9pt, fill: luma(100))[Period:] *{{ period }}*],
  [#text(size: 9pt, fill: luma(100))[Date:] *{{ date }}*],
  [#text(size: 9pt, fill: luma(100))[Prepared by:] *{{ prepared_by }}*],
)

#v(0.3in)
#line(length: 100%, stroke: 1pt + luma(200))
#v(0.2in)

// --- Executive Summary ---
== Executive Summary

{{ executive_summary }}

#v(0.2in)

// --- Key Metrics ---
== Key Metrics

#table(
  columns: (2fr, 1fr, 1fr, 1fr),
  stroke: none,
  inset: (x: 8pt, y: 6pt),

  table.header(
    table.cell(fill: luma(235))[*Metric*],
    table.cell(fill: luma(235), align(right)[*Actual*]),
    table.cell(fill: luma(235), align(right)[*Target*]),
    table.cell(fill: luma(235), align(center)[*Status*]),
  ),
  table.hline(stroke: 0.5pt),
{% for m in metrics %}
  [{{ m.label }}],
  align(right)[*{{ m.value }}*],
  align(right)[{{ m.target }}],
  align(center)[{% if m.status == "above" %}#text(fill: rgb("#27ae60"))[Above]{% elif m.status == "met" %}#text(fill: rgb("#2980b9"))[Met]{% else %}#text(fill: rgb("#c0392b"))[Below]{% endif %}],
  table.hline(stroke: 0.3pt + luma(220)),
{% endfor %}
)

#v(0.2in)

// --- Incident Summary ---
== Incident Summary

{% for inc in incidents %}
#block(
  width: 100%,
  inset: 10pt,
  stroke: (left: 3pt + {% if inc.severity == "P1" %}rgb("#e74c3c"){% else %}rgb("#f39c12"){% endif %}),
  fill: luma(248),
)[
  #grid(
    columns: (auto, 1fr, auto),
    [*{{ inc.id }}*],
    [],
    [#text(size: 9pt)[{{ inc.date }} #h(0.5em) Duration: {{ inc.duration }}]],
  )
  #v(4pt)
  #text(size: 9.5pt)[{{ inc.description }}]
  #v(4pt)
  #text(size: 9pt, fill: luma(80))[*Root cause:* {{ inc.root_cause }}]
  #v(2pt)
  #text(size: 9pt, fill: luma(80))[*Resolution:* {{ inc.resolution }}]
]
#v(0.1in)
{% endfor %}

// --- Cloud Spend ---
== Cloud Spend by Service

#table(
  columns: (2.5fr, 1fr, 1fr, 1fr),
  stroke: none,
  inset: (x: 8pt, y: 6pt),

  table.header(
    table.cell(fill: luma(235))[*Service*],
    table.cell(fill: luma(235), align(right)[*Q1 2026*]),
    table.cell(fill: luma(235), align(right)[*Q4 2025*]),
    table.cell(fill: luma(235), align(right)[*Change*]),
  ),
  table.hline(stroke: 0.5pt),
{% for s in spend_by_service %}
  [{{ s.service }}],
  align(right)[{{ s.q1_spend }}],
  align(right)[{{ s.q4_spend }}],
  align(right)[{% if s.change.startswith("-") %}#text(fill: rgb("#27ae60"))[{{ s.change }}]{% else %}{{ s.change }}{% endif %}],
  table.hline(stroke: 0.3pt + luma(220)),
{% endfor %}
)

#v(0.2in)

// --- Recommendations ---
== Recommendations

{% for rec in recommendations %}
+ {{ rec }}
{% endfor %}

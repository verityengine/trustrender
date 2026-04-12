// Business letter template
// Tests: text-first layout, sender/recipient blocks, paragraphs, signature

#let primary = rgb("#1B2838")
#let accent = rgb("#C4622A")
#let muted = rgb("#7A7670")
#let light-bg = rgb("#F8F7F5")
#let rule-light = rgb("#E5E2DD")

#set page(
  paper: "us-letter",
  margin: (top: 0.9in, bottom: 1in, left: 1.1in, right: 1.1in),
  footer: context {
    if counter(page).get().first() > 1 {
      align(center, text(size: 7.5pt, fill: muted, font: "Inter")[
        Page #counter(page).display("1") of #counter(page).final().at(0)
      ])
    }
  },
)

#set text(size: 10.5pt, font: "Inter", fill: primary)
#set par(leading: 0.75em, justify: true)

// ══════════════════════════════════════════════════════════════
// LETTERHEAD
// ══════════════════════════════════════════════════════════════

#grid(
  columns: (1fr, 1fr),
  gutter: 0.2in,
  text(weight: "bold", size: 14pt)[{{ sender.name }}],
  align(right)[
    #text(size: 8.5pt, fill: muted)[
      {{ sender.address }} \
      {{ sender.phone }} · {{ sender.email }}
    ]
  ],
)

#v(4pt)
#line(length: 100%, stroke: 1pt + accent)

#v(0.35in)

// ══════════════════════════════════════════════════════════════
// DATE
// ══════════════════════════════════════════════════════════════

#text(fill: muted)[{{ date }}]

#v(0.3in)

// ══════════════════════════════════════════════════════════════
// RECIPIENT
// ══════════════════════════════════════════════════════════════

#block(stroke: (left: 3pt + rule-light), inset: (left: 12pt))[
  #text(weight: "bold")[{{ recipient.name }}] \
  {{ recipient.title }} \
  {{ recipient.company }} \
  {{ recipient.address }}
]

#v(0.3in)

// ══════════════════════════════════════════════════════════════
// SUBJECT
// ══════════════════════════════════════════════════════════════

#text(weight: "bold", size: 11pt)[Re: {{ subject }}]

#v(0.25in)

// ══════════════════════════════════════════════════════════════
// BODY
// ══════════════════════════════════════════════════════════════

{{ salutation }}

#v(0.15in)

{% for paragraph in body_paragraphs %}
{{ paragraph }}

{% if not loop.last %}
#v(0.12in)
{% endif %}
{% endfor %}

#v(0.35in)

// ══════════════════════════════════════════════════════════════
// CLOSING + SIGNATURE
// ══════════════════════════════════════════════════════════════

{{ closing }}

#v(0.5in)

#block(stroke: (bottom: 1pt + rule-light), inset: (bottom: 4pt))[
  #text(weight: "bold")[{{ signature_name }}]
]
#v(3pt)
#text(size: 9pt, fill: muted)[{{ signature_title }}] \
#text(size: 9pt, fill: muted)[{{ signature_company }}]

{% if enclosures %}
#v(0.35in)
#line(length: 100%, stroke: 0.5pt + rule-light)
#v(8pt)

#text(size: 9pt, weight: "bold", fill: muted)[Enclosures:]
{% for enc in enclosures %}
#text(size: 9pt, fill: muted)[· {{ enc }}]
{% endfor %}
{% endif %}

{% if cc %}
#v(0.15in)
#text(size: 9pt, weight: "bold", fill: muted)[cc:]
{% for person in cc %}
#text(size: 9pt, fill: muted)[· {{ person }}]
{% endfor %}
{% endif %}

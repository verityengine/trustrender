// Business letter template
// Tests: text-first layout, sender/recipient blocks, paragraphs, signature, spacing

#set page(
  paper: "us-letter",
  margin: (top: 1in, bottom: 1in, left: 1.25in, right: 1.25in),
  footer: context {
    if counter(page).get().first() > 1 {
      align(center, text(size: 8pt, fill: luma(120))[
        Page #counter(page).display("1 of 1", both: true)
      ])
    }
  },
)

#set text(size: 11pt, font: "Inter")
#set par(leading: 0.7em, justify: true)

// --- Letterhead ---
#grid(
  columns: (auto, 1fr),
  gutter: 0.2in,
  image("assets/logo.png", width: 1in),
  align(right)[
    #text(weight: "bold", size: 12pt)[{{ sender.name }}] \
    #text(size: 9pt, fill: luma(100))[
      {{ sender.address_line1 }} \
      {{ sender.address_line2 }} \
      {{ sender.phone }} #h(1em) {{ sender.email }}
    ]
  ],
)

#v(0.4in)

// --- Date ---
{{ date }}

#v(0.3in)

// --- Recipient ---
{{ recipient.name }} \
{{ recipient.title }} \
{{ recipient.company }} \
{{ recipient.address_line1 }} \
{{ recipient.address_line2 }}

#v(0.3in)

// --- Subject ---
*Re: {{ subject }}*

#v(0.2in)

// --- Salutation ---
{{ salutation }}

#v(0.15in)

// --- Body ---
{% for paragraph in body_paragraphs %}
{{ paragraph }}

{% if not loop.last %}
#v(0.1in)
{% endif %}
{% endfor %}

#v(0.3in)

// --- Closing ---
{{ closing }}

#v(0.6in)

// --- Signature Block ---
*{{ signature_name }}* \
{{ signature_title }} \
{{ signature_company }}

{% if enclosures %}
#v(0.3in)

// --- Enclosures ---
#text(size: 9.5pt)[
  *Enclosures:*
  {% for enc in enclosures %}
  - {{ enc }}
  {% endfor %}
]
{% endif %}

{% if cc %}
#v(0.15in)

// --- CC ---
#text(size: 9.5pt)[
  *cc:*
  {% for person in cc %}
  - {{ person }}
  {% endfor %}
]
{% endif %}

// Invoice template - Jinja2 preprocessed
// Data flows: JSON -> Jinja2 -> Typst markup -> PDF

#set page(
  paper: "us-letter",
  margin: (top: 1.2in, bottom: 1in, left: 1in, right: 1in),
  header: align(right, text(size: 8pt, fill: luma(120))[T]),
  footer: context align(center, text(size: 8pt, fill: luma(120))[
  Page #counter(page).display("1 of 1", both: true)
]),
)

#set text(size: 10pt, font: "Inter")

// --- Logo and Invoice Title ---



#grid(
  columns: (1fr, 1fr),
  align(left, image("assets/logo.png", width: 1.5in)),
  align(right)[
    #text(size: 24pt, weight: "bold")[INVOICE]
    #v(4pt)
    #text(size: 10pt, fill: luma(100))[Invoice \#T]
  ],
)

#v(0.3in)

// --- Sender / Recipient ---
#grid(
  columns: (1fr, 1fr),
  gutter: 0.5in,
  [
    #text(weight: "bold")[From:]
    #v(4pt)
    T \
     \
     \
    
  ],
  [
    #text(weight: "bold")[Bill To:]
    #v(4pt)
    T \
     \
     \
    
  ],
)

#v(0.2in)

// --- Invoice Details ---
#grid(
  columns: (1fr, 1fr, 1fr),
  [
    #text(weight: "bold")[Invoice Date] \
    T
  ],
  [
    #text(weight: "bold")[Due Date] \
    T
  ],
  [
    #text(weight: "bold")[Payment Terms] \
    T
  ],
)

#v(0.3in)

// --- Line Items Table ---
#table(
  columns: (auto, 3fr, 1fr, 1fr, 1fr),
  stroke: none,
  inset: (x: 8pt, y: 6pt),

  table.header(
    table.cell(fill: luma(240))[*\#*],
    table.cell(fill: luma(240))[*Description*],
    table.cell(fill: luma(240), align(right)[*Qty*]),
    table.cell(fill: luma(240), align(right)[*Unit Price*]),
    table.cell(fill: luma(240), align(right)[*Amount*]),
  ),
  table.hline(stroke: 0.5pt),

)

#v(0.2in)

// --- Totals ---
#align(right)[
  #grid(
    columns: (auto, 120pt),
    row-gutter: 6pt,
    align(right)[Subtotal:], align(right)[0],
    align(right)[Tax (0):], align(right)[0],
    grid.hline(stroke: 0.5pt),
    align(right)[#text(weight: "bold", size: 12pt)[Total Due:]], align(right)[#text(weight: "bold", size: 12pt)[0]],
  )
]

#v(0.4in)

// --- Notes ---
#line(length: 100%, stroke: 0.5pt + luma(200))
#v(0.1in)
#text(size: 9pt, fill: luma(100))[
  *Notes:* 
]

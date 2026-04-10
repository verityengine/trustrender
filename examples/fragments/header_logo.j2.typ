#grid(
  columns: (1fr, 1fr),
  align(left, image("{{ logo_path }}", width: 1.5in)),
  align(right)[
    #text(size: 24pt, weight: "bold")[{{ doc_title }}]
    #v(4pt)
    #text(size: 10pt, fill: luma(100))[{{ doc_subtitle }}]
  ],
)
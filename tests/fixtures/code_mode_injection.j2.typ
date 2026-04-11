// Deliberately vulnerable template for injection POC testing.
// This template places user data in a Typst code-mode string context.
// DO NOT use this pattern in production templates.
#set page(paper: "us-letter", margin: 1in)
#set text(size: 12pt)

// Code-mode string interpolation (vulnerable if data contains unescaped quotes)
#let doc_title = "{{ title }}"

= #doc_title

{{ body }}

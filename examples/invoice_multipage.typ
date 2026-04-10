// Multi-page invoice - 45 line items, tests pagination and repeated headers
// Tests: page breaks, repeated table headers, footer on every page, row wrapping

#set page(
  paper: "us-letter",
  margin: (top: 1.2in, bottom: 1in, left: 1in, right: 1in),
  header: context {
    if counter(page).get().first() > 1 {
      grid(
        columns: (1fr, 1fr),
        align(left, text(size: 8pt, fill: luma(120))[Acme Corporation]),
        align(right, text(size: 8pt, fill: luma(120))[Invoice \#INV-2026-0042 (continued)]),
      )
    }
  },
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
    #text(size: 10pt, fill: luma(100))[Invoice \#INV-2026-0042]
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
    Acme Corporation \
    123 Business Ave, Suite 400 \
    San Francisco, CA 94105 \
    billing\@acme.com
  ],
  [
    #text(weight: "bold")[Bill To:]
    #v(4pt)
    Contoso Ltd. \
    456 Enterprise Blvd \
    New York, NY 10001 \
    accounts\@contoso.com
  ],
)

#v(0.2in)

// --- Invoice Details ---
#grid(
  columns: (1fr, 1fr, 1fr),
  [
    #text(weight: "bold")[Invoice Date] \
    April 10, 2026
  ],
  [
    #text(weight: "bold")[Due Date] \
    May 10, 2026
  ],
  [
    #text(weight: "bold")[Payment Terms] \
    Net 30
  ],
)

#v(0.3in)

// --- Line Items Table (45 items) ---
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

  [1], [Website redesign and development], align(right)[1], align(right)[\$4,500.00], align(right)[\$4,500.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [2], [Logo design and brand identity package], align(right)[1], align(right)[\$2,200.00], align(right)[\$2,200.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [3], [SEO optimization and keyword research], align(right)[1], align(right)[\$1,800.00], align(right)[\$1,800.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [4], [Social media content creation (monthly)], align(right)[3], align(right)[\$750.00], align(right)[\$2,250.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [5], [Email marketing campaign setup], align(right)[1], align(right)[\$1,200.00], align(right)[\$1,200.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [6], [Analytics dashboard configuration], align(right)[1], align(right)[\$950.00], align(right)[\$950.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [7], [Content writing - blog posts (batch of 5)], align(right)[5], align(right)[\$300.00], align(right)[\$1,500.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [8], [Photography and professional image editing], align(right)[1], align(right)[\$800.00], align(right)[\$800.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [9], [Hosting setup and DNS configuration], align(right)[1], align(right)[\$350.00], align(right)[\$350.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [10], [Staff training session and documentation delivery], align(right)[2], align(right)[\$500.00], align(right)[\$1,000.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [11], [Database migration and optimization], align(right)[1], align(right)[\$3,200.00], align(right)[\$3,200.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [12], [API development and integration], align(right)[1], align(right)[\$5,500.00], align(right)[\$5,500.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [13], [Security audit and penetration testing], align(right)[1], align(right)[\$4,000.00], align(right)[\$4,000.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [14], [SSL certificate setup and configuration], align(right)[2], align(right)[\$150.00], align(right)[\$300.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [15], [Mobile responsive design adjustments], align(right)[1], align(right)[\$1,800.00], align(right)[\$1,800.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [16], [Payment gateway integration (Stripe)], align(right)[1], align(right)[\$2,000.00], align(right)[\$2,000.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [17], [User authentication system implementation], align(right)[1], align(right)[\$3,500.00], align(right)[\$3,500.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [18], [Automated email notification system], align(right)[1], align(right)[\$1,500.00], align(right)[\$1,500.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [19], [CRM integration and data sync], align(right)[1], align(right)[\$2,800.00], align(right)[\$2,800.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [20], [Performance optimization and caching], align(right)[1], align(right)[\$1,600.00], align(right)[\$1,600.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [21], [Accessibility compliance (WCAG 2.1 AA)], align(right)[1], align(right)[\$2,400.00], align(right)[\$2,400.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [22], [Search functionality implementation], align(right)[1], align(right)[\$1,800.00], align(right)[\$1,800.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [23], [Admin dashboard development], align(right)[1], align(right)[\$4,200.00], align(right)[\$4,200.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [24], [Data export and reporting module], align(right)[1], align(right)[\$2,000.00], align(right)[\$2,000.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [25], [Multi-language support (i18n)], align(right)[3], align(right)[\$800.00], align(right)[\$2,400.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [26], [Inventory management module], align(right)[1], align(right)[\$3,800.00], align(right)[\$3,800.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [27], [Order processing workflow automation], align(right)[1], align(right)[\$2,600.00], align(right)[\$2,600.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [28], [Customer portal development], align(right)[1], align(right)[\$5,000.00], align(right)[\$5,000.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [29], [Webhook integration for third-party services], align(right)[4], align(right)[\$600.00], align(right)[\$2,400.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [30], [Automated backup system configuration], align(right)[1], align(right)[\$900.00], align(right)[\$900.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [31], [Load testing and scalability assessment], align(right)[1], align(right)[\$1,500.00], align(right)[\$1,500.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [32], [Docker containerization and deployment], align(right)[1], align(right)[\$2,200.00], align(right)[\$2,200.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [33], [CI/CD pipeline setup (GitHub Actions)], align(right)[1], align(right)[\$1,400.00], align(right)[\$1,400.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [34], [Monitoring and alerting configuration], align(right)[1], align(right)[\$1,100.00], align(right)[\$1,100.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [35], [Custom reporting dashboard], align(right)[1], align(right)[\$3,000.00], align(right)[\$3,000.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [36], [Data visualization components], align(right)[6], align(right)[\$450.00], align(right)[\$2,700.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [37], [User onboarding flow design and implementation], align(right)[1], align(right)[\$2,500.00], align(right)[\$2,500.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [38], [Notification preferences management], align(right)[1], align(right)[\$800.00], align(right)[\$800.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [39], [Role-based access control system], align(right)[1], align(right)[\$2,800.00], align(right)[\$2,800.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [40], [Audit logging and compliance tracking], align(right)[1], align(right)[\$1,600.00], align(right)[\$1,600.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [41], [API rate limiting and throttling], align(right)[1], align(right)[\$700.00], align(right)[\$700.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [42], [File upload and document management], align(right)[1], align(right)[\$1,900.00], align(right)[\$1,900.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [43], [Two-factor authentication implementation], align(right)[1], align(right)[\$1,200.00], align(right)[\$1,200.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [44], [Scheduled task and job queue system], align(right)[1], align(right)[\$2,100.00], align(right)[\$2,100.00],
  table.hline(stroke: 0.3pt + luma(200)),
  [45], [Final QA testing, bug fixes, and deployment support with extended warranty coverage and documentation handoff], align(right)[1], align(right)[\$3,500.00], align(right)[\$3,500.00],
)

#v(0.2in)

// --- Totals ---
#align(right)[
  #grid(
    columns: (auto, 120pt),
    row-gutter: 6pt,
    align(right)[Subtotal:], align(right)[\$102,450.00],
    align(right)[Tax (8.5%):], align(right)[\$8,708.25],
    grid.hline(stroke: 0.5pt),
    align(right)[#text(weight: "bold", size: 12pt)[Total Due:]], align(right)[#text(weight: "bold", size: 12pt)[\$111,158.25]],
  )
]

#v(0.4in)

// --- Notes ---
#line(length: 100%, stroke: 0.5pt + luma(200))
#v(0.1in)
#text(size: 9pt, fill: luma(100))[
  *Notes:* Payment is due within 30 days. Please include the invoice number with your payment.
  For questions, contact billing\@acme.com.
]

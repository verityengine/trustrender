import { useState, useEffect, useRef } from 'react'

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   TRUSTRENDER — Product site
   Validate Stripe / Shopify / custom billing data before
   Factur-X / ZUGFeRD embedding.
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */

const REPO = 'https://github.com/verityengine/trustrender'
const PYPI = 'https://pypi.org/project/trustrender/'

/* ── Scroll reveal wrapper ─────────────────────────────────────── */
function FadeUp({ children, delay = 0, className = '' }) {
  const ref = useRef(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            setTimeout(() => el.classList.add('vis'), delay)
            io.unobserve(el)
          }
        })
      },
      { threshold: 0.12 }
    )
    io.observe(el)
    return () => io.disconnect()
  }, [delay])
  return (
    <div ref={ref} className={`fade-up ${className}`}>
      {children}
    </div>
  )
}

/* ── Copy-to-clipboard pill ────────────────────────────────────── */
function CopyPill({ text, dark = false }) {
  const [copied, setCopied] = useState(false)
  const onClick = () => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1400)
  }
  const cls = dark
    ? 'border-panel/15 hover:border-panel/30 bg-panel/[0.05] hover:bg-panel/[0.08] text-panel/80'
    : 'border-rule-light hover:border-mid/40 bg-panel hover:bg-white text-ink-2'
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-3 px-5 py-2.5 rounded-full border transition-colors cursor-pointer group ${cls}`}
    >
      <code className="font-mono text-[13px]">{text}</code>
      <span
        className={`text-[10px] uppercase tracking-wider transition-colors ${
          dark ? 'text-panel/30 group-hover:text-panel/60' : 'text-muted group-hover:text-ink-2'
        }`}
      >
        {copied ? 'copied' : 'copy'}
      </span>
    </button>
  )
}

/* ── Terminal-style block (for static demo outputs) ────────────── */
function Terminal({ filename, children, status = null }) {
  return (
    <div className="bg-ink-3 rounded-xl border border-panel/10 overflow-hidden shadow-sm">
      <div className="px-4 py-2.5 border-b border-panel/10 flex items-center gap-2">
        <div className="flex gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full bg-panel/15" />
          <div className="w-2.5 h-2.5 rounded-full bg-panel/15" />
          <div className="w-2.5 h-2.5 rounded-full bg-panel/15" />
        </div>
        {filename && (
          <span className="text-[11px] font-mono text-panel/50 ml-2">{filename}</span>
        )}
        {status && (
          <span
            className={`ml-auto text-[10px] uppercase tracking-wider font-mono ${
              status === 'pass'
                ? 'text-sage-light'
                : status === 'block'
                  ? 'text-rust-light'
                  : 'text-panel/40'
            }`}
          >
            {status === 'pass' ? '● PASS' : status === 'block' ? '● BLOCKED' : status}
          </span>
        )}
      </div>
      <pre className="px-5 py-4 text-[12.5px] font-mono leading-[1.6] text-panel/85 overflow-x-auto whitespace-pre">
        {children}
      </pre>
    </div>
  )
}

/* ── Section wrapper ───────────────────────────────────────────── */
function Section({ id, kicker, title, lede, children, light = true, narrow = false }) {
  return (
    <section
      id={id}
      className={`py-20 md:py-28 ${light ? 'bg-bg' : 'bg-ink text-panel'}`}
    >
      <div className={`mx-auto px-6 md:px-10 ${narrow ? 'max-w-4xl' : 'max-w-[1200px]'}`}>
        <FadeUp>
          {kicker && (
            <p
              className={`text-[11px] tracking-[0.22em] uppercase mb-4 font-semibold ${
                light ? 'text-rust' : 'text-rust-light'
              }`}
            >
              {kicker}
            </p>
          )}
          <h2
            className={`font-display font-extrabold text-[28px] md:text-[40px] tracking-[-0.03em] leading-[1.08] mb-5 max-w-3xl ${
              light ? 'text-ink' : 'text-panel'
            }`}
          >
            {title}
          </h2>
          {lede && (
            <p
              className={`text-[16px] md:text-[17px] leading-relaxed max-w-2xl mb-12 ${
                light ? 'text-mid' : 'text-panel/65'
              }`}
            >
              {lede}
            </p>
          )}
        </FadeUp>
        {children}
      </div>
    </section>
  )
}

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   HEADER
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
function Header() {
  return (
    <header className="absolute top-0 left-0 right-0 z-50 bg-ink/80 backdrop-blur-md border-b border-panel/5">
      <div className="max-w-[1280px] mx-auto px-6 md:px-10 py-4 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-md bg-rust/20 border border-rust/30 flex items-center justify-center">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
              <path d="M3 3h7l3 3v7H3V3z" stroke="#d4783e" strokeWidth="1.4" strokeLinejoin="round" />
              <path d="M5.5 9l1.5 1.5L10 7.5" stroke="#d4783e" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <span className="font-display font-bold text-panel text-[18px] tracking-tight">TrustRender</span>
        </div>
        <nav className="flex items-center gap-2">
          <a
            href={PYPI}
            target="_blank"
            rel="noopener noreferrer"
            className="hidden md:inline-flex text-[13px] text-panel/70 hover:text-panel px-3 py-2 transition-colors"
          >
            PyPI
          </a>
          <a
            href={REPO}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[13px] text-panel border border-panel/20 hover:border-panel/40 hover:bg-panel/[0.06] px-4 py-2 rounded-full transition-colors"
          >
            GitHub
          </a>
        </nav>
      </div>
    </header>
  )
}

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   HERO
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
function Hero() {
  return (
    <section
      className="text-panel relative overflow-hidden pt-28 md:pt-32 pb-16 md:pb-24"
      style={{
        background:
          'radial-gradient(ellipse 80% 60% at 50% 30%, rgba(196,98,42,0.12) 0%, transparent 70%), linear-gradient(180deg, #141618 0%, #111214 40%, #0f1012 100%)',
      }}
    >
      <div className="max-w-[1200px] mx-auto px-6 md:px-10 relative z-10">
        <div className="text-center max-w-4xl mx-auto hero-stagger">
          <p className="text-[11px] tracking-[0.22em] uppercase text-rust-light font-semibold mb-6">
            Stripe · Shopify · Custom billing  →  Factur-X / ZUGFeRD
          </p>
          <h1 className="font-display font-extrabold text-[40px] md:text-[64px] lg:text-[78px] leading-[0.98] tracking-[-0.04em] gradient-text pb-2">
            Validate billing data before it becomes a non&#8209;compliant invoice.
          </h1>
          <p className="text-[16px] md:text-[18px] text-panel/55 max-w-2xl mx-auto mt-6 leading-relaxed">
            TrustRender catches missing seller fields, arithmetic mismatches, and
            structural problems in Stripe and Shopify exports — before
            <code className="mx-1 px-1.5 py-0.5 rounded bg-panel/[0.08] text-panel/80 font-mono text-[13px]">factur-x</code>
            or
            <code className="mx-1 px-1.5 py-0.5 rounded bg-panel/[0.08] text-panel/80 font-mono text-[13px]">drafthorse</code>
            embed them as compliant XML.
          </p>
          <div className="mt-8 flex flex-col items-center gap-3">
            <CopyPill text="pip install trustrender" dark />
            <p className="text-[12px] text-panel/35 font-mono">v0.3.4 · MIT · Python 3.11+</p>
          </div>
        </div>

        {/* The proof: blocked → pass terminal flow */}
        <FadeUp delay={400}>
          <div className="mt-14 md:mt-20 grid grid-cols-1 lg:grid-cols-2 gap-6 max-w-5xl mx-auto">
            <Terminal filename="$ trustrender validate demo_stripe.json --source stripe" status="block">
{`Invoice:   INV-2026-0187
From:
To:        Rheingold Maschinenbau GmbH
Items:     3
Total:     €2,945.25

BLOCKED — 1 problem(s)

  Missing vendor/sender name
    Add a sender.name field to your invoice data.

This invoice cannot be processed
until the problems above are fixed.`}
            </Terminal>
            <Terminal filename="$ trustrender validate demo_stripe_ready.json --source stripe" status="pass">
{`Invoice:   INV-2026-0187
From:      NovaTech Solutions GmbH
To:        Rheingold Maschinenbau GmbH
Items:     3
Total:     €2,945.25

PASS — invoice data is valid

Safe to embed in Factur-X/ZUGFeRD PDF.`}
            </Terminal>
          </div>
          <p className="text-center text-[13px] text-panel/45 mt-6">
            The only difference between the two files is one added field:&nbsp;
            <code className="font-mono text-panel/75 bg-panel/[0.06] px-2 py-0.5 rounded">
              "sender": &#123; "name": "NovaTech Solutions GmbH" &#125;
            </code>
          </p>
        </FadeUp>
      </div>
    </section>
  )
}

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   WHY THIS EXISTS
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
function WhyExists() {
  return (
    <Section
      id="why"
      kicker="The gap"
      title="Stripe and Shopify don't generate compliant invoices."
      lede="They send you billing exports — cents in integers, Unix timestamps, decimal-string amounts, no seller info, no concept of EU tax compliance. factur-x and drafthorse generate compliant Factur-X / ZUGFeRD XML, but they assume clean canonical input. TrustRender is the validation and normalization layer in between."
    >
      <FadeUp delay={150}>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6">
          {[
            {
              n: '1',
              title: 'Adapt',
              body: 'Convert raw Stripe / Shopify payloads into canonical structure. Cents → euros, Unix → ISO dates, strings → floats.',
            },
            {
              n: '2',
              title: 'Validate',
              body: 'Check arithmetic, identity, structure. Catch missing seller fields, broken line totals, mismatched subtotals.',
            },
            {
              n: '3',
              title: 'Hand off',
              body: 'Pass the canonical dict to factur-x or drafthorse. They generate the compliant XML, you trust the input.',
            },
          ].map((step) => (
            <div
              key={step.n}
              className="p-6 rounded-xl border border-rule-light bg-panel"
            >
              <div className="flex items-baseline gap-3 mb-3">
                <span className="font-display text-[28px] font-extrabold text-rust leading-none">
                  {step.n}
                </span>
                <h3 className="font-display font-bold text-[18px] text-ink">
                  {step.title}
                </h3>
              </div>
              <p className="text-[14px] leading-relaxed text-mid">{step.body}</p>
            </div>
          ))}
        </div>
      </FadeUp>
    </Section>
  )
}

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ADAPTERS — Stripe + Shopify side by side
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
function Adapters() {
  return (
    <Section
      id="adapters"
      kicker="Adapters"
      title="Bring your own billing platform."
      lede="Each adapter knows the platform's quirks — Stripe's cents, Shopify's decimal strings, Unix timestamps, ISO 8601 — and produces a canonical invoice dict ready for validation."
      light={false}
    >
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <FadeUp delay={100}>
          <div className="bg-ink-3 border border-panel/10 rounded-xl p-7">
            <div className="flex items-baseline justify-between mb-4">
              <h3 className="font-display font-bold text-[22px] text-panel">Stripe</h3>
              <code className="text-[12px] font-mono text-panel/40">--source stripe</code>
            </div>
            <ul className="space-y-2.5 text-[14px] text-panel/70 mb-5">
              <li className="flex gap-3">
                <span className="text-rust-light">→</span>
                <span>cents <code className="font-mono text-panel/50">247500</code> become euros <code className="font-mono text-panel/50">2475.00</code></span>
              </li>
              <li className="flex gap-3">
                <span className="text-rust-light">→</span>
                <span>Unix timestamps <code className="font-mono text-panel/50">1775779200</code> become dates <code className="font-mono text-panel/50">2026-04-10</code></span>
              </li>
              <li className="flex gap-3">
                <span className="text-rust-light">→</span>
                <span>line items extracted from <code className="font-mono text-panel/50">lines.data[]</code></span>
              </li>
              <li className="flex gap-3">
                <span className="text-rust-light">→</span>
                <span>customer maps to recipient; sender stays empty (Stripe doesn't have it)</span>
              </li>
            </ul>
            <Terminal>
{`from trustrender import validate_invoice
from trustrender.adapters import from_stripe

result = validate_invoice(
    from_stripe(stripe_invoice),
    zugferd=True,
)`}
            </Terminal>
          </div>
        </FadeUp>

        <FadeUp delay={200}>
          <div className="bg-ink-3 border border-panel/10 rounded-xl p-7">
            <div className="flex items-baseline justify-between mb-4">
              <h3 className="font-display font-bold text-[22px] text-panel">Shopify</h3>
              <code className="text-[12px] font-mono text-panel/40">--source shopify</code>
            </div>
            <ul className="space-y-2.5 text-[14px] text-panel/70 mb-5">
              <li className="flex gap-3">
                <span className="text-rust-light">→</span>
                <span>decimal strings <code className="font-mono text-panel/50">"1100.00"</code> become floats <code className="font-mono text-panel/50">1100.00</code></span>
              </li>
              <li className="flex gap-3">
                <span className="text-rust-light">→</span>
                <span>ISO 8601 <code className="font-mono text-panel/50">"2026-04-08T14:30+02:00"</code> becomes <code className="font-mono text-panel/50">2026-04-08</code></span>
              </li>
              <li className="flex gap-3">
                <span className="text-rust-light">→</span>
                <span><code className="font-mono text-panel/50">first_name + last_name</code> joined into recipient</span>
              </li>
              <li className="flex gap-3">
                <span className="text-rust-light">→</span>
                <span>line totals computed from <code className="font-mono text-panel/50">qty × price</code> when missing</span>
              </li>
            </ul>
            <Terminal>
{`from trustrender import validate_invoice
from trustrender.adapters import from_shopify

result = validate_invoice(
    from_shopify(shopify_order),
)`}
            </Terminal>
          </div>
        </FadeUp>
      </div>

      <FadeUp delay={300}>
        <p className="text-center text-[13px] text-panel/45 mt-10">
          Custom billing system?  Pass the dict directly to{' '}
          <code className="font-mono text-panel/70">validate_invoice()</code> — 90+
          field aliases (DocNumber, invoiceNo, vendor.companyName…) resolve to canonical names automatically.
        </p>
      </FadeUp>
    </Section>
  )
}

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   WHAT IT CHECKS
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
function WhatItChecks() {
  const checks = [
    { rule: 'identity.invoice_number', desc: 'Missing or empty invoice number' },
    { rule: 'identity.sender_name', desc: 'Missing vendor / sender name' },
    { rule: 'identity.recipient_name', desc: 'Missing recipient / buyer name' },
    { rule: 'items.non_empty', desc: 'No line items present' },
    { rule: 'arithmetic.line_total', desc: 'line_total ≠ quantity × unit_price' },
    { rule: 'arithmetic.subtotal', desc: 'subtotal ≠ sum of line_totals' },
    { rule: 'arithmetic.total', desc: 'total ≠ subtotal + tax_amount' },
  ]
  return (
    <Section
      id="checks"
      kicker="Validation"
      title="Seven deterministic checks. No AI. No heuristics."
      lede="Every rule is objectively verifiable. Either the math works or it doesn't. Either the field exists or it doesn't. No surprises in production."
    >
      <FadeUp delay={150}>
        <div className="rounded-xl border border-rule-light bg-panel overflow-hidden">
          {checks.map((c, i) => (
            <div
              key={c.rule}
              className={`grid grid-cols-[minmax(200px,260px)_1fr] gap-6 px-6 py-4 ${
                i !== checks.length - 1 ? 'border-b border-rule-light' : ''
              }`}
            >
              <code className="font-mono text-[13px] text-rust">{c.rule}</code>
              <span className="text-[14px] text-ink-2">{c.desc}</span>
            </div>
          ))}
        </div>
        <p className="text-[13px] text-muted mt-6 max-w-2xl">
          When <code className="font-mono">--zugferd</code> is set, additional EN
          16931 readiness checks run: tax-rate consistency, currency, country
          codes, supported document types (380 invoices, 381 credit notes).
        </p>
      </FadeUp>
    </Section>
  )
}

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   END-TO-END PYTHON EXAMPLE
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
function EndToEnd() {
  return (
    <Section
      id="example"
      kicker="In your code"
      title="Three lines between Stripe and a compliant Factur-X invoice."
      lede="Adapter normalizes the platform quirks. Validator returns a canonical dict and a list of any blocking issues. You hand the canonical dict to factur-x or drafthorse for XML embedding."
      light={false}
      narrow
    >
      <FadeUp delay={150}>
        <Terminal filename="integration.py">
{`from trustrender import validate_invoice
from trustrender.adapters import from_stripe

# 1. Pull a Stripe invoice (raw API response)
stripe_invoice = stripe.Invoice.retrieve("in_1RExNk...")

# 2. Adapt + validate (one call)
result = validate_invoice(
    from_stripe(stripe_invoice.to_dict()),
    zugferd=True,
)

# 3. Hand off the canonical dict — or surface the blocking errors
if result["render_ready"] and result["zugferd_ready"]:
    canonical = result["canonical"]
    # ... your factur-x / drafthorse generation code here
else:
    for error in result["errors"]:
        print(f"BLOCKED: {error['message']}")`}
        </Terminal>
        <div className="mt-8 flex flex-wrap gap-3 justify-center">
          <CopyPill text="pip install trustrender" dark />
          <a
            href={`${REPO}/blob/main/examples/start_to_finish.py`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full border border-panel/15 hover:border-panel/30 bg-panel/[0.05] hover:bg-panel/[0.08] text-panel/80 transition-colors text-[13px]"
          >
            See the full example  ↗
          </a>
        </div>
      </FadeUp>
    </Section>
  )
}

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   STATS / TRUST
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
function Stats() {
  const stats = [
    { value: '993', label: 'tests passing' },
    { value: '90+', label: 'field aliases' },
    { value: 'EN 16931', label: 'compliance path' },
    { value: 'Pure Python', label: 'no Java, no browser' },
  ]
  return (
    <section className="py-16 md:py-20 bg-bg border-y border-rule-light">
      <div className="max-w-[1200px] mx-auto px-6 md:px-10">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
          {stats.map((s, i) => (
            <FadeUp key={s.label} delay={i * 80}>
              <div className="text-center md:text-left">
                <div className="font-display font-extrabold text-[30px] md:text-[38px] text-ink leading-none mb-1.5 tracking-tight">
                  {s.value}
                </div>
                <div className="text-[12px] tracking-[0.18em] uppercase text-mid font-semibold">
                  {s.label}
                </div>
              </div>
            </FadeUp>
          ))}
        </div>
      </div>
    </section>
  )
}

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   SCOPE — what it is / isn't
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
function Scope() {
  return (
    <Section
      id="scope"
      kicker="Honest scope"
      title="Narrow. Deterministic. Boring on purpose."
      lede="TrustRender is a focused validation layer, not an AP automation platform. It does one thing well: catch billing-data problems before they become non-compliant XML."
    >
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <FadeUp delay={100}>
          <div>
            <h3 className="font-display font-bold text-[18px] text-ink mb-4 flex items-center gap-2">
              <span className="text-sage">●</span> What it is
            </h3>
            <ul className="space-y-3 text-[14px] text-ink-2">
              {[
                'Validation + normalization for Stripe / Shopify / custom billing data',
                'Adapter layer — handles platform-specific formats',
                'Pre-flight check before factur-x / drafthorse embedding',
                'EN 16931 readiness scan (German B2B path)',
                'Deterministic rule set — same input, same output, every time',
              ].map((x) => (
                <li key={x} className="flex gap-3">
                  <span className="text-sage mt-1">·</span>
                  <span>{x}</span>
                </li>
              ))}
            </ul>
          </div>
        </FadeUp>
        <FadeUp delay={200}>
          <div>
            <h3 className="font-display font-bold text-[18px] text-ink mb-4 flex items-center gap-2">
              <span className="text-wine">●</span> What it isn't
            </h3>
            <ul className="space-y-3 text-[14px] text-mid">
              {[
                'A full AP automation platform',
                'An e-invoicing compliance certification',
                'An AI-powered data fixer (every rule is deterministic)',
                'A replacement for factur-x or drafthorse — it runs before them',
                'Cross-border, reverse-charge, or non-EUR currency support (yet)',
              ].map((x) => (
                <li key={x} className="flex gap-3">
                  <span className="text-wine mt-1">·</span>
                  <span>{x}</span>
                </li>
              ))}
            </ul>
          </div>
        </FadeUp>
      </div>
    </Section>
  )
}

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   FINAL CTA
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
function FinalCTA() {
  return (
    <section className="py-24 md:py-32 bg-ink text-panel">
      <div className="max-w-3xl mx-auto px-6 md:px-10 text-center">
        <FadeUp>
          <h2 className="font-display font-extrabold text-[34px] md:text-[52px] tracking-[-0.03em] leading-[1.05] mb-6">
            Catch the problem at the data layer,<br />not at the customer.
          </h2>
          <p className="text-[16px] md:text-[17px] text-panel/55 max-w-xl mx-auto mb-9 leading-relaxed">
            Open source. MIT-licensed. No accounts, no SaaS, no telemetry. Just a
            Python package that validates billing data before it becomes a broken
            invoice.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-3">
            <CopyPill text="pip install trustrender" dark />
            <a
              href={REPO}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full border border-panel/15 hover:border-panel/30 bg-panel/[0.05] hover:bg-panel/[0.08] text-panel/80 transition-colors text-[13px]"
            >
              View on GitHub  ↗
            </a>
          </div>
        </FadeUp>
      </div>
    </section>
  )
}

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   FOOTER
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
function Footer() {
  return (
    <footer className="bg-ink-2 border-t border-panel/5 text-panel/55 py-10">
      <div className="max-w-[1200px] mx-auto px-6 md:px-10 flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2.5">
          <div className="w-5 h-5 rounded bg-rust/20 border border-rust/30 flex items-center justify-center">
            <svg width="10" height="10" viewBox="0 0 16 16" fill="none">
              <path d="M3 3h7l3 3v7H3V3z" stroke="#d4783e" strokeWidth="1.6" strokeLinejoin="round" />
              <path d="M5.5 9l1.5 1.5L10 7.5" stroke="#d4783e" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <span className="text-[13px] text-panel/70">TrustRender · by Verity Engine</span>
        </div>
        <nav className="flex items-center gap-5 text-[12px]">
          <a href={REPO} target="_blank" rel="noopener noreferrer" className="hover:text-panel transition-colors">
            GitHub
          </a>
          <a href={PYPI} target="_blank" rel="noopener noreferrer" className="hover:text-panel transition-colors">
            PyPI
          </a>
          <a href={`${REPO}/blob/main/README.md`} target="_blank" rel="noopener noreferrer" className="hover:text-panel transition-colors">
            Docs
          </a>
          <span className="text-panel/30">MIT</span>
        </nav>
      </div>
    </footer>
  )
}

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   APP
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
export default function App() {
  return (
    <div className="min-h-screen">
      <Header />
      <Hero />
      <WhyExists />
      <Adapters />
      <Stats />
      <WhatItChecks />
      <EndToEnd />
      <Scope />
      <FinalCTA />
      <Footer />
    </div>
  )
}

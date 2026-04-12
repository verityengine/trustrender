import { useState, useEffect, useRef, useCallback } from 'react'
import * as pdfjsLib from 'pdfjs-dist'
import pdfjsWorker from 'pdfjs-dist/build/pdf.worker.mjs?url'
import JSZip from 'jszip'
import CodeEditor from './CodeEditor.jsx'
import { buildPathIndex } from './json-path-index.js'
import { resolveErrorLocation } from './error-resolver.js'

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfjsWorker

const API_BASE = import.meta.env.VITE_API_BASE || ''
const apiUrl = (path) => `${API_BASE}${path}`

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   TRUSTRENDER — Product site
   Art direction: editorial charcoal meets document precision
   Display: DM Serif Display / Body: Inter / Code: JetBrains Mono
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */

/* ── Animated SVG: Document Particle Field (hero background) ──────── */
function DocumentField() {
  const canvasRef = useRef(null)
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    let raf
    let particles = []
    const resize = () => { canvas.width = canvas.offsetWidth * 2; canvas.height = canvas.offsetHeight * 2; ctx.scale(2, 2) }
    resize()
    window.addEventListener('resize', resize)

    // Generate particles: tiny document fragments, data points, and connection lines
    for (let i = 0; i < 60; i++) {
      particles.push({
        x: Math.random() * canvas.offsetWidth,
        y: Math.random() * canvas.offsetHeight,
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.2,
        size: Math.random() * 3 + 1,
        type: Math.random() > 0.7 ? 'doc' : Math.random() > 0.5 ? 'check' : 'dot',
        opacity: Math.random() * 0.15 + 0.05,
        phase: Math.random() * Math.PI * 2,
        speed: Math.random() * 0.005 + 0.002,
      })
    }

    const w = () => canvas.offsetWidth
    const h = () => canvas.offsetHeight

    function draw(t) {
      ctx.clearRect(0, 0, w(), h())

      // Draw connections between nearby particles
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x
          const dy = particles[i].y - particles[j].y
          const dist = Math.sqrt(dx * dx + dy * dy)
          if (dist < 120) {
            ctx.beginPath()
            ctx.moveTo(particles[i].x, particles[i].y)
            ctx.lineTo(particles[j].x, particles[j].y)
            ctx.strokeStyle = `rgba(250,248,245,${0.03 * (1 - dist / 120)})`
            ctx.lineWidth = 0.5
            ctx.stroke()
          }
        }
      }

      particles.forEach(p => {
        p.x += p.vx
        p.y += p.vy
        p.phase += p.speed
        const pulse = Math.sin(p.phase) * 0.5 + 0.5
        const alpha = p.opacity * (0.6 + pulse * 0.4)

        if (p.x < -10) p.x = w() + 10
        if (p.x > w() + 10) p.x = -10
        if (p.y < -10) p.y = h() + 10
        if (p.y > h() + 10) p.y = -10

        ctx.save()
        ctx.globalAlpha = alpha
        ctx.translate(p.x, p.y)

        if (p.type === 'doc') {
          // Tiny document icon
          ctx.strokeStyle = 'rgba(250,248,245,0.6)'
          ctx.lineWidth = 0.8
          ctx.strokeRect(-3, -4, 6, 8)
          ctx.beginPath()
          ctx.moveTo(-1.5, -1); ctx.lineTo(1.5, -1)
          ctx.moveTo(-1.5, 1); ctx.lineTo(1.5, 1)
          ctx.stroke()
        } else if (p.type === 'check') {
          // Tiny checkmark
          ctx.strokeStyle = 'rgba(47,110,138,0.7)'
          ctx.lineWidth = 1
          ctx.beginPath()
          ctx.moveTo(-2, 0); ctx.lineTo(-0.5, 1.5); ctx.lineTo(2.5, -2)
          ctx.stroke()
        } else {
          // Data dot
          ctx.fillStyle = `rgba(250,248,245,${0.4 + pulse * 0.3})`
          ctx.beginPath()
          ctx.arc(0, 0, p.size * 0.5, 0, Math.PI * 2)
          ctx.fill()
        }
        ctx.restore()
      })

      raf = requestAnimationFrame(draw)
    }
    raf = requestAnimationFrame(draw)
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', resize) }
  }, [])

  return <canvas ref={canvasRef} className="absolute inset-0 w-full h-full pointer-events-none" style={{ opacity: 0.6 }} />
}

/* ── Animated Logo ────────────────────────────────────────────────── */
function AnimatedLogo({ size = 'default', animate = false }) {
  const checkRef = useRef(null)
  const lineRefs = [useRef(null), useRef(null), useRef(null)]

  useEffect(() => {
    if (!animate) return
    // Animate data lines drawing in
    lineRefs.forEach((ref, i) => {
      const el = ref.current
      if (!el) return
      const len = el.getTotalLength()
      el.style.strokeDasharray = len
      el.style.strokeDashoffset = len
      el.getBoundingClientRect()
      el.style.transition = `stroke-dashoffset ${0.3}s ease-out ${0.3 + i * 0.15}s`
      el.style.strokeDashoffset = '0'
    })
    // Animate check mark
    if (checkRef.current) {
      const el = checkRef.current
      const len = el.getTotalLength()
      el.style.strokeDasharray = len
      el.style.strokeDashoffset = len
      el.getBoundingClientRect()
      el.style.transition = `stroke-dashoffset 0.35s ease-out 0.85s`
      el.style.strokeDashoffset = '0'
    }
  }, [animate])

  const s = size === 'small' ? 'h-7' : 'h-9'
  return (
    <div className="flex items-center gap-2.5">
      <svg className={`${s} aspect-square`} viewBox="0 0 36 36" fill="none">
        {/* Document body */}
        <rect x="4" y="2" width="22" height="28" rx="2.5" stroke="currentColor" strokeWidth="1.8" opacity="0.5" />
        {/* Dog ear fold */}
        <path d="M20 2v6h6" stroke="currentColor" strokeWidth="1.5" opacity="0.3" strokeLinecap="round" strokeLinejoin="round" />
        {/* Data lines */}
        <line ref={lineRefs[0]} x1="9" y1="13" x2="21" y2="13" stroke="currentColor" strokeWidth="1.8" opacity="0.6" strokeLinecap="round" />
        <line ref={lineRefs[1]} x1="9" y1="17.5" x2="18" y2="17.5" stroke="currentColor" strokeWidth="1.5" opacity="0.35" strokeLinecap="round" />
        <line ref={lineRefs[2]} x1="9" y1="22" x2="19.5" y2="22" stroke="currentColor" strokeWidth="1.5" opacity="0.35" strokeLinecap="round" />
        {/* Verification badge circle */}
        <circle cx="26" cy="26" r="8.5" fill="#c4622a" opacity="0.95" />
        {/* Check mark */}
        <path ref={checkRef} d="M22.5 26l2.5 2.5L29.5 24" stroke="white" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
      </svg>
      <span className={`font-display tracking-[-0.02em] ${size === 'small' ? 'text-[18px]' : 'text-[24px]'}`}>TrustRender</span>
    </div>
  )
}

/* ── Trust Layer Flourish: Readiness (canvas-rendered) ────────────── */
function ReadinessFlourish() {
  const canvasRef = useRef(null)
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const dpr = window.devicePixelRatio || 1
    const W = 560, H = 360
    canvas.width = W * dpr; canvas.height = H * dpr
    canvas.style.width = W + 'px'; canvas.style.height = H + 'px'
    ctx.scale(dpr, dpr)
    let raf, t = 0

    const fields = ['sender.name','sender.email','recipient.name','items[]','items[].qty','items[].amount','subtotal','tax_rate','total','notes']
    const gateX = 420

    function draw() {
      t += 0.012
      ctx.clearRect(0, 0, W, H)

      // Gate line with glow
      ctx.save()
      ctx.strokeStyle = 'rgba(196,98,42,0.15)'
      ctx.lineWidth = 1
      ctx.setLineDash([6, 4])
      ctx.beginPath(); ctx.moveTo(gateX, 0); ctx.lineTo(gateX, H); ctx.stroke()
      ctx.setLineDash([])
      // Gate glow
      const gateGlow = ctx.createLinearGradient(gateX - 20, 0, gateX + 20, 0)
      gateGlow.addColorStop(0, 'rgba(196,98,42,0)')
      gateGlow.addColorStop(0.5, 'rgba(196,98,42,0.04)')
      gateGlow.addColorStop(1, 'rgba(196,98,42,0)')
      ctx.fillStyle = gateGlow
      ctx.fillRect(gateX - 20, 0, 40, H)
      ctx.restore()

      // Fields streaming through
      fields.forEach((name, i) => {
        const cycleT = (t + i * 0.15) % 3
        const y = 20 + i * 33
        const progress = Math.min(cycleT / 0.8, 1)
        const passed = name !== 'tax_rate' || Math.sin(t * 2) > -0.3

        if (progress <= 0) return

        // Streaming line
        const lineEnd = 20 + (gateX - 20) * progress
        const lineAlpha = progress < 1 ? 0.6 : 0.25
        ctx.save()
        ctx.strokeStyle = passed ? `rgba(45,110,86,${lineAlpha * 0.5})` : `rgba(158,51,32,${lineAlpha * 0.5})`
        ctx.lineWidth = 1.5
        ctx.beginPath(); ctx.moveTo(20, y); ctx.lineTo(lineEnd, y); ctx.stroke()

        // Moving dot on the line
        if (progress < 1) {
          ctx.beginPath()
          ctx.arc(lineEnd, y, 3, 0, Math.PI * 2)
          ctx.fillStyle = passed ? 'rgba(45,110,86,0.8)' : 'rgba(158,51,32,0.8)'
          ctx.fill()
          // Glow
          ctx.beginPath()
          ctx.arc(lineEnd, y, 8, 0, Math.PI * 2)
          ctx.fillStyle = passed ? 'rgba(45,110,86,0.1)' : 'rgba(158,51,32,0.1)'
          ctx.fill()
        }

        // Field label
        ctx.font = '500 11px "JetBrains Mono", monospace'
        ctx.fillStyle = `rgba(28,27,25,${0.5 * Math.min(progress * 3, 1)})`
        ctx.fillText(name, 22, y - 6)

        // Result indicator (after gate)
        if (progress >= 1) {
          const resultX = gateX + 50
          const fadeIn = Math.min((cycleT - 0.8) * 3, 1)
          if (passed) {
            ctx.strokeStyle = `rgba(45,110,86,${0.7 * fadeIn})`
            ctx.lineWidth = 2.5
            ctx.lineCap = 'round'
            ctx.beginPath()
            ctx.moveTo(resultX - 5, y); ctx.lineTo(resultX - 1, y + 4); ctx.lineTo(resultX + 7, y - 5)
            ctx.stroke()
          } else {
            ctx.strokeStyle = `rgba(158,51,32,${0.7 * fadeIn})`
            ctx.lineWidth = 2.5
            ctx.lineCap = 'round'
            ctx.beginPath()
            ctx.moveTo(resultX - 4, y - 4); ctx.lineTo(resultX + 4, y + 4)
            ctx.moveTo(resultX - 4, y + 4); ctx.lineTo(resultX + 4, y - 4)
            ctx.stroke()
          }
        }
        ctx.restore()
      })

      // Gate label
      ctx.save()
      ctx.font = '600 9px "JetBrains Mono", monospace'
      ctx.fillStyle = 'rgba(196,98,42,0.35)'
      ctx.textAlign = 'center'
      ctx.fillText('CONTRACT', gateX, H - 8)
      ctx.restore()

      raf = requestAnimationFrame(draw)
    }
    raf = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(raf)
  }, [])
  return <canvas ref={canvasRef} className="w-full" style={{ aspectRatio: '560/360' }} />
}

/* ── Trust Layer Flourish: Compliance (canvas-rendered) ───────────── */
function ComplianceFlourish() {
  return (
    <div className="bg-panel rounded-xl border border-rule-light overflow-hidden" style={{ boxShadow: '0 2px 8px rgba(20,18,16,0.04)' }}>
      <div className="grid grid-cols-2 divide-x divide-rule-light">
        {/* JSON input */}
        <div>
          <div className="px-3 py-2 border-b border-rule-light flex items-center gap-2">
            <span className="text-[9px] font-mono text-muted">your data</span>
            <span className="text-[8px] px-1.5 py-0.5 rounded bg-surface text-muted font-mono">.json</span>
          </div>
          <pre className="p-3 font-mono text-[9px] leading-[1.8] text-ink-2 overflow-hidden">{`{
  "seller": {
    "name": "Muster GmbH",
    "vat_id": "DE123456789"
  },
  "buyer": {
    "name": "Kunde AG",
    "vat_id": "DE987654321"
  },
  "items": [{
    "description": "Consulting",
    "unit_price": 4500.00,
    "tax_rate": 19
  }],
  "payment": {
    "iban": "DE8937...013000"
  }
}`}</pre>
        </div>
        {/* CII XML output */}
        <div>
          <div className="px-3 py-2 border-b border-rule-light flex items-center gap-2">
            <span className="text-[9px] font-mono text-sage">embedded XML</span>
            <span className="text-[8px] px-1.5 py-0.5 rounded bg-sage/10 text-sage font-mono">CII</span>
          </div>
          <pre className="p-3 font-mono text-[9px] leading-[1.8] text-ink-2 overflow-hidden">{`<CrossIndustryInvoice>
  <ExchangedDocument>
    <ID>RE-2026-0042</ID>
    <TypeCode>380</TypeCode>
  </ExchangedDocument>
  <SellerTradeParty>
    <Name>Muster GmbH</Name>
    <SpecifiedTaxRegistration>
      <ID>DE123456789</ID>
    </SpecifiedTaxRegistration>
  </SellerTradeParty>
  <ApplicableTradeTax>
    <TypeCode>VAT</TypeCode>
    <CategoryCode>S</CategoryCode>
    <RateApplicablePercent>
      19
    </RateApplicablePercent>
  </ApplicableTradeTax>
</CrossIndustryInvoice>`}</pre>
        </div>
      </div>
      <div className="px-3 py-2 border-t border-rule-light flex items-center justify-between">
        <span className="text-[9px] text-muted italic">XSD + Schematron validated, embedded in PDF/A-3b</span>
        <span className="text-[8px] px-2 py-0.5 rounded-full bg-sage/10 text-sage font-semibold">EN 16931</span>
      </div>
    </div>
  )
}

/* ── Trust Layer Flourish: Provenance (canvas-rendered) ───────────── */
function ProvenanceFlourish() {
  const canvasRef = useRef(null)
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const dpr = window.devicePixelRatio || 1
    const W = 520, H = 300
    canvas.width = W * dpr; canvas.height = H * dpr
    canvas.style.width = W + 'px'; canvas.style.height = H + 'px'
    ctx.scale(dpr, dpr)
    let raf, t = 0

    const rows = [
      { label: 'data', file: 'invoice_data.json', hash: 'sha256:a7f3e2c1', icon: '{ }' },
      { label: 'template', file: 'invoice.j2.typ', hash: 'sha256:c2e1b809', icon: '< >' },
      { label: 'assets', file: 'Inter-Bold.ttf, logo.png', hash: 'sha256:d4f09188', icon: 'A a' },
      { label: 'output', file: 'invoice.pdf  (3 pages)', hash: 'sha256:9b4d7a52', icon: 'PDF' },
    ]

    const rowH = 52, startY = 32, leftX = 28, hashX = 370

    function draw() {
      t += 0.005
      ctx.clearRect(0, 0, W, H)

      const cycleT = (t * 0.6) % 3.5
      const activeCount = Math.min(Math.floor(cycleT / 0.6), 4)
      const verifying = activeCount > 0 && activeCount <= 4 ? Math.floor(cycleT / 0.6) - 1 : -1

      // Timeline spine
      const spineX = leftX + 14
      ctx.beginPath()
      ctx.moveTo(spineX, startY + 16)
      ctx.lineTo(spineX, startY + (rows.length - 1) * rowH + 16)
      ctx.strokeStyle = 'rgba(28,27,25,0.1)'
      ctx.lineWidth = 1.5
      ctx.stroke()

      // Active spine
      if (activeCount > 0) {
        const endY = startY + Math.min(activeCount - 1, 3) * rowH + 16
        ctx.beginPath()
        ctx.moveTo(spineX, startY + 16)
        ctx.lineTo(spineX, endY)
        ctx.strokeStyle = 'rgba(196,98,42,0.5)'
        ctx.lineWidth = 2
        ctx.stroke()
      }

      rows.forEach((row, i) => {
        const y = startY + i * rowH
        const active = i < activeCount
        const current = i === verifying
        const pulse = current ? Math.sin(t * 8) * 0.12 + 0.88 : 1

        // Timeline dot
        ctx.beginPath()
        ctx.arc(spineX, y + 16, active ? 5 : 3.5, 0, Math.PI * 2)
        ctx.fillStyle = active ? `rgba(196,98,42,${0.85 * pulse})` : 'rgba(28,27,25,0.15)'
        ctx.fill()
        if (current) {
          ctx.beginPath()
          ctx.arc(spineX, y + 16, 10, 0, Math.PI * 2)
          ctx.fillStyle = `rgba(196,98,42,${0.12 * pulse})`
          ctx.fill()
        }

        // Icon circle
        const iconX = leftX + 44
        ctx.beginPath()
        ctx.arc(iconX, y + 16, 13, 0, Math.PI * 2)
        ctx.fillStyle = active ? 'rgba(196,98,42,0.1)' : 'rgba(28,27,25,0.04)'
        ctx.strokeStyle = active ? `rgba(196,98,42,${0.4 * pulse})` : 'rgba(28,27,25,0.12)'
        ctx.lineWidth = 1.2
        ctx.fill(); ctx.stroke()

        ctx.font = `600 8px "JetBrains Mono", monospace`
        ctx.textAlign = 'center'
        ctx.fillStyle = active ? `rgba(196,98,42,${0.8 * pulse})` : 'rgba(28,27,25,0.3)'
        ctx.fillText(row.icon, iconX, y + 19)

        // Stage label
        ctx.font = `${active ? '600' : '400'} 12px "JetBrains Mono", monospace`
        ctx.textAlign = 'left'
        ctx.fillStyle = `rgba(28,27,25,${active ? 0.85 : 0.3})`
        ctx.fillText(row.label, leftX + 66, y + 13)

        // File name
        ctx.font = '400 9px "JetBrains Mono", monospace'
        ctx.fillStyle = `rgba(28,27,25,${active ? 0.45 : 0.15})`
        ctx.fillText(row.file, leftX + 66, y + 28)

        // Hash value — appears with typing animation for current
        ctx.textAlign = 'right'
        if (active) {
          let displayHash = row.hash
          if (current) {
            const charCount = Math.floor(((cycleT / 0.6) % 1) * (row.hash.length + 4))
            displayHash = row.hash.slice(0, Math.min(charCount, row.hash.length))
            // Blinking cursor
            if (Math.sin(t * 12) > 0) displayHash += '_'
          }
          ctx.font = '500 10px "JetBrains Mono", monospace'
          ctx.fillStyle = current ? `rgba(196,98,42,${0.9 * pulse})` : 'rgba(196,98,42,0.55)'
          ctx.fillText(displayHash, W - 28, y + 13)

          // Checkmark for completed (not current)
          if (!current) {
            ctx.font = '500 12px system-ui'
            ctx.fillStyle = 'rgba(107,142,95,0.8)'
            ctx.fillText('\u2713', W - 18, y + 29)
            ctx.font = '400 8px "JetBrains Mono", monospace'
            ctx.fillStyle = 'rgba(28,27,25,0.3)'
            ctx.fillText('verified', W - 32, y + 29)
          }
        } else {
          ctx.font = '500 10px "JetBrains Mono", monospace'
          ctx.fillStyle = 'rgba(28,27,25,0.1)'
          ctx.fillText('- - - - - -', W - 28, y + 13)
        }

        // Horizontal connector from icon to hash area
        if (active) {
          ctx.beginPath()
          ctx.moveTo(leftX + 66 + ctx.measureText(row.label).width + 8, y + 9)
          ctx.textAlign = 'left'
          ctx.font = '600 12px "JetBrains Mono", monospace'
          const labelW = ctx.measureText(row.label).width
          const lineStartX = leftX + 66 + labelW + 10
          const lineEndX = hashX - 10
          if (lineEndX > lineStartX) {
            ctx.beginPath()
            ctx.moveTo(lineStartX, y + 10)
            ctx.lineTo(lineEndX, y + 10)
            ctx.strokeStyle = `rgba(196,98,42,${0.15 * pulse})`
            ctx.lineWidth = 1
            ctx.setLineDash([3, 4])
            ctx.stroke()
            ctx.setLineDash([])
          }
        }
      })

      // Final combined fingerprint at bottom
      const bottomY = startY + rows.length * rowH + 8
      if (activeCount >= 4) {
        const allDone = cycleT > 2.8
        const fadeIn = Math.min((cycleT - 2.4) / 0.4, 1)
        if (fadeIn > 0) {
          ctx.globalAlpha = fadeIn
          // Separator line
          ctx.beginPath()
          ctx.moveTo(leftX, bottomY - 4)
          ctx.lineTo(W - 28, bottomY - 4)
          ctx.strokeStyle = 'rgba(196,98,42,0.2)'
          ctx.lineWidth = 1
          ctx.stroke()

          ctx.font = '600 11px "JetBrains Mono", monospace'
          ctx.textAlign = 'left'
          ctx.fillStyle = `rgba(196,98,42,${allDone ? 0.9 : 0.6})`
          ctx.fillText('render fingerprint', leftX + 14, bottomY + 16)

          ctx.font = '500 10px "JetBrains Mono", monospace'
          ctx.textAlign = 'right'
          ctx.fillStyle = 'rgba(196,98,42,0.7)'
          ctx.fillText('sha256:e83b...f41a', W - 28, bottomY + 16)

          if (allDone) {
            ctx.font = '600 9px system-ui'
            ctx.fillStyle = 'rgba(107,142,95,0.85)'
            ctx.textAlign = 'left'
            ctx.fillText('\u2713  all inputs tracked', leftX + 14, bottomY + 34)
          }
          ctx.globalAlpha = 1
        }
      }

      raf = requestAnimationFrame(draw)
    }
    raf = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(raf)
  }, [])
  return <canvas ref={canvasRef} className="w-full" style={{ aspectRatio: '520/300' }} />
}

/* ── Utilities ────────────────────────────────────────────────────── */
function FadeUp({ children, className = '', delay = 0 }) {
  const r = useRef(null)
  useEffect(() => {
    const el = r.current; if (!el) return
    const obs = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) { setTimeout(() => el.classList.add('vis'), delay); obs.unobserve(el) }
    }, { threshold: 0.08 })
    obs.observe(el)
    return () => obs.disconnect()
  }, [delay])
  return <div ref={r} className={`fade-up ${className}`}>{children}</div>
}

/* ── Logo mark ────────────────────────────────────────────────────── */
function Logo({ size = 'default' }) {
  const s = size === 'small' ? 'h-6' : 'h-8'
  return (
    <div className="flex items-center gap-2.5">
      {/* Symbol: structured document seal / imprint */}
      <svg className={`${s} aspect-square`} viewBox="0 0 32 32" fill="none">
        <rect x="2" y="2" width="28" height="28" rx="4" stroke="currentColor" strokeWidth="2" />
        <rect x="7" y="7" width="18" height="3" rx="1" fill="currentColor" opacity="0.9" />
        <rect x="7" y="13" width="18" height="1.5" rx="0.75" fill="currentColor" opacity="0.3" />
        <rect x="7" y="17" width="14" height="1.5" rx="0.75" fill="currentColor" opacity="0.3" />
        <rect x="7" y="21" width="16" height="1.5" rx="0.75" fill="currentColor" opacity="0.3" />
        <path d="M20 22.5l2.5 2.5L27 20" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" opacity="0.8" />
      </svg>
      <span className={`font-display tracking-tight ${size === 'small' ? 'text-[18px]' : 'text-[22px]'}`}>
        TrustRender
      </span>
    </div>
  )
}

/* ── Data ──────────────────────────────────────────────────────────── */
const VALID = {
  invoice_number: "INV-2026-0042",
  invoice_date: "April 10, 2026",
  due_date: "May 10, 2026",
  payment_terms: "Net 30",
  sender: { name: "Acme Corp", address: "123 Business Ave, SF 94105", email: "billing@acme.com" },
  recipient: { name: "Contoso Ltd", address: "456 Enterprise Blvd, NY 10001", email: "ap@contoso.com" },
  items: [
    { num: 1, description: "Website redesign", qty: 1, unit_price: "$4,500", amount: "$4,500" },
    { num: 2, description: "Logo and brand identity", qty: 1, unit_price: "$2,200", amount: "$2,200" },
    { num: 3, description: "SEO optimization", qty: 1, unit_price: "$1,800", amount: "$1,800" },
    { num: 4, description: "Social media content", qty: 3, unit_price: "$750", amount: "$2,250" },
    { num: 5, description: "Email campaign setup", qty: 1, unit_price: "$1,200", amount: "$1,200" },
    { num: 6, description: "Analytics config", qty: 1, unit_price: "$950", amount: "$950" },
    { num: 7, description: "Blog posts", qty: 5, unit_price: "$300", amount: "$1,500" },
  ],
  subtotal: "$14,400",
  tax_rate: "8.5%",
  tax_amount: "$1,224",
  total: "$15,624",
  notes: "Payment due within 30 days."
}

const INVALID = {
  invoice_number: "INV-2026-0042",
  invoice_date: "April 10, 2026",
  due_date: "May 10, 2026",
  payment_terms: "Net 30",
  sender: { name: "Acme Corp", address: "123 Business Ave, SF 94105" },
  recipient: { address: "456 Enterprise Blvd, NY 10001", email: "ap@contoso.com" },
  items: [
    { num: 1, description: "Website redesign", qty: 1, unit_price: "$4,500", amount: "$4,500" },
    { num: 2, qty: 1, unit_price: "$2,200", amount: "$2,200" },
    { num: 3, description: "SEO optimization", qty: 1, unit_price: "$1,800", amount: "$1,800" },
  ],
  subtotal: "$8,500",
  tax_rate: "8.5%",
  tax_amount: "$722",
  total: "$8,500",
  notes: "Payment due within 30 days."
}

const ERRORS = [
  { path: 'sender.email', expected: 'scalar', got: 'missing' },
  { path: 'recipient.name', expected: 'scalar', got: 'missing' },
  { path: 'items[1].description', expected: 'scalar', got: 'missing' },
]

/* ── JSON syntax coloring ─────────────────────────────────────────── */
function Json({ data, marks = {} }) {
  const lines = JSON.stringify(data, null, 2).split('\n')
  return (
    <pre className="font-mono text-[11px] leading-[1.85] text-ink-2 whitespace-pre">
      {lines.map((line, i) => {
        const mk = Object.keys(marks).find(k => line.includes(`"${k}"`))
        const h = line
          .replace(/"([^"]+)"(\s*:)/g, '<span style="color:#8a8278">"$1"</span>$2')
          .replace(/:\s*"([^"]*?)"/g, (_, v) => `: <span style="color:#141210">"${v}"</span>`)
          .replace(/:\s*(\d[\d.]*)/g, ': <span style="color:#8b3a2a">$1</span>')
          .replace(/:\s*(null)\b/g, ': <span style="color:#6e2517;font-weight:600">null</span>')
          .replace(/([{}[\],])/g, '<span style="color:#c9c2b6">$1</span>')
        return (
          <div key={i}
            className={mk ? 'border-l-[3px] border-wine/50 bg-wine/[0.05] pl-2.5 -ml-2.5 rounded-r-sm' : ''}
            dangerouslySetInnerHTML={{ __html: h || '\u00A0' }}
          />
        )
      })}
    </pre>
  )
}

/* ── JSON dark (for hero on dark bg) ──────────────────────────────── */
function JsonDark({ data, marks = {} }) {
  const lines = JSON.stringify(data, null, 2).split('\n')
  return (
    <pre className="font-mono text-[11px] leading-[1.85] whitespace-pre">
      {lines.map((line, i) => {
        const mk = Object.keys(marks).find(k => line.includes(`"${k}"`))
        // Build colored spans token by token instead of chained regexes
        const parts = []
        let rest = line
        // Match key: value patterns safely
        const keyMatch = rest.match(/^(\s*)"([^"]+)"(\s*:\s*)(.*)$/)
        if (keyMatch) {
          const [, indent, key, colon, val] = keyMatch
          parts.push(<span key="i" style={{ color: 'transparent' }}>{indent}</span>)
          parts.push(<span key="k" style={{ color: 'rgba(250,248,245,0.35)' }}>"{key}"</span>)
          parts.push(<span key="c" style={{ color: 'rgba(250,248,245,0.15)' }}>{colon}</span>)
          // Parse value
          if (val === 'null' || val === 'null,') {
            const comma = val.endsWith(',') ? ',' : ''
            parts.push(<span key="v" style={{ color: '#e55', fontWeight: 600 }}>null</span>)
            if (comma) parts.push(<span key="cm" style={{ color: 'rgba(250,248,245,0.12)' }}>,</span>)
          } else if (val.match(/^".*"[,]?$/)) {
            const comma = val.endsWith(',') ? ',' : ''
            const str = comma ? val.slice(0, -1) : val
            parts.push(<span key="v" style={{ color: 'rgba(250,248,245,0.75)' }}>{str}</span>)
            if (comma) parts.push(<span key="cm" style={{ color: 'rgba(250,248,245,0.12)' }}>,</span>)
          } else if (val.match(/^\d/)) {
            const comma = val.endsWith(',') ? ',' : ''
            const num = comma ? val.slice(0, -1) : val
            parts.push(<span key="v" style={{ color: '#a34d3a' }}>{num}</span>)
            if (comma) parts.push(<span key="cm" style={{ color: 'rgba(250,248,245,0.12)' }}>,</span>)
          } else {
            // brackets, braces, arrays
            parts.push(<span key="v" style={{ color: 'rgba(250,248,245,0.15)' }}>{val}</span>)
          }
        } else {
          // Structural lines: braces, brackets
          parts.push(<span key="s" style={{ color: 'rgba(250,248,245,0.15)' }}>{rest}</span>)
        }
        return (
          <div key={i} className={mk ? 'border-l-[3px] border-red-400/40 bg-red-400/[0.06] pl-2.5 -ml-2.5 rounded-r-sm' : ''}>
            {/* Re-render indent visibly */}
            <span style={{ color: 'transparent', userSelect: 'none' }}>{''}</span>
            {line.match(/^\s*/)[0].split('').map((_, ci) => <span key={ci}>&nbsp;</span>)}
            {parts}
          </div>
        )
      })}
    </pre>
  )
}

/* ── Invoice document artifact ────────────────────────────────────── */
function Invoice({ data }) {
  return (
    <div className="bg-white rounded-lg overflow-hidden text-ink"
      style={{ boxShadow: '0 12px 40px rgba(20,18,16,0.12), 0 2px 8px rgba(20,18,16,0.06)' }}>
      <div className="p-8 pb-7">
        <div className="flex justify-between items-start mb-8">
          <div>
            <div className="text-[16px] font-bold tracking-[-0.02em]">{data.sender.name}</div>
            <div className="text-[10px] text-muted mt-1.5 leading-relaxed">{data.sender.address}</div>
            <div className="text-[10px] text-muted mt-0.5">{data.sender.email}</div>
          </div>
          <div className="text-right">
            <div className="text-[24px] font-display tracking-tight text-ink/70">INVOICE</div>
            <div className="text-[10px] text-muted mt-1 font-mono">{data.invoice_number}</div>
            <div className="text-[10px] text-muted">{data.invoice_date}</div>
          </div>
        </div>
        <div className="h-px bg-ink/10 mb-7" />
        <div className="grid grid-cols-3 gap-6 mb-7">
          <div>
            <div className="text-[8px] uppercase tracking-[0.14em] text-muted mb-1.5 font-semibold">Bill to</div>
            <div className="text-[11px] font-semibold">{data.recipient.name}</div>
            <div className="text-[10px] text-muted leading-relaxed mt-0.5">{data.recipient.address}</div>
          </div>
          <div>
            <div className="text-[8px] uppercase tracking-[0.14em] text-muted mb-1.5 font-semibold">Due date</div>
            <div className="text-[11px] font-semibold">{data.due_date}</div>
            <div className="text-[10px] text-muted">{data.payment_terms}</div>
          </div>
          <div>
            <div className="text-[8px] uppercase tracking-[0.14em] text-muted mb-1.5 font-semibold">Amount due</div>
            <div className="text-[18px] font-bold tracking-tight">{data.total}</div>
          </div>
        </div>
        <table className="w-full text-[10px] mb-7">
          <thead>
            <tr className="border-b-2 border-ink/10">
              {['#', 'Description', 'Qty', 'Price', 'Amount'].map((h, i) => (
                <th key={h} className={`py-2.5 font-semibold text-[8px] uppercase tracking-[0.1em] text-muted ${i > 1 ? 'text-right' : 'text-left'} ${i === 0 ? 'w-7' : i > 2 ? 'w-20' : i === 2 ? 'w-10' : ''}`}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.items.map((item, i) => (
              <tr key={i} className="border-b border-ink/[0.04]">
                <td className="py-2 text-muted tabular-nums">{item.num}</td>
                <td className="py-2 text-ink-2">{item.description}</td>
                <td className="py-2 text-right text-muted tabular-nums">{item.qty}</td>
                <td className="py-2 text-right text-muted tabular-nums">{item.unit_price}</td>
                <td className="py-2 text-right font-medium tabular-nums">{item.amount}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="flex justify-end mb-7">
          <div className="w-52">
            <div className="flex justify-between py-1 text-[10px]"><span className="text-muted">Subtotal</span><span className="font-medium tabular-nums">{data.subtotal}</span></div>
            <div className="flex justify-between py-1 text-[10px] text-muted"><span>Tax ({data.tax_rate})</span><span className="tabular-nums">{data.tax_amount}</span></div>
            <div className="h-px bg-ink/15 my-1.5" />
            <div className="flex justify-between py-1.5 text-[14px] font-bold"><span>Total</span><span className="tabular-nums">{data.total}</span></div>
          </div>
        </div>
        <div className="border-t border-ink/[0.06] pt-4">
          <div className="text-[8px] uppercase tracking-[0.14em] text-muted mb-1 font-semibold">Notes</div>
          <div className="text-[9px] text-muted leading-relaxed max-w-sm">{data.notes}</div>
        </div>
      </div>
      <div className="px-8 py-2.5 bg-surface/40 border-t border-ink/[0.04] flex justify-between text-[8px] text-muted">
        <span>Generated by TrustRender</span>
        <span className="tabular-nums">Page 1 of 1</span>
      </div>
    </div>
  )
}

/* ── Pipeline stage ───────────────────────────────────────────────── */
function Stage({ label, status, sub }) {
  const isPass = status === 'pass', isFail = status === 'fail', isRun = status === 'running', isBlocked = status === 'blocked'
  return (
    <div className={`flex items-center gap-3.5 transition-opacity duration-300 ${isBlocked ? 'opacity-15' : ''}`}>
      <div className="relative shrink-0">
        {status === 'waiting' && <div className="w-9 h-9 rounded-full border-2 border-rule" />}
        {isRun && <div className="w-9 h-9 rounded-full border-2 border-muted pulse-ring flex items-center justify-center text-muted"><div className="w-2.5 h-2.5 rounded-full bg-muted/50 contract-pulse" /></div>}
        {isPass && <div className="w-9 h-9 rounded-full bg-sage flex items-center justify-center anim-check"><svg className="w-4.5 h-4.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="3"><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg></div>}
        {isFail && <div className="w-9 h-9 rounded-full bg-wine flex items-center justify-center anim-x"><svg className="w-4.5 h-4.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="3"><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg></div>}
        {isBlocked && <div className="w-9 h-9 rounded-full border-2 border-rule/30" />}
      </div>
      <div>
        <div className={`text-[14px] font-semibold leading-tight ${isFail ? 'text-wine' : isPass ? 'text-sage' : isBlocked ? 'text-muted/30' : 'text-ink'}`}>{label}</div>
        {sub && <div className={`text-[11px] mt-0.5 ${isFail ? 'text-wine/60' : isPass ? 'text-sage/50' : 'text-muted'}`}>{sub}</div>}
      </div>
    </div>
  )
}

function Connector({ active, blocked }) {
  return <div className="flex justify-start pl-[17px]"><div className={`w-px h-7 transition-all duration-300 ${blocked ? 'bg-rule/15' : active ? 'bg-sage/30' : 'bg-rule/60'}`} /></div>
}

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   SECTION 1: HERO = PRODUCT REVEAL
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
function HeroReveal() {
  const [mode, setMode] = useState(null) // null = no selection yet
  const [phase, setPhase] = useState('idle')
  const [run, setRun] = useState(0)

  useEffect(() => {
    if (mode === null) return // don't auto-run on mount
    setPhase('idle')
    const t = []
    t.push(setTimeout(() => setPhase('validate'), 250))
    t.push(setTimeout(() => setPhase(mode === 'valid' ? 'render' : 'fail'), 1000))
    t.push(setTimeout(() => { if (mode === 'valid') setPhase('done') }, 1800))
    return () => t.forEach(clearTimeout)
  }, [mode, run])

  const toggle = (m) => { setMode(m); setRun(r => r + 1) }

  const vSt = phase === 'idle' ? 'waiting' : phase === 'validate' ? 'running' : phase === 'fail' ? 'fail' : 'pass'
  const rSt = phase === 'idle' || phase === 'validate' ? 'waiting' : phase === 'fail' ? 'blocked' : phase === 'render' ? 'running' : 'pass'
  const oSt = phase === 'done' ? 'pass' : phase === 'fail' ? 'blocked' : 'waiting'
  const showDoc = phase === 'done' && mode === 'valid'
  const showErrors = phase === 'fail' && mode === 'invalid'

  return (
    <section className="text-panel relative overflow-hidden" style={{ background: 'radial-gradient(ellipse 80% 60% at 50% 30%, rgba(179,108,57,0.10) 0%, transparent 70%), linear-gradient(180deg, #141618 0%, #111214 40%, #0f1012 100%)' }}>
      {/* Animated particle background */}
      <DocumentField />

      {/* Hero content */}
      <div className="max-w-[1280px] mx-auto px-6 md:px-10 pt-16 md:pt-24 pb-12 md:pb-16 relative z-10">
        <div className="text-center max-w-4xl mx-auto mb-8 hero-stagger">
          <h1 className="font-display font-extrabold text-[44px] md:text-[72px] lg:text-[88px] leading-[0.95] tracking-[-0.04em] gradient-text pb-2">
            Bad payloads never become broken documents.
          </h1>
          <p className="text-[16px] md:text-[18px] text-panel/45 max-w-xl mx-auto mt-6 leading-relaxed">
            Validate document data before render. Catch missing fields, broken paths, and structural errors before a bad invoice reaches a customer.
          </p>
          <div className="mt-6 inline-flex flex-col items-center gap-2">
            <button onClick={() => navigator.clipboard.writeText('pip install trustrender && trustrender quickstart')}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full border border-panel/15 hover:border-panel/30 bg-panel/[0.05] hover:bg-panel/[0.08] transition-colors cursor-pointer group">
              <code className="font-mono text-[13px] text-panel/60 group-hover:text-panel/80">pip install trustrender && trustrender quickstart</code>
              <span className="text-[9px] text-panel/25 group-hover:text-panel/50 transition-colors">copy</span>
            </button>
          </div>
          {/* Scroll indicator */}
          <div className="mt-8 flex justify-center">
            <div className="w-6 h-10 rounded-full border border-panel/20 flex items-start justify-center pt-2">
              <div className="w-1 h-2 rounded-full bg-panel/50 scroll-dot" />
            </div>
          </div>
        </div>

        {/* Toggle */}
        <div className="hero-stagger">
          <div className="flex items-center justify-center gap-3 mb-8">
            <button onClick={() => toggle('valid')}
              className={`text-[13px] px-6 py-2.5 rounded-full border-2 transition-all font-medium cursor-pointer
                ${mode === 'valid' ? 'bg-rust text-white border-rust' : 'text-panel/70 border-panel/30 hover:border-panel/50 hover:text-panel/90 bg-panel/[0.06]'}`}>
              See it pass
            </button>
            <button onClick={() => toggle('invalid')}
              className={`text-[13px] px-6 py-2.5 rounded-full border-2 transition-all font-medium cursor-pointer
                ${mode === 'invalid' ? 'bg-wine text-white border-wine' : 'text-panel/70 border-panel/30 hover:border-panel/50 hover:text-panel/90 bg-panel/[0.06]'}`}>
              See what gets caught
            </button>
            <span className="ml-3 text-[11px] text-panel/50 font-mono hidden md:inline">
              {mode === null ? 'pick a scenario' : mode === 'valid' ? 'invoice_data.json' : 'bad_data.json'}{mode !== null ? ' \u2192 invoice.j2.typ' : ''}
            </span>
          </div>
        </div>

        {/* The Pipeline — the centerpiece */}
        <FadeUp delay={350}>
          <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,0.9fr)_180px_minmax(0,1.2fr)] gap-6 lg:gap-10 items-start" key={run}>

            {/* LEFT: payload */}
            <div className="bg-ink-3 rounded-xl border border-panel/8 overflow-hidden relative">
              <div className="px-4 py-2.5 border-b border-panel/8 flex items-center gap-2">
                <div className="flex gap-1.5">
                  <div className="w-2 h-2 rounded-full bg-panel/15" />
                  <div className="w-2 h-2 rounded-full bg-panel/15" />
                  <div className="w-2 h-2 rounded-full bg-panel/15" />
                </div>
                <span className="text-[10px] font-mono text-panel/50 ml-2">{mode === 'invalid' ? 'bad_data.json' : 'invoice_data.json'}</span>
              </div>
              <div className="p-4 max-h-[520px] overflow-y-auto overflow-x-auto" style={{ colorScheme: 'dark' }}>
                <JsonDark data={mode === 'invalid' ? INVALID : VALID} marks={mode === 'invalid' ? { recipient: 1 } : {}} />
              </div>
              <div className="absolute top-10 bottom-0 right-0 w-6 pointer-events-none" style={{ background: 'linear-gradient(to right, transparent, #282724)' }} />
            </div>

            {/* MIDDLE: pipeline */}
            <div className="flex flex-row lg:flex-col items-center lg:items-stretch gap-3 lg:gap-0 lg:pt-16 justify-center">
              <Stage label="Contract" status={vSt} sub={vSt === 'pass' ? 'all fields valid' : vSt === 'fail' ? '3 errors \u2014 stopped' : vSt === 'running' ? 'checking\u2026' : null} />
              <Connector active={vSt === 'pass'} blocked={rSt === 'blocked'} />
              <Stage label="Render" status={rSt} sub={rSt === 'pass' ? '41 ms \u00B7 typst' : rSt === 'running' ? 'typst\u2026' : rSt === 'blocked' ? 'not invoked' : null} />
              <Connector active={rSt === 'pass'} blocked={oSt === 'blocked'} />
              <Stage label="Output" status={oSt} sub={oSt === 'pass' ? 'PDF delivered' : oSt === 'blocked' ? 'not generated' : null} />
            </div>

            {/* RIGHT: result */}
            <div className="min-h-[520px] flex flex-col">
              {showDoc && <div className="anim-doc"><Invoice data={VALID} /></div>}

              {showErrors && (
                <div>
                  <div className="mb-6">
                    <div className="text-[16px] font-display text-red-300 mb-2">Payload intercepted before render</div>
                    <div className="text-[13px] text-panel/50">3 field errors caught at the data layer. The renderer was never invoked.</div>
                    <div className="text-[13px] text-panel/40 mt-2 border-l-2 border-panel/10 pl-3">No PDF was generated. No broken invoice was produced.</div>
                  </div>
                  <div className="space-y-1.5">
                    {ERRORS.map((err, i) => (
                      <div key={err.path} className="anim-error border-l-[3px] border-red-400/40 pl-4 py-3 rounded-r-sm bg-red-400/[0.04]"
                        style={{ animationDelay: `${i * 140}ms`, animationFillMode: 'both' }}>
                        <div className="font-mono text-[13px] font-semibold text-panel/90">{err.path}</div>
                        <div className="text-[11px] text-panel/40 mt-0.5">
                          expected <span className="font-mono font-semibold text-panel/60">{err.expected}</span>
                          <span className="mx-1.5 text-panel/15">&rarr;</span>
                          got <span className="font-mono font-semibold text-red-300">{err.got}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="mt-8 relative">
                    <div className="absolute inset-0 z-10 flex items-center justify-center">
                      <div className="bg-ink/95 backdrop-blur-sm rounded-lg px-7 py-5 border border-red-400/20 anim-stamp"
                        style={{ animationDelay: '500ms', animationFillMode: 'both' }}>
                        <div className="text-[14px] font-display text-red-300 text-center">Not generated</div>
                        <div className="text-[11px] text-panel/40 text-center mt-1.5 max-w-[200px]">This invoice was blocked before output, not after.</div>
                      </div>
                    </div>
                    <div className="opacity-[0.03] pointer-events-none scale-[0.93] origin-top blur-[1px]"><Invoice data={VALID} /></div>
                  </div>
                </div>
              )}

              {!showDoc && !showErrors && (
                <div className="flex-1 flex items-center justify-center min-h-[400px]">
                  <div className="text-center">
                    {phase === 'validate' && (
                      <>
                        <div className="w-12 h-12 mx-auto mb-5 rounded-full border-2 border-panel/20 relative pulse-ring flex items-center justify-center text-panel/20"><div className="w-3 h-3 rounded-full bg-panel/15 contract-pulse" /></div>
                        <p className="text-[13px] text-panel/40 font-medium">Checking data contract&hellip;</p>
                      </>
                    )}
                    {phase === 'render' && (
                      <>
                        <div className="w-56 h-1.5 bg-panel/10 rounded-full overflow-hidden mx-auto mb-5"><div className="h-full bg-panel/20 rounded-full shimmer-bar" /></div>
                        <p className="text-[13px] text-panel/40 font-medium">Rendering via Typst&hellip;</p>
                      </>
                    )}
                    {phase === 'idle' && (
                      <>
                        <div className="w-12 h-12 mx-auto mb-5 rounded-full border-2 border-panel/10 flex items-center justify-center"><div className="w-3 h-3 rounded-full border-2 border-panel/10" /></div>
                        <p className="text-[13px] text-panel/50">Awaiting input</p>
                      </>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </FadeUp>
      </div>
    </section>
  )
}

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   SECTION 2: TRUST LAYERS
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
function TrustLayers() {
  const layers = [
    {
      title: 'Readiness',
      desc: 'Structural contract inferred from your template. Missing fields, wrong types, null values — intercepted at the data layer before render.',
      stats: ['854 automated tests', '500 soak renders, 0 errors', '~60ms avg latency (Apple Silicon)'],
      flourish: <ReadinessFlourish />,
    },
    {
      title: 'Compliance',
      desc: 'Machine-readable German B2B invoices for the supported EN 16931 path. Validated before render, embedded as ZUGFeRD / Factur-X. Pure Python \u2014 no Java stack.',
      stats: ['Supported EN 16931 path', 'ZUGFeRD / Factur-X', 'German B2B invoice flow'],
      flourish: <ComplianceFlourish />,
      caption: 'Real JSON input \u2192 real CII XML output. XSD + Schematron validated.',
    },
    {
      title: 'Provenance',
      desc: 'Traceable input-to-output lineage within the render pipeline. Know what data went in, what template was used, and fingerprint the artifact produced.',
      stats: ['Input fingerprinting', 'Template fingerprinting', 'Output SHA-256'],
      flourish: <ProvenanceFlourish />,
    },
  ]

  return (
    <section className="py-20 md:py-28">
      <div className="max-w-[1280px] mx-auto px-6 md:px-10">
        <FadeUp>
          <p className="text-[11px] tracking-[0.22em] uppercase text-rust mb-4 font-semibold">Trust layers</p>
          <h2 className="font-display font-extrabold text-[28px] md:text-[40px] tracking-[-0.03em] leading-[1.08] mb-16 max-w-lg">
            Three layers between your data and a broken document.
          </h2>
        </FadeUp>
        <div className="space-y-16 md:space-y-24">
          {layers.map((l, i) => (
            <FadeUp key={l.title} delay={i * 100}>
              <div className={`grid grid-cols-1 md:grid-cols-[1.4fr_1fr] gap-8 md:gap-14 items-center ${i % 2 === 1 ? 'md:grid-cols-[1fr_1.4fr]' : ''}`}>
                {/* Flourish — alternates sides */}
                <div className={`bg-panel rounded-xl border border-rule-light overflow-hidden p-6 md:p-8 ${i % 2 === 1 ? 'md:order-2' : ''}`}
                  style={{ boxShadow: '0 2px 12px rgba(20,18,16,0.05)' }}>
                  {l.flourish}
                  {l.caption && <p className="text-[10px] text-muted text-center mt-2 italic">{l.caption}</p>}
                </div>
                {/* Text */}
                <div className={i % 2 === 1 ? 'md:order-1' : ''}>
                  <p className="text-[11px] tracking-[0.18em] uppercase text-rust font-semibold mb-3">0{i + 1}</p>
                  <div className="text-[28px] md:text-[34px] font-display tracking-tight mb-4 text-ink">{l.title}</div>
                  <p className="text-[15px] text-ink-2 leading-relaxed mb-6">{l.desc}</p>
                  <div className="space-y-3">
                    {l.stats.map(s => (
                      <div key={s} className="text-[13px] text-mid flex items-center gap-2.5">
                        <div className="w-1.5 h-1.5 rounded-full bg-rust shrink-0" />
                        {s}
                      </div>
                    ))}
                  </div>
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
   SECTION 3: LIVE PLAYGROUND
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
const FIXTURES = {
  'invoice.j2.typ': {
    label: 'Invoice',
    valid: {
      invoice_number: "INV-2026-0042", invoice_date: "April 10, 2026", due_date: "May 10, 2026", payment_terms: "Net 30",
      sender: { name: "Acme Corp", address: "123 Business Ave, SF, CA 94105", email: "billing@acme.com" },
      recipient: { name: "Contoso Ltd", address: "456 Enterprise Blvd, NY, NY 10001", email: "ap@contoso.com" },
      items: [
        { num: 1, description: "Website redesign", qty: 1, unit_price: "$4,500.00", amount: "$4,500.00" },
        { num: 2, description: "Logo and brand", qty: 1, unit_price: "$2,200.00", amount: "$2,200.00" },
        { num: 3, description: "SEO optimization", qty: 1, unit_price: "$1,800.00", amount: "$1,800.00" },
      ],
      subtotal: "$8,500.00", tax_rate: "8.5%", tax_amount: "$722.50", total: "$9,222.50",
      notes: "Payment due within 30 days."
    },
    invalid: {
      invoice_number: "INV-2026-0042", invoice_date: "April 10, 2026", due_date: "May 10, 2026", payment_terms: "Net 30",
      sender: { name: "Acme Corp", address: "123 Business Ave, SF, CA 94105" },
      recipient: { address: "456 Enterprise Blvd, NY, NY 10001", email: "ap@contoso.com" },
      items: [
        { num: 1, description: "Website redesign", qty: 1, unit_price: "$4,500.00", amount: "$4,500.00" },
        { num: 2, qty: 1, unit_price: "$2,200.00", amount: "$2,200.00" },
        { num: 3, description: "SEO optimization", qty: 1, unit_price: "$1,800.00", amount: "$1,800.00" },
      ],
      subtotal: "$8,500.00", tax_rate: "8.5%", tax_amount: "$722.50", total: "$8,500.00",
      notes: "Payment due within 30 days."
    },
  },
  'statement.j2.typ': {
    label: 'Statement',
    valid: {
      company: { name: "Acme Corp", address: "123 Business Ave, SF, CA 94105", email: "accounts@acme.com", phone: "(415) 555-0100" },
      customer: { name: "Contoso Ltd", account_number: "ACCT-78432", address: "456 Enterprise Blvd, NY, NY 10001", email: "ap@contoso.com" },
      statement_date: "April 10, 2026", period: "Mar 1 \u2013 Mar 31, 2026",
      opening_balance: "$12,450.00", closing_balance: "$18,267.50", total_charges: "$9,225.00", total_payments: "-$3,407.50",
      transactions: [
        { date: "Mar 01", description: "Opening Balance", reference: "", amount: "", balance: "$12,450.00" },
        { date: "Mar 02", description: "Invoice #0031", reference: "INV-0031", amount: "$1,500.00", balance: "$13,950.00" },
        { date: "Mar 03", description: "Wire payment", reference: "PMT-9981", amount: "-$2,000.00", balance: "$11,950.00" },
      ],
      aging: { current: "$5,575.00", days_30: "$3,200.00", days_60: "$1,500.00", days_90: "$7,992.50", total: "$18,267.50" },
      notes: "Payment terms: Net 30."
    },
    invalid: {
      company: { name: "Acme Corp", address: "123 Business Ave, SF, CA 94105", email: "accounts@acme.com", phone: "(415) 555-0100" },
      customer: { name: "Contoso Ltd", address: "456 Enterprise Blvd, NY, NY 10001", email: "ap@contoso.com" },
      statement_date: "April 10, 2026", period: "Mar 1 \u2013 Mar 31, 2026",
      opening_balance: "$12,450.00", closing_balance: "$18,267.50", total_charges: "$9,225.00", total_payments: "-$3,407.50",
      transactions: [
        { date: "Mar 01", description: "Opening Balance", reference: "", amount: "", balance: "$12,450.00" },
        { date: "Mar 02", reference: "INV-0031", amount: "$1,500.00", balance: "$13,950.00" },
      ],
      aging: { current: "$5,575.00", days_30: "$3,200.00", total: "$18,267.50" },
      notes: null
    },
  },
  'receipt.j2.typ': {
    label: 'Receipt',
    valid: {
      company: { name: "Daily Grind Coffee", address: "782 Market St, SF, CA 94102", phone: "(415) 555-0187", website: "dailygrind.com" },
      receipt_number: "REC-20260410", date: "April 10, 2026", time: "8:47 AM", cashier: "Maria S.", register: "POS-03",
      items: [
        { description: "Oat Milk Latte (Large)", qty: 2, unit_price: "$6.75", amount: "$13.50" },
        { description: "Avocado Toast", qty: 1, unit_price: "$12.95", amount: "$12.95" },
      ],
      subtotal: "$26.45", tax_label: "CA Sales Tax", tax_amount: "$2.28", total: "$28.73",
      payment: { method: "Visa", last_four: "4821", auth_code: "A94721" },
      amount_tendered: "$28.73", change_due: "$0.00", footer_message: "Thank you!"
    },
    invalid: {
      company: { name: "Daily Grind Coffee", address: "782 Market St, SF, CA 94102", phone: "(415) 555-0187" },
      receipt_number: "REC-20260410", date: "April 10, 2026", time: "8:47 AM", cashier: "Maria S.", register: "POS-03",
      items: [
        { description: "Oat Milk Latte (Large)", qty: 2, unit_price: "$6.75", amount: "$13.50" },
        { qty: 1, unit_price: "$12.95", amount: "$12.95" },
      ],
      subtotal: "$26.45", tax_label: "CA Sales Tax", tax_amount: "$2.28", total: null,
      payment: { method: "Visa", last_four: "4821" },
      amount_tendered: "$28.73", change_due: "$0.00", footer_message: "Thank you!"
    },
  },
  'letter.j2.typ': {
    label: 'Letter',
    valid: {
      sender: { name: "Acme Corp", title: "Accounts Receivable", address: "123 Business Ave, SF, CA 94105", phone: "(415) 555-0100", email: "ar@acme.com" },
      recipient: { name: "Margaret Chen", title: "CFO", company: "Contoso Ltd", address: "456 Enterprise Blvd, NY, NY 10001" },
      date: "April 10, 2026", subject: "Outstanding Balance", salutation: "Dear Ms. Chen,",
      body_paragraphs: ["Your account has an outstanding balance of $18,267.50.", "Please settle at your earliest convenience."],
      closing: "Sincerely,", signature_name: "James Rodriguez", signature_title: "Director of Finance", signature_company: "Acme Corp",
    },
    invalid: {
      sender: { name: "Acme Corp", title: "Accounts Receivable", address: "123 Business Ave, SF, CA 94105", phone: "(415) 555-0100" },
      recipient: { name: "Margaret Chen", title: "CFO", company: "Contoso Ltd", address: "456 Enterprise Blvd, NY, NY 10001" },
      date: "April 10, 2026", subject: "Outstanding Balance", salutation: "Dear Ms. Chen,",
      body_paragraphs: "Your account has an outstanding balance.",
      closing: "Sincerely,", signature_name: "James Rodriguez", signature_title: "Director of Finance",
    },
  },
  'einvoice.j2.typ': {
    label: 'E-Invoice (DE)',
    zugferd: 'en16931',
    valid: {
      invoice_type: "380", invoice_number: "RE-2026-0042", invoice_date: "2026-04-10", due_date: "2026-05-10", currency: "EUR",
      seller: { name: "Muster GmbH", address: "Musterstra\u00dfe 1", city: "Berlin", postal_code: "10115", country: "DE", vat_id: "DE123456789", email: "rechnung@muster.de", phone: "+49 30 12345678" },
      buyer: { name: "Kunde AG", address: "Kundenweg 42", city: "M\u00fcnchen", postal_code: "80331", country: "DE", vat_id: "DE987654321" },
      items: [
        { description: "Webseiten-Redesign", quantity: 1, unit: "C62", unit_price: 4500.00, tax_rate: 19, line_total: 4500.00 },
        { description: "SEO-Optimierung (3 Monate)", quantity: 3, unit: "MON", unit_price: 750.00, tax_rate: 19, line_total: 2250.00 },
        { description: "Logo-Design und CI", quantity: 1, unit: "C62", unit_price: 2200.00, tax_rate: 19, line_total: 2200.00 },
      ],
      subtotal: 8950.00,
      tax_entries: [{ rate: 19, basis: 8950.00, amount: 1700.50 }],
      tax_total: 1700.50, total: 10650.50,
      payment: { means: "credit_transfer", iban: "DE89370400440532013000", bic: "COBADEFFXXX", bank_name: "Commerzbank" },
      notes: "Zahlbar innerhalb von 30 Tagen netto."
    },
    invalid: {
      invoice_type: "380", invoice_number: "RE-2026-0042", invoice_date: "2026-04-10", due_date: "2026-05-10", currency: "EUR",
      seller: { name: "Muster GmbH", address: "Musterstra\u00dfe 1", city: "Berlin", postal_code: "10115", country: "DE" },
      buyer: { name: "Kunde AG", address: "Kundenweg 42", city: "M\u00fcnchen", postal_code: "80331", country: "DE" },
      items: [
        { description: "Webseiten-Redesign", quantity: 1, unit: "C62", unit_price: 4500.00, tax_rate: 19, line_total: 4500.00 },
      ],
      subtotal: 8950.00,
      tax_entries: [{ rate: 19, basis: 8950.00, amount: 1700.50 }],
      tax_total: 1700.50, total: 10650.50,
      payment: { means: "credit_transfer", iban: "DE89370400440532013000" },
      notes: "Zahlbar innerhalb von 30 Tagen netto."
    },
  },
  'report.j2.typ': {
    label: 'Report',
    valid: {
      company: { name: "Acme Corp", department: "Engineering" },
      title: "Q1 2026 Infrastructure Review", subtitle: "Quarterly Summary", date: "April 10, 2026",
      prepared_by: "Sarah Kim, VP Eng", period: "Jan 1 \u2013 Mar 31, 2026",
      executive_summary: "Uptime 99.94%. Two P1 incidents resolved within SLA.",
      metrics: [{ label: "Uptime", value: "99.94%", target: "99.9%", status: "above" }],
      incidents: [{ id: "INC-0012", date: "Feb 14", severity: "P1", duration: "18 min", description: "DB pool exhaustion.", root_cause: "Connection leak.", resolution: "Hotfix." }],
      spend_by_service: [{ service: "Compute", q1_spend: "$52,100", q4_spend: "$58,400", change: "-10.8%" }],
      recommendations: ["Migrate to reserved instances."],
    },
    invalid: {
      company: { name: "Acme Corp", department: "Engineering" },
      title: "Q1 2026 Infrastructure Review", subtitle: "Quarterly Summary", date: "April 10, 2026",
      prepared_by: "Sarah Kim, VP Eng", period: "Jan 1 \u2013 Mar 31, 2026",
      executive_summary: "Uptime 99.94%. Two P1 incidents resolved within SLA.",
      metrics: [{ label: "Uptime", value: "99.94%", target: "99.9%" }],
      incidents: [{ id: "INC-0012", date: "Feb 14", severity: "P1", duration: "18 min", description: "DB pool exhaustion." }],
      spend_by_service: [{ service: "Compute", q1_spend: "$52,100" }],
    },
  },
}

// Display name for a rendered bundle — doc type + best identifier + time fallback
const bundleDisplayName = (templateKey, data) => {
  const label = FIXTURES[templateKey]?.label || 'Document'
  let id = ''
  try {
    const d = typeof data === 'string' ? JSON.parse(data) : data
    if (templateKey === 'invoice.j2.typ') id = d.invoice_number || (d.recipient?.name ? `for ${d.recipient.name}` : '')
    else if (templateKey === 'receipt.j2.typ') id = d.receipt_number || (d.company?.name ? `from ${d.company.name}` : '')
    else if (templateKey === 'statement.j2.typ') id = d.customer?.account_number || (d.customer?.name ? `for ${d.customer.name}` : '')
    else if (templateKey === 'letter.j2.typ') id = d.recipient?.name ? `to ${d.recipient.name}` : d.subject || ''
    else if (templateKey === 'einvoice.j2.typ') id = d.invoice_number || (d.buyer?.name ? `for ${d.buyer.name}` : '')
    else if (templateKey === 'report.j2.typ') id = d.title || d.subtitle || ''
  } catch {}
  return id ? `${label} ${id}` : label
}

// Required fields per document type — gate "Ready to render" on these
const REQUIRED_FIELDS = {
  'invoice.j2.typ': (d) =>
    d.invoice_number && d.invoice_date && d.sender?.name && d.recipient?.name
    && d.items?.length > 0 && d.total,
  'statement.j2.typ': (d) =>
    d.company?.name && d.customer?.name && d.statement_date && d.closing_balance,
  'receipt.j2.typ': (d) =>
    d.company?.name && (d.receipt_number || d.date) && d.items?.length > 0 && d.total,
  'letter.j2.typ': (d) =>
    d.sender?.name && d.recipient?.name && d.subject && d.body_paragraphs?.length > 0,
  'einvoice.j2.typ': (d) =>
    d.invoice_number && d.seller?.name && d.buyer?.name && d.items?.length > 0 && d.total,
  'report.j2.typ': (d) =>
    d.title && d.company?.name && d.executive_summary,
}

const isComplete = (templateKey, data) => {
  const check = REQUIRED_FIELDS[templateKey]
  if (!check) return false
  try { return Boolean(check(data)) } catch { return false }
}

// Minimal starter shape — just enough structure, no field dump
const SCAFFOLDS = {
  'invoice.j2.typ': { sender: {}, recipient: {}, items: [] },
  'statement.j2.typ': { company: {}, customer: {}, transactions: [], aging: {} },
  'receipt.j2.typ': { company: {}, items: [], payment: {} },
  'letter.j2.typ': { sender: {}, recipient: {}, body_paragraphs: [] },
  'einvoice.j2.typ': { seller: {}, buyer: {}, items: [], tax_entries: [], payment: {} },
  'report.j2.typ': { company: {}, metrics: [], incidents: [], spend_by_service: [], recommendations: [] },
}

/* ── Mini Ready Demo (landing page teaser) ───────────────────────── */
function ReadyDemo() {
  const [template, setTemplate] = useState('invoice.j2.typ')
  const [payloadMode, setPayloadMode] = useState('valid')
  const [json, setJson] = useState(() => JSON.stringify(FIXTURES['invoice.j2.typ'].valid, null, 2))
  const [parseError, setParseError] = useState(null)
  const [verdict, setVerdict] = useState(null)
  const [checking, setChecking] = useState(false)

  const switchFixture = (tpl, mode) => {
    setTemplate(tpl); setPayloadMode(mode)
    setJson(JSON.stringify(FIXTURES[tpl][mode === 'valid' ? 'valid' : 'invalid'], null, 2))
    setVerdict(null)
  }

  useEffect(() => {
    try { JSON.parse(json); setParseError(null) }
    catch (e) { setParseError(e.message.split(' at ')[0]) }
  }, [json])

  const runPreflight = async () => {
    if (parseError) return
    setChecking(true); setVerdict(null)
    try {
      const data = JSON.parse(json)
      const res = await fetch(apiUrl('/preflight'), {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ template, data }),
      })
      setVerdict(await res.json()); setChecking(false)
    } catch {
      setVerdict({ ready: false, errors: [{ stage: 'network', check: 'unreachable', severity: 'error', path: 'server', message: 'Server unreachable. Is trustrender serve running on port 8190?' }], warnings: [], stages_checked: [] })
      setChecking(false)
    }
  }

  return (
    <section id="playground" className="py-20 md:py-28 bg-surface border-t border-rule">
      <div className="max-w-[1280px] mx-auto px-6 md:px-10">
        <FadeUp>
          <p className="text-[11px] tracking-[0.22em] uppercase text-rust mb-4 font-semibold">Try it</p>
          <h2 className="font-display font-extrabold text-[28px] md:text-[40px] tracking-[-0.03em] leading-[1.08] mb-3">
            Check readiness before render.
          </h2>
          <p className="text-[15px] text-mid max-w-md leading-relaxed mb-10">
            Toggle to an invalid payload and see what TrustRender catches before the renderer is ever invoked.
          </p>
        </FadeUp>

        <FadeUp delay={200}>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
            {/* Editor */}
            <div className="bg-panel rounded-xl border border-rule-light overflow-hidden" style={{ boxShadow: '0 2px 8px rgba(20,18,16,0.04)' }}>
              <div className="px-4 py-2.5 border-b border-rule-light flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="flex gap-1.5"><div className="w-2 h-2 rounded-full bg-rule" /><div className="w-2 h-2 rounded-full bg-rule" /><div className="w-2 h-2 rounded-full bg-rule" /></div>
                  <span className="text-[10px] font-mono text-muted ml-2">payload</span>
                </div>
                <div className="flex items-center gap-2">
                  <select value={template} onChange={e => switchFixture(e.target.value, payloadMode)} className="text-[10px] font-mono text-muted bg-transparent border border-rule rounded px-2 py-1 cursor-pointer">
                    {Object.entries(FIXTURES).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
                  </select>
                  <span className="text-[9px] text-muted">example</span>
                  <div className="flex rounded-full border border-rule overflow-hidden">
                    <button onClick={() => switchFixture(template, 'valid')}
                      className={`text-[9px] px-2.5 py-1 font-medium cursor-pointer transition-colors
                        ${payloadMode === 'valid' ? 'bg-sage/10 text-sage' : 'text-muted hover:text-mid'}`}>
                      passing
                    </button>
                    <button onClick={() => switchFixture(template, 'invalid')}
                      className={`text-[9px] px-2.5 py-1 font-medium cursor-pointer transition-colors
                        ${payloadMode === 'invalid' ? 'bg-wine/10 text-wine' : 'text-muted hover:text-mid'}`}>
                      broken
                    </button>
                  </div>
                </div>
              </div>
              <textarea value={json} onChange={e => setJson(e.target.value)} spellCheck={false} wrap="off"
                className="w-full p-4 font-mono text-[11px] leading-[1.8] text-ink-2 bg-panel resize-none focus:outline-none min-h-[320px] whitespace-pre overflow-x-auto"
                style={{ tabSize: 2 }} />
              {parseError && <div className="px-4 py-2 border-t border-wine/20 bg-wine/[0.04] text-[11px] text-wine font-mono">JSON: {parseError}</div>}
              {payloadMode === 'invalid' && !parseError && (
                <div className="px-4 py-2 border-t border-rule-light text-[10px] text-muted">Try the broken payload to see what Ready catches.</div>
              )}
              <div className="px-4 py-3 border-t border-rule-light flex items-center gap-3">
                <button onClick={runPreflight} disabled={!!parseError || checking}
                  className={`text-[12px] px-5 py-2.5 rounded-full font-medium transition-all cursor-pointer ${parseError ? 'bg-rule text-muted cursor-not-allowed' : checking ? 'bg-ink/70 text-panel cursor-wait' : 'bg-ink text-panel hover:bg-ink-2'}`}>
                  {checking ? 'Checking\u2026' : 'Check readiness'}
                </button>
              </div>
            </div>

            {/* Verdict */}
            <div className="bg-panel rounded-xl border border-rule-light overflow-hidden min-h-[420px] flex flex-col" style={{ boxShadow: '0 2px 8px rgba(20,18,16,0.04)' }}>
              <div className="px-4 py-2.5 border-b border-rule-light flex items-center justify-between">
                <span className="text-[10px] font-mono text-muted">readiness</span>
                {verdict && (
                  <span className={`text-[10px] font-medium ${verdict.ready ? 'text-sage' : 'text-wine'}`}>
                    {verdict.ready ? 'ready' : `${verdict.errors.length} issue${verdict.errors.length !== 1 ? 's' : ''}`}
                  </span>
                )}
              </div>
              <div className="flex-1 flex items-start p-4 overflow-y-auto">
                {!verdict && !checking && (
                  <div className="w-full text-center py-16">
                    <div className="w-12 h-12 mx-auto mb-4 rounded-full border-2 border-rule flex items-center justify-center">
                      <svg className="w-5 h-5 text-rule" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5"><path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    </div>
                    <p className="text-[13px] text-muted">Click &ldquo;Check readiness&rdquo; to validate</p>
                  </div>
                )}
                {checking && (
                  <div className="w-full text-center py-16">
                    <div className="w-48 h-1.5 bg-rule rounded-full overflow-hidden mx-auto mb-4"><div className="h-full bg-ink/30 rounded-full shimmer-bar" /></div>
                    <p className="text-[13px] text-muted font-medium">Checking&hellip;</p>
                  </div>
                )}
                {verdict && (
                  <div className="w-full space-y-4">
                    {/* Verdict badge */}
                    <div className={`flex items-center gap-3 px-4 py-3 rounded-lg border ${verdict.ready ? 'bg-sage/[0.06] border-sage/20' : 'bg-wine/[0.04] border-wine/20'}`}>
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center ${verdict.ready ? 'bg-sage/15' : 'bg-wine/10'}`}>
                        {verdict.ready
                          ? <svg className="w-4 h-4 text-sage" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5"><path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" /></svg>
                          : <svg className="w-4 h-4 text-wine" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5"><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
                        }
                      </div>
                      <div>
                        <div className={`text-[14px] font-semibold ${verdict.ready ? 'text-sage' : 'text-wine'}`}>
                          {verdict.ready ? 'Ready to render' : 'Not ready'}
                        </div>
                        <div className="text-[11px] text-muted">
                          {verdict.stages_checked?.length || 0} stages checked
                          {verdict.warnings?.length > 0 && ` \u00b7 ${verdict.warnings.length} warning${verdict.warnings.length !== 1 ? 's' : ''}`}
                        </div>
                      </div>
                    </div>

                    {/* Errors */}
                    {verdict.errors?.length > 0 && (
                      <div className="space-y-1.5">
                        {verdict.errors.map((e, i) => (
                          <div key={i} className="border-l-[3px] border-wine/30 pl-3 py-2 rounded-r-sm bg-wine/[0.03]">
                            <div className="flex items-center gap-2">
                              <span className="text-[9px] px-1.5 py-0.5 rounded bg-wine/10 text-wine font-mono">{e.stage}</span>
                              <span className="font-mono text-[12px] font-semibold text-ink">{e.path}</span>
                            </div>
                            <div className="text-[11px] text-mid mt-0.5">{e.message}</div>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Warnings */}
                    {verdict.warnings?.length > 0 && (
                      <div className="space-y-1.5">
                        {verdict.warnings.map((w, i) => (
                          <div key={i} className="border-l-[3px] border-rust/30 pl-3 py-2 rounded-r-sm bg-rust/[0.03]">
                            <div className="flex items-center gap-2">
                              <span className="text-[9px] px-1.5 py-0.5 rounded bg-rust/10 text-rust font-mono">{w.stage}</span>
                              <span className="font-mono text-[12px] font-semibold text-ink">{w.path}</span>
                            </div>
                            <div className="text-[11px] text-mid mt-0.5">{w.message}</div>
                          </div>
                        ))}
                      </div>
                    )}

                    {verdict.ready && <p className="text-[11px] text-sage border-l-2 border-sage/30 pl-3">All checks passed. This payload is ready to render.</p>}
                    {!verdict.ready && <p className="text-[11px] text-mid border-l-2 border-rule pl-3">Fix the issues above. No PDF was generated.</p>}
                  </div>
                )}
              </div>
              <div className="px-4 py-3 border-t border-rule-light">
                <a href="#app" className="flex items-center justify-between gap-3 group px-4 py-2.5 -mx-1 rounded-lg bg-rust/8 hover:bg-rust/15 transition-colors">
                  <span className="text-[12px] text-rust font-semibold">Try the full playground</span>
                  <span className="text-[11px] text-rust/60 font-mono group-hover:text-rust transition-colors">Ready &middot; Generate &middot; History &rarr;</span>
                </a>
              </div>
            </div>
          </div>
        </FadeUp>
      </div>
    </section>
  )
}

/* ── Full App Workspace (at #app) ────────────────────────────────── */
function AppWorkspace() {
  const [tab, setTab] = useState('ready')
  const [template, setTemplate] = useState('')
  const [payloadMode, setPayloadMode] = useState('valid')
  const [json, setJson] = useState('{\n  \n}')
  const [parseError, setParseError] = useState(null)

  // Server templates — discovered from /templates endpoint
  const [serverTemplates, setServerTemplates] = useState(null) // null=loading, []=none
  const [serverLoaded, setServerLoaded] = useState(false)

  useEffect(() => {
    fetch(apiUrl('/templates'))
      .then(res => res.ok ? res.json() : null)
      .then(data => {
        if (data?.templates?.length) {
          setServerTemplates(data.templates)
        } else {
          setServerTemplates([])
        }
        setServerLoaded(true)
      })
      .catch(() => {
        setServerTemplates([])
        setServerLoaded(true)
      })
  }, [])

  const loadServerTemplate = async (tpl) => {
    setVerdict(null); setRenderStatus('idle'); setPdfData(null); setRenderError(null)
    setPayloadMode('valid')
    // Fetch template source
    try {
      const srcRes = await fetch(apiUrl(`/template-source?name=${encodeURIComponent(tpl)}`))
      if (srcRes.ok) {
        const { source } = await srcRes.json()
        setTemplateSource(source); setOriginalSource(source)
      }
    } catch {}
    // Fetch matching data file
    try {
      const dataRes = await fetch(apiUrl(`/template-data?name=${encodeURIComponent(tpl)}`))
      if (dataRes.ok) {
        const { data } = await dataRes.json()
        if (data) {
          setJson(JSON.stringify(data, null, 2))
          return
        }
      }
    } catch {}
    // Fallback to fixture data if available
    if (FIXTURES[tpl]) {
      setJson(JSON.stringify(FIXTURES[tpl].valid, null, 2))
    } else {
      setJson('{\n  \n}')
    }
  }

  // Error-to-editor mapping
  const [pathIndex, setPathIndex] = useState(null)
  const dataScrollToLine = useRef(null)
  const templateScrollToLine = useRef(null)

  // Template editor state
  const [editorTab, setEditorTab] = useState('data') // 'data' | 'template'
  const [templateSource, setTemplateSource] = useState('')
  const [originalSource, setOriginalSource] = useState('')
  const [sourceLoading, setSourceLoading] = useState(false)

  // Ready state
  const [verdict, setVerdict] = useState(null)
  const [checking, setChecking] = useState(false)
  const preflightTimer = useRef(null)

  // Generate state
  const [renderStatus, setRenderStatus] = useState('idle')
  const [pdfData, setPdfData] = useState(null)
  const [currentPage, setCurrentPage] = useState(1)
  const [renderError, setRenderError] = useState(null)
  const [traceId, setTraceId] = useState(null)

  // Outputs state — session-local render bundles
  const [outputBundles, setOutputBundles] = useState([])
  const MAX_BUNDLES = 50

  // History state
  const [traces, setTraces] = useState(null) // null=not loaded, []=empty, [...]=data
  const [historyError, setHistoryError] = useState(null) // 'disabled' or 'error'
  const [selectedTrace, setSelectedTrace] = useState(null)
  const [dashboardAvailable, setDashboardAvailable] = useState(false)

  // Probe /dashboard availability once
  useEffect(() => {
    fetch(apiUrl('/dashboard'), { method: 'HEAD' })
      .then(res => setDashboardAvailable(res.ok))
      .catch(() => setDashboardAvailable(false))
  }, [])

  const fetchTraces = async ({ autoSelect = false } = {}) => {
    try {
      const res = await fetch(apiUrl('/history?limit=50'))
      if (res.status === 503) { setHistoryError('disabled'); setTraces(null); return }
      if (!res.ok) { setHistoryError('error'); return }
      const data = await res.json()
      setTraces(data); setHistoryError(null)
      if (autoSelect && data.length > 0) setSelectedTrace(data[0])
    } catch { setHistoryError('error') }
  }

  // Refresh traces when History tab is selected — auto-select newest on first load
  useEffect(() => { if (tab === 'history') fetchTraces({ autoSelect: !selectedTrace }) }, [tab])

  // Refresh after any render completes (regardless of current tab) so History is fresh when user arrives
  const prevRenderStatus = useRef(renderStatus)
  useEffect(() => {
    if (prevRenderStatus.current === 'rendering' && (renderStatus === 'done' || renderStatus === 'error')) {
      fetchTraces({ autoSelect: tab === 'history' })
    }
    prevRenderStatus.current = renderStatus
  }, [renderStatus])

  const switchFixture = (tpl, mode) => {
    setTemplate(tpl); setPayloadMode(mode)
    // If it's a server-only template (not in FIXTURES), load from server
    if (!FIXTURES[tpl]) {
      loadServerTemplate(tpl)
      return
    }
    setJson(JSON.stringify(FIXTURES[tpl][mode === 'valid' ? 'valid' : 'invalid'], null, 2))
    setVerdict(null); setRenderStatus('idle'); setPdfData(null); setRenderError(null)
    // Template editor: fetch fresh source, clear modified state
    setTemplateSource(''); setOriginalSource('')
    fetchTemplateSource(tpl)
  }

  // Create blank draft from canonical schema — no demo data
  const selectDocType = (tpl) => {
    setTemplate(tpl)
    setPayloadMode('valid')
    setJson(JSON.stringify(SCAFFOLDS[tpl] || {}, null, 2))
    setVerdict(null); setRenderStatus('idle'); setPdfData(null); setRenderError(null)
    setParseError(null)
    setTemplateSource(''); setOriginalSource('')
    setEditorTab('data')
    fetchTemplateSource(tpl)
  }

  // Load sample data into current draft
  const loadSample = () => {
    if (FIXTURES[template]) {
      setJson(JSON.stringify(FIXTURES[template].valid, null, 2))
      setPayloadMode('valid')
    }
  }

  const startFresh = () => {
    setTemplate('')
    setPayloadMode('valid')
    setJson('{\n  \n}')
    setTemplateSource('')
    setOriginalSource('')
    setVerdict(null)
    setRenderStatus('idle')
    setPdfData(null)
    setRenderError(null)
    setParseError(null)
    setEditorTab('data')
    setTraceId(null)
    setSelectedTrace(null)
    setTab('ready')
  }

  const fetchTemplateSource = async (tpl) => {
    setSourceLoading(true)
    try {
      const res = await fetch(apiUrl(`/template-source?name=${encodeURIComponent(tpl)}`))
      if (res.ok) {
        const { source } = await res.json()
        setTemplateSource(source); setOriginalSource(source)
      }
    } catch { /* server unreachable — editor stays empty */ }
    setSourceLoading(false)
  }

  // Fetch template source on initial mount
  useEffect(() => { fetchTemplateSource(template) }, [])

  // JSON parse check + path index build
  useEffect(() => {
    try {
      JSON.parse(json)
      setParseError(null)
      // Build path index on successful parse (non-blocking)
      if (typeof requestIdleCallback !== 'undefined') {
        requestIdleCallback(() => setPathIndex(buildPathIndex(json)))
      } else {
        setTimeout(() => setPathIndex(buildPathIndex(json)), 0)
      }
    } catch (e) {
      setParseError(e.message.split(' at ')[0])
    }
  }, [json])

  // Auto-preflight on valid JSON / template source change
  // Request sequencing: only apply the latest response, ignore stale ones
  const jsonRef = useRef(json)
  const templateRef = useRef(template)
  const templateSourceRef = useRef(templateSource)
  const originalSourceRef = useRef(originalSource)
  const preflightSeq = useRef(0)
  jsonRef.current = json
  templateRef.current = template
  templateSourceRef.current = templateSource
  originalSourceRef.current = originalSource

  const templateSourceTimer = useRef(null)
  const isTemplateModified = templateSource !== originalSource && originalSource !== ''

  // Debounce: 500ms for data changes, 900ms for template source edits (burstier typing)
  useEffect(() => {
    if (parseError || !template) return
    if (preflightTimer.current) clearTimeout(preflightTimer.current)
    preflightTimer.current = setTimeout(() => { runPreflight() }, 500)
    return () => clearTimeout(preflightTimer.current)
  }, [json, template])

  useEffect(() => {
    if (parseError || !originalSource) return
    if (templateSourceTimer.current) clearTimeout(templateSourceTimer.current)
    templateSourceTimer.current = setTimeout(() => { runPreflight() }, 900)
    return () => clearTimeout(templateSourceTimer.current)
  }, [templateSource])

  const runPreflight = async () => {
    let data
    try { data = JSON.parse(jsonRef.current) } catch { return }
    const tpl = templateRef.current
    const src = templateSourceRef.current
    const origSrc = originalSourceRef.current
    const modified = src !== origSrc && origSrc !== ''
    const seq = ++preflightSeq.current
    setChecking(true)
    const payload = { template: tpl, data }
    if (modified) payload.template_source = src
    const fixtureZugferd = FIXTURES[tpl]?.zugferd
    if (fixtureZugferd) payload.zugferd = fixtureZugferd
    try {
      const res = await fetch(apiUrl('/preflight'), {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (seq !== preflightSeq.current) return // stale response, discard
      setVerdict(await res.json())
    } catch {
      if (seq !== preflightSeq.current) return
      setVerdict({ ready: false, errors: [{ stage: 'network', check: 'unreachable', severity: 'error', path: 'server', message: 'Server unreachable' }], warnings: [], stages_checked: [] })
    }
    if (seq === preflightSeq.current) setChecking(false)
  }

  // Error-to-editor navigation
  const handleErrorClick = useCallback((issue) => {
    const location = resolveErrorLocation(issue, pathIndex, templateSource)
    if (!location || !location.navigable) return

    if (location.editor === 'data') {
      setEditorTab('data')
      // Small delay to let tab switch render the editor
      setTimeout(() => { dataScrollToLine.current?.(location.line) }, 50)
    } else if (location.editor === 'template') {
      setEditorTab('template')
      setTimeout(() => { templateScrollToLine.current?.(location.line) }, 50)
    }
  }, [pathIndex, templateSource])

  const isErrorNavigable = useCallback((issue) => {
    const location = resolveErrorLocation(issue, pathIndex, templateSource)
    return location?.navigable ?? false
  }, [pathIndex, templateSource])

  const renderPdf = async () => {
    if (parseError) return
    setRenderStatus('rendering'); setRenderError(null); setCurrentPage(1); setTraceId(null)
    if (pdfData?.downloadUrl) URL.revokeObjectURL(pdfData.downloadUrl)
    setPdfData(null)

    // Freeze render-time state for bundle
    const frozenTemplate = template
    const frozenSource = templateSource
    const frozenJson = JSON.stringify(JSON.parse(json), null, 2)

    try {
      const data = JSON.parse(json)
      const renderPayload = { template, data, validate: true, debug: true }
      if (isTemplateModified) renderPayload.template_source = templateSource
      const fixtureZugferd = FIXTURES[template]?.zugferd
      if (fixtureZugferd) renderPayload.zugferd = fixtureZugferd
      const res = await fetch(apiUrl('/render'), {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(renderPayload),
      })
      const resTraceId = res.headers.get('X-Trace-ID') || null
      if (resTraceId) setTraceId(resTraceId)
      if (res.ok) {
        const buf = await res.arrayBuffer()
        const uint8 = new Uint8Array(buf)
        const downloadUrl = URL.createObjectURL(new Blob([uint8], { type: 'application/pdf' }))
        const pdf = await pdfjsLib.getDocument({ data: uint8.slice() }).promise
        const pages = []
        for (let i = 1; i <= pdf.numPages; i++) {
          const page = await pdf.getPage(i)
          const vp = page.getViewport({ scale: 2 })
          const canvas = document.createElement('canvas')
          canvas.width = vp.width; canvas.height = vp.height
          await page.render({ canvasContext: canvas.getContext('2d'), viewport: vp }).promise
          pages.push(canvas.toDataURL('image/png'))
        }
        setPdfData({ pages, totalPages: pdf.numPages, downloadUrl })
        setRenderStatus('done')

        // Capture output bundle
        const bundle = {
          id: crypto.randomUUID(),
          timestamp: new Date().toISOString(),
          templateName: frozenTemplate,
          templateSource: frozenSource,
          jsonData: frozenJson,
          pdfBytes: uint8,
          traceId: resTraceId,
          trace: null,
          outcome: 'success',
        }
        // Best-effort trace fetch
        if (resTraceId) {
          try {
            const tr = await fetch(apiUrl(`/history/${resTraceId}`))
            if (tr.ok) bundle.trace = await tr.json()
          } catch { /* trace is optional */ }
        }
        setOutputBundles(prev => [bundle, ...prev].slice(0, MAX_BUNDLES))
      } else {
        const errData = await res.json()
        setRenderError(errData); setRenderStatus('error')
        // Record failed render (no pdfBytes)
        setOutputBundles(prev => [{
          id: crypto.randomUUID(),
          timestamp: new Date().toISOString(),
          templateName: frozenTemplate,
          templateSource: frozenSource,
          jsonData: frozenJson,
          pdfBytes: null,
          traceId: resTraceId,
          trace: null,
          outcome: 'error',
          errorMessage: errData.message || 'Render failed',
        }, ...prev].slice(0, MAX_BUNDLES))
      }
    } catch (e) {
      const isNet = e instanceof TypeError && e.message.includes('fetch')
      setRenderError({ error: isNet ? 'NETWORK' : 'RENDER_ERROR', message: isNet ? 'Server unreachable' : e.message })
      setRenderStatus('error')
    }
  }

  // ── ZIP bundle helpers ──
  const makeProvenance = (bundle) => JSON.stringify({
    version: '0.1.0',
    engine: 'TrustRender',
    timestamp: bundle.timestamp,
    template: bundle.templateName,
    hashes: {
      template: bundle.trace?.template_hash || 'unavailable',
      data: bundle.trace?.data_hash || 'unavailable',
      output_pdf: bundle.trace?.output_hash || 'unavailable',
    },
    outcome: bundle.outcome,
    duration_ms: bundle.trace?.total_ms || null,
  }, null, 2)

  const downloadBundle = async (bundle) => {
    const zip = new JSZip()
    const ts = bundle.timestamp.replace(/[:.]/g, '-').slice(0, 19)
    const fileLabel = bundleDisplayName(bundle.templateName, bundle.jsonData).toLowerCase().replace(/[^a-z0-9]+/g, '-')
    const folderName = `trustrender-${fileLabel}-${ts}`
    const folder = zip.folder(folderName)
    if (bundle.pdfBytes) folder.file(`${fileLabel}.pdf`, bundle.pdfBytes)
    folder.file(bundle.templateName, bundle.templateSource)
    folder.file('data.json', bundle.jsonData)
    if (bundle.trace) folder.file('trace.json', JSON.stringify(bundle.trace, null, 2))
    folder.file('provenance.json', makeProvenance(bundle))
    const blob = await zip.generateAsync({ type: 'blob' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = `${folderName}.zip`; a.click()
    URL.revokeObjectURL(url)
  }

  const downloadAllBundles = async () => {
    const zip = new JSZip()
    for (const b of outputBundles.filter(b => b.outcome === 'success')) {
      const ts = b.timestamp.replace(/[:.]/g, '-').slice(0, 19)
      const bFileLabel = bundleDisplayName(b.templateName, b.jsonData).toLowerCase().replace(/[^a-z0-9]+/g, '-')
      const folder = zip.folder(`${bFileLabel}-${ts}`)
      if (b.pdfBytes) folder.file(`${bFileLabel}.pdf`, b.pdfBytes)
      folder.file(b.templateName, b.templateSource)
      folder.file('data.json', b.jsonData)
      if (b.trace) folder.file('trace.json', JSON.stringify(b.trace, null, 2))
      folder.file('provenance.json', makeProvenance(b))
    }
    const blob = await zip.generateAsync({ type: 'blob' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = `trustrender-session-${new Date().toISOString().slice(0, 10)}.zip`; a.click()
    URL.revokeObjectURL(url)
  }

  const STAGES = ['payload', 'template', 'environment', 'compliance', 'semantic']
  const STAGE_SKIP_INFO = {
    compliance: { label: 'optional', reason: 'Enable with a compliance profile' },
    semantic: { label: 'optional', reason: 'Enable with semantic hints for this template' },
  }

  const stageStatus = (stageName) => {
    if (!verdict) return 'unchecked'
    if (!verdict.stages_checked?.includes(stageName)) return 'skipped'
    if (verdict.errors?.some(e => e.stage === stageName)) return 'fail'
    if (verdict.warnings?.some(w => w.stage === stageName)) return 'warn'
    return 'pass'
  }

  const StageIcon = ({ status }) => {
    if (status === 'pass') return <svg className="w-3.5 h-3.5 text-sage" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5"><path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" /></svg>
    if (status === 'fail') return <svg className="w-3.5 h-3.5 text-wine" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5"><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
    if (status === 'warn') return <div className="w-3 h-3 rounded-full bg-rust/30 flex items-center justify-center"><div className="w-1.5 h-1.5 rounded-full bg-rust" /></div>
    if (status === 'skipped') return <div className="w-3.5 h-3.5 rounded-full border-[1.5px] border-dashed border-muted" />
    return <div className="w-3 h-3 rounded-full border border-rule-light" />
  }

  return (
    <div className="min-h-screen bg-bg">
      {/* Header */}
      <header className="border-b border-rule-light bg-panel">
        <div className="max-w-[1280px] mx-auto px-6 md:px-10 flex items-center justify-between h-14">
          <div className="flex items-center gap-4">
            <a href="#" className="flex items-center gap-2.5">
              <AnimatedLogo size="small" />
            </a>
            <button onClick={startFresh}
              className="text-[11px] text-muted hover:text-ink px-3 py-1.5 rounded-md border border-rule-light hover:border-rule transition-colors cursor-pointer font-medium">
              New draft
            </button>
          </div>
          <div className="flex items-center gap-1 bg-surface rounded-lg p-1 border border-rule-light">
            {[['ready', 'Ready'], ['generate', 'Generate'], ['outputs', 'Outputs'], ['history', 'History']].map(([key, label]) => (
              <button key={key} onClick={() => setTab(key)}
                className={`text-[13px] px-4 py-1.5 rounded-md font-medium transition-colors cursor-pointer
                  ${tab === key ? 'bg-panel text-ink shadow-sm' : 'text-muted hover:text-mid'}`}>
                {label}
                {key === 'ready' && verdict && !checking && (
                  <span className={`ml-1.5 inline-block w-1.5 h-1.5 rounded-full ${verdict.ready ? 'bg-sage' : 'bg-wine'}`} />
                )}
                {key === 'outputs' && outputBundles.length > 0 && (
                  <span className="ml-1.5 text-[10px] font-mono text-muted">{outputBundles.length}</span>
                )}
              </button>
            ))}
          </div>
        </div>
      </header>

      <div className="max-w-[1280px] mx-auto px-6 md:px-10 py-8">
        {/* Shared: template selector + editor */}
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.2fr] gap-6 items-start">
          {/* Left: Editor (shared across tabs) */}
          {!template ? (
          <div className="bg-panel rounded-xl border border-rule-light overflow-hidden" style={{ boxShadow: '0 2px 8px rgba(20,18,16,0.04)' }}>
            <div className="px-4 py-3 border-b border-rule-light">
              <span className="text-[13px] font-semibold text-ink">Choose a document type</span>
            </div>
            <div className="divide-y divide-rule-light">
              {Object.entries(FIXTURES).map(([key, fix]) => (
                <button key={key} onClick={() => selectDocType(key)}
                  className="w-full px-4 py-3.5 flex items-center justify-between hover:bg-surface transition-colors cursor-pointer text-left">
                  <span className="text-[13px] font-medium text-ink">{fix.label}</span>
                  <svg className="w-4 h-4 text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5"><path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" /></svg>
                </button>
              ))}
            </div>
          </div>
          ) : (
          <div className="bg-panel rounded-xl border border-rule-light overflow-hidden" style={{ boxShadow: '0 2px 8px rgba(20,18,16,0.04)' }}>
            {/* Editor header: tab switcher + template selector */}
            <div className="px-4 py-2.5 border-b border-rule-light flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="flex gap-1.5"><div className="w-2 h-2 rounded-full bg-rule" /><div className="w-2 h-2 rounded-full bg-rule" /><div className="w-2 h-2 rounded-full bg-rule" /></div>
                <div className="flex items-center gap-0.5 ml-2 rounded-md border border-rule overflow-hidden">
                  <button onClick={() => setEditorTab('data')}
                    className={`text-[10px] font-mono px-2.5 py-1 cursor-pointer transition-colors
                      ${editorTab === 'data' ? 'bg-surface text-ink font-semibold' : 'text-muted hover:text-mid'}`}>
                    Data
                  </button>
                  <button onClick={() => setEditorTab('template')}
                    className={`text-[10px] font-mono px-2.5 py-1 cursor-pointer transition-colors flex items-center gap-1
                      ${editorTab === 'template' ? 'bg-surface text-ink font-semibold' : 'text-muted hover:text-mid'}`}>
                    Layout
                    {isTemplateModified && <span className="w-1.5 h-1.5 rounded-full bg-rust" />}
                  </button>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <select value={template} onChange={e => selectDocType(e.target.value)} className="text-[10px] font-mono text-muted bg-transparent border border-rule rounded px-2 py-1 cursor-pointer">
                  {Object.entries(FIXTURES).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
                </select>
                {(FIXTURES[template]?.zugferd || template.includes('einvoice')) && (
                  <span className="text-[8px] font-mono px-2 py-0.5 rounded-full bg-rust/10 text-rust font-semibold">EN 16931</span>
                )}
                {editorTab === 'data' && FIXTURES[template] && (
                  <button onClick={loadSample}
                    className="text-[9px] px-2.5 py-1 font-medium cursor-pointer text-muted hover:text-ink border border-rule rounded-full transition-colors">
                    Load sample
                  </button>
                )}
                {editorTab === 'template' && isTemplateModified && (
                  <button onClick={() => setTemplateSource(originalSource)}
                    className="text-[9px] px-2.5 py-1 font-medium cursor-pointer text-muted hover:text-ink border border-rule rounded-full transition-colors">
                    Reset
                  </button>
                )}
              </div>
            </div>

            {/* Data editor */}
            {editorTab === 'data' && (
              <>
                <CodeEditor
                  value={json}
                  onChange={setJson}
                  language="json"
                  onEditorReady={(scrollFn) => { dataScrollToLine.current = scrollFn }}
                  className="w-full min-h-[520px]"
                />
                {parseError && <div className="px-4 py-2 border-t border-wine/20 bg-wine/[0.04] text-[11px] text-wine font-mono">JSON: {parseError}</div>}
                {payloadMode === 'invalid' && !parseError && (
                  <div className="px-4 py-2 border-t border-rule-light text-[10px] text-muted">Try the broken payload to see what Ready catches.</div>
                )}
              </>
            )}

            {/* Template editor */}
            {editorTab === 'template' && (
              <>
                {sourceLoading ? (
                  <div className="p-4 min-h-[520px] flex items-center justify-center">
                    <span className="text-[11px] text-muted font-mono">Loading template...</span>
                  </div>
                ) : (
                  <CodeEditor
                    value={templateSource}
                    onChange={setTemplateSource}
                    language="plain"
                    onEditorReady={(scrollFn) => { templateScrollToLine.current = scrollFn }}
                    className="w-full min-h-[520px]"
                  />
                )}
                {/* Template compile errors from preflight */}
                {verdict && !checking && verdict.errors?.filter(e => ['template', 'template_preprocess', 'compilation', 'template_syntax'].includes(e.stage) || e.check?.includes('syntax')).length > 0 && (
                  <div className="px-4 py-2 border-t border-wine/20 bg-wine/[0.04]">
                    {verdict.errors.filter(e => ['template', 'template_preprocess', 'compilation', 'template_syntax'].includes(e.stage) || e.check?.includes('syntax')).map((e, i) => (
                      <div key={i} className="text-[11px] text-wine font-mono">{e.message}</div>
                    ))}
                  </div>
                )}
                <div className="px-4 py-1.5 border-t border-rule-light text-[9px] text-muted">
                  Edits are session-only and not saved to disk.
                </div>
              </>
            )}
          </div>
          )}

          {/* Right: Tab content */}
          <div>
            {/* ── READY TAB ── */}
            {tab === 'ready' && (
              <div className="space-y-4">
                {/* Verdict badge */}
                {checking && (
                  <div className="flex items-center gap-3 px-4 py-3 rounded-lg border border-rule-light bg-panel">
                    <div className="w-48 h-1.5 bg-rule rounded-full overflow-hidden"><div className="h-full bg-ink/30 rounded-full shimmer-bar" /></div>
                    <span className="text-[12px] text-muted">Checking readiness&hellip;</span>
                  </div>
                )}
                {verdict && !checking && (() => {
                  let parsedData; try { parsedData = JSON.parse(json) } catch { parsedData = null }
                  const dataFilled = parsedData && isComplete(template, parsedData)
                  const actuallyReady = verdict.ready && dataFilled
                  const incompleteButValid = verdict.ready && !dataFilled
                  return (
                  <div className={`flex items-center gap-4 px-5 py-4 rounded-lg border ${actuallyReady ? 'bg-sage/[0.06] border-sage/20' : incompleteButValid ? 'bg-surface border-rule-light' : 'bg-wine/[0.04] border-wine/20'}`}>
                    <div className={`w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 ${actuallyReady ? 'bg-sage/15' : incompleteButValid ? 'bg-rule/20' : 'bg-wine/10'}`}>
                      {actuallyReady
                        ? <svg className="w-4.5 h-4.5 text-sage" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5"><path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" /></svg>
                        : incompleteButValid
                        ? <svg className="w-4.5 h-4.5 text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5"><path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                        : <svg className="w-4.5 h-4.5 text-wine" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5"><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
                      }
                    </div>
                    <div className="flex-1">
                      <div className={`font-semibold ${actuallyReady ? 'text-[17px] text-sage' : incompleteButValid ? 'text-[14px] text-muted' : 'text-[14px] text-wine'}`}>
                        {actuallyReady ? 'Ready to render' : incompleteButValid ? 'Structure valid — fill in your data' : `${verdict.errors?.length || 0} issue${(verdict.errors?.length || 0) !== 1 ? 's' : ''} must be fixed`}
                      </div>
                      <div className="text-[11px] text-muted mt-0.5">
                        {verdict.stages_checked?.length || 0} stages checked
                        {verdict.warnings?.length > 0 && ` \u00b7 ${verdict.warnings.length} warning${verdict.warnings.length !== 1 ? 's' : ''}`}
                      </div>
                    </div>
                    {actuallyReady ? (
                      <button onClick={() => { setTab('generate'); setTimeout(renderPdf, 100) }}
                        className="text-[13px] px-5 py-2 rounded-full font-semibold bg-ink text-panel hover:bg-ink-2 transition-all cursor-pointer flex-shrink-0 shadow-sm hover:shadow-md">
                        Render PDF
                      </button>
                    ) : (
                      <div className="text-[10px] text-muted font-mono flex-shrink-0">{verdict.checked_at?.split('T')[1]?.split('.')[0] || ''}</div>
                    )}
                  </div>
                  )
                })()}
                {!verdict && !checking && (
                  <div className="flex items-center gap-3 px-4 py-3 rounded-lg border border-rule-light bg-panel">
                    <div className="w-8 h-8 rounded-full border-2 border-rule flex items-center justify-center flex-shrink-0">
                      <svg className="w-4 h-4 text-rule" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5"><path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    </div>
                    <div className="text-[13px] text-muted">Edit the payload to run readiness checks automatically</div>
                  </div>
                )}

                {/* Stage list */}
                {verdict && !checking && (
                  <div className="bg-panel rounded-xl border border-rule-light overflow-hidden" style={{ boxShadow: '0 2px 8px rgba(20,18,16,0.04)' }}>
                    <div className="px-4 py-2.5 border-b border-rule-light">
                      <span className="text-[10px] font-mono text-muted">stages</span>
                    </div>
                    <div className="divide-y divide-rule-light">
                      {STAGES.map(stage => {
                        const s = stageStatus(stage)
                        const issues = [...(verdict.errors?.filter(e => e.stage === stage) || []), ...(verdict.warnings?.filter(w => w.stage === stage) || [])]
                        return (
                          <div key={stage} className={`px-4 py-3 ${s === 'skipped' ? 'opacity-50' : ''}`}>
                            <div className="flex items-center gap-3">
                              <StageIcon status={s} />
                              <div className="flex-1 min-w-0">
                                <span className={`text-[13px] font-medium capitalize ${s === 'skipped' ? 'text-muted' : 'text-ink'}`}>{stage}</span>
                                {s === 'skipped' && STAGE_SKIP_INFO[stage] && (
                                  <div className="text-[10px] text-muted">{STAGE_SKIP_INFO[stage].reason}</div>
                                )}
                              </div>
                              <span className={`text-[10px] font-mono flex-shrink-0 ${s === 'pass' ? 'text-sage' : s === 'fail' ? 'text-wine' : s === 'warn' ? 'text-rust' : 'text-muted'}`}>
                                {s === 'pass' ? 'pass' : s === 'fail' ? 'fail' : s === 'warn' ? 'warn' : s === 'skipped' ? (STAGE_SKIP_INFO[stage]?.label || 'skipped') : ''}
                              </span>
                            </div>
                            {issues.length > 0 && (
                              <div className="mt-2 ml-6.5 space-y-1">
                                {issues.map((issue, i) => {
                                  const navigable = isErrorNavigable(issue)
                                  return (
                                    <div key={i}
                                      onClick={navigable ? () => handleErrorClick(issue) : undefined}
                                      className={`border-l-[3px] pl-3 py-1.5 rounded-r-sm ${issue.severity === 'error' ? 'border-wine/30 bg-wine/[0.03]' : 'border-rust/30 bg-rust/[0.03]'} ${navigable ? 'cursor-pointer hover:bg-wine/[0.06] transition-colors' : ''}`}
                                    >
                                      <div className="font-mono text-[11px] font-semibold text-ink">{issue.path}</div>
                                      <div className="text-[10px] text-mid">{issue.message}</div>
                                    </div>
                                  )
                                })}
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>

                    {/* Compliance eligibility */}
                    {verdict.profile_eligible?.length > 0 && (
                      <div className="px-4 py-3 border-t border-rule-light">
                        <div className="text-[10px] text-muted mb-2">Eligible compliance profiles</div>
                        <div className="flex gap-2">
                          {verdict.profile_eligible.map(p => (
                            <span key={p} className="text-[10px] px-2 py-1 rounded bg-sage/10 text-sage font-mono border border-sage/20">{p}</span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* ── GENERATE TAB ── */}
            {tab === 'generate' && (
              <div className="space-y-4">
                {/* Output */}
                <div className="bg-panel rounded-xl border border-rule-light overflow-hidden min-h-[480px] flex flex-col" style={{ boxShadow: '0 2px 8px rgba(20,18,16,0.04)' }}>
                  <div className="px-4 py-2.5 border-b border-rule-light flex items-center justify-between gap-3">
                    <span className="text-[11px] font-mono text-muted">{renderStatus === 'done' ? 'output.pdf' : renderStatus === 'rendering' ? 'rendering\u2026' : renderStatus === 'error' ? 'error' : 'output'}</span>
                    <div className="flex items-center gap-3">
                      {renderStatus === 'done' && pdfData && pdfData.totalPages > 1 && (
                        <div className="flex items-center gap-2">
                          <button onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={currentPage <= 1} className="text-[12px] text-muted hover:text-ink disabled:opacity-30 cursor-pointer disabled:cursor-default px-1">&larr;</button>
                          <span className="text-[11px] text-muted font-mono tabular-nums">{currentPage}/{pdfData.totalPages}</span>
                          <button onClick={() => setCurrentPage(p => Math.min(pdfData.totalPages, p + 1))} disabled={currentPage >= pdfData.totalPages} className="text-[12px] text-muted hover:text-ink disabled:opacity-30 cursor-pointer disabled:cursor-default px-1">&rarr;</button>
                        </div>
                      )}
                      {traceId && <span className="text-[10px] font-mono text-muted">trace: {traceId.slice(0, 8)}</span>}
                      {renderStatus === 'done' && <span className="text-[11px] text-sage font-medium">rendered</span>}
                      {renderStatus === 'error' && <span className="text-[11px] text-wine font-mono font-medium">{renderError?.error}</span>}
                      {pdfData?.downloadUrl && <a href={pdfData.downloadUrl} download="trustrender-demo.pdf" className="text-[12px] text-rust hover:text-wine font-medium">Download</a>}
                    </div>
                  </div>
                  <div className="flex-1 flex items-center justify-center p-4">
                    {renderStatus === 'idle' && (
                      <div className="text-center py-12">
                        {/* Document silhouette */}
                        <div className="w-[120px] mx-auto mb-6 rounded border border-rule-light bg-white/60 p-4 opacity-40" style={{ aspectRatio: '8.5/11' }}>
                          <div className="w-1/2 h-1.5 bg-rule/20 rounded-full mb-3" />
                          <div className="w-3/4 h-1 bg-rule/15 rounded-full mb-2" />
                          <div className="w-full h-1 bg-rule/15 rounded-full mb-2" />
                          <div className="w-2/3 h-1 bg-rule/15 rounded-full mb-4" />
                          <div className="w-full h-px bg-rule/10 mb-3" />
                          <div className="space-y-1.5">
                            <div className="flex gap-2"><div className="w-2/5 h-1 bg-rule/12 rounded-full" /><div className="flex-1 h-1 bg-rule/12 rounded-full" /></div>
                            <div className="flex gap-2"><div className="w-2/5 h-1 bg-rule/12 rounded-full" /><div className="flex-1 h-1 bg-rule/12 rounded-full" /></div>
                            <div className="flex gap-2"><div className="w-2/5 h-1 bg-rule/12 rounded-full" /><div className="flex-1 h-1 bg-rule/12 rounded-full" /></div>
                          </div>
                        </div>
                        <p className="text-[14px] text-muted font-medium mb-1.5">Your rendered PDF will appear here</p>
                        {verdict?.ready ? (
                          <button onClick={() => { renderPdf() }}
                            className="text-[12px] text-rust hover:text-wine font-medium cursor-pointer transition-colors">
                            Render now
                          </button>
                        ) : (
                          <button onClick={() => setTab('ready')}
                            className="text-[12px] text-rust hover:text-wine font-medium cursor-pointer transition-colors">
                            Run readiness checks first &rarr;
                          </button>
                        )}
                      </div>
                    )}
                    {renderStatus === 'rendering' && (
                      <div className="text-center py-16">
                        <div className="w-48 h-1.5 bg-rule rounded-full overflow-hidden mx-auto mb-4"><div className="h-full bg-ink/30 rounded-full shimmer-bar" /></div>
                        <p className="text-[13px] text-muted font-medium">Rendering&hellip;</p>
                      </div>
                    )}
                    {renderStatus === 'done' && pdfData && (
                      <div className="w-full flex flex-col items-center anim-doc">
                        <div className="relative w-full max-w-[480px]">
                          {pdfData.totalPages > 1 && currentPage < pdfData.totalPages && (
                            <><div className="absolute top-2 left-2 right-[-4px] bottom-[-4px] bg-white/60 rounded border border-rule/30" />
                            {pdfData.totalPages > 2 && currentPage < pdfData.totalPages - 1 && <div className="absolute top-4 left-4 right-[-8px] bottom-[-8px] bg-white/30 rounded border border-rule/20" />}</>
                          )}
                          <img src={pdfData.pages[currentPage - 1]} alt={`Page ${currentPage}`} className="relative w-full rounded bg-white border border-rule/40" style={{ boxShadow: '0 8px 24px rgba(20,18,16,0.08)' }} />
                        </div>
                        <div className="mt-3 text-[10px] text-muted">{pdfData.totalPages === 1 ? '1 page' : `${pdfData.totalPages} pages`}</div>
                      </div>
                    )}
                    {renderStatus === 'error' && renderError && (
                      <div className="p-4 w-full overflow-y-auto max-h-[520px]">
                        <div className="mb-5">
                          <div className="text-[15px] font-display text-wine mb-1">{renderError.error === 'DATA_CONTRACT' ? 'Payload intercepted before render' : renderError.error}</div>
                          <div className="text-[12px] text-mid">{renderError.message}</div>
                        </div>
                        {renderError.detail ? (
                          <pre className="font-mono text-[11px] text-ink-2 whitespace-pre-wrap leading-relaxed bg-wine/[0.03] border-l-[3px] border-wine/30 pl-4 py-3 rounded-r-sm">{renderError.detail}</pre>
                        ) : null}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* ── OUTPUTS TAB ── */}
            {tab === 'outputs' && (
              <div className="space-y-4">
                {outputBundles.length === 0 ? (
                  <div className="bg-panel rounded-xl border border-rule-light p-8 text-center" style={{ boxShadow: '0 2px 8px rgba(20,18,16,0.04)' }}>
                    <div className="w-12 h-12 mx-auto mb-4 rounded-full border-2 border-rule-light flex items-center justify-center text-muted text-[18px]">{'\u2193'}</div>
                    <p className="text-[13px] text-mid mb-1">No renders in this session yet.</p>
                    <p className="text-[12px] text-muted">Render a document from the Ready tab to see output bundles here.</p>
                    <p className="text-[10px] text-muted/50 mt-3">Session outputs — stored in browser, cleared on refresh.</p>
                  </div>
                ) : (
                  <div className="bg-panel rounded-xl border border-rule-light overflow-hidden" style={{ boxShadow: '0 2px 8px rgba(20,18,16,0.04)' }}>
                    <div className="px-4 py-2.5 border-b border-rule-light flex items-center justify-between">
                      <span className="text-[10px] font-mono text-muted">{outputBundles.length} bundle{outputBundles.length !== 1 ? 's' : ''} <span className="text-muted/40">· session only</span></span>
                      <div className="flex items-center gap-2">
                        <button onClick={() => setOutputBundles([])} className="text-[10px] text-muted hover:text-ink cursor-pointer">Clear</button>
                        {outputBundles.some(b => b.outcome === 'success') && (
                          <button onClick={downloadAllBundles} className="text-[11px] px-3 py-1 rounded-md border border-rule-light hover:border-rule text-muted hover:text-ink font-medium cursor-pointer transition-colors">
                            Download all
                          </button>
                        )}
                      </div>
                    </div>
                    <div className="divide-y divide-rule-light">
                      {outputBundles.map(b => (
                        <div key={b.id} className="px-4 py-3 flex items-center gap-3">
                          <div className={`w-2 h-2 rounded-full ${b.outcome === 'success' ? 'bg-sage' : 'bg-wine'}`} />
                          <div className="flex-1 min-w-0">
                            <div className="text-[13px] font-semibold text-ink truncate">{bundleDisplayName(b.templateName, b.jsonData)}</div>
                            <div className="text-[10px] text-muted font-mono">{new Date(b.timestamp).toLocaleTimeString()}{b.trace ? ` · ${b.trace.total_ms}ms` : ''}</div>
                          </div>
                          <span className={`text-[10px] font-mono font-semibold ${b.outcome === 'success' ? 'text-sage' : 'text-wine'}`}>{b.outcome}</span>
                          {b.outcome === 'success' ? (
                            <button onClick={() => downloadBundle(b)} className="text-[11px] text-rust hover:text-wine font-medium cursor-pointer ml-2">
                              ZIP
                            </button>
                          ) : (
                            <span className="text-[10px] text-muted/40 ml-2">{b.errorMessage || 'failed'}</span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* ── HISTORY TAB ── */}
            {tab === 'history' && (
              <div className="space-y-4">
                {/* Disabled state */}
                {historyError === 'disabled' && (
                  <div className="bg-panel rounded-xl border border-rule-light overflow-hidden min-h-[480px] flex items-center justify-center" style={{ boxShadow: '0 2px 8px rgba(20,18,16,0.04)' }}>
                    <div className="text-center py-16 px-8">
                      <div className="w-12 h-12 mx-auto mb-4 rounded-full border-2 border-rule flex items-center justify-center">
                        <svg className="w-5 h-5 text-rule" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5"><path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                      </div>
                      <p className="text-[14px] font-semibold text-ink mb-2">History not enabled</p>
                      <p className="text-[12px] text-muted max-w-xs mx-auto leading-relaxed">
                        Start the server with <code className="font-mono text-[11px] bg-surface px-1 py-0.5 rounded">--history ~/.trustrender/history.db</code> to enable render trace storage.
                      </p>
                    </div>
                  </div>
                )}

                {/* Loading */}
                {!historyError && traces === null && (
                  <div className="flex items-center gap-3 px-4 py-3 rounded-lg border border-rule-light bg-panel">
                    <div className="w-48 h-1.5 bg-rule rounded-full overflow-hidden"><div className="h-full bg-ink/30 rounded-full shimmer-bar" /></div>
                    <span className="text-[12px] text-muted">Loading traces&hellip;</span>
                  </div>
                )}

                {/* Empty state */}
                {!historyError && traces && traces.length === 0 && (
                  <div className="bg-panel rounded-xl border border-rule-light overflow-hidden min-h-[480px] flex items-center justify-center" style={{ boxShadow: '0 2px 8px rgba(20,18,16,0.04)' }}>
                    <div className="text-center py-16 px-8">
                      <div className="w-12 h-12 mx-auto mb-4 rounded-full border-2 border-rule flex items-center justify-center">
                        <svg className="w-5 h-5 text-rule" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5"><path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                      </div>
                      <p className="text-[14px] font-semibold text-ink mb-2">No renders yet</p>
                      <p className="text-[12px] text-muted">Render a document from the Ready tab to see trace history here.</p>
                    </div>
                  </div>
                )}

                {/* Trace list */}
                {!historyError && traces && traces.length > 0 && (
                  <div className="bg-panel rounded-xl border border-rule-light overflow-hidden" style={{ boxShadow: '0 2px 8px rgba(20,18,16,0.04)' }}>
                    <div className="px-4 py-2.5 border-b border-rule-light flex items-center justify-between">
                      <span className="text-[10px] font-mono text-muted">{traces.length} trace{traces.length !== 1 ? 's' : ''}</span>
                      <div className="flex items-center gap-3">
                        {dashboardAvailable && (
                          <a href={apiUrl('/dashboard')} target="_blank" rel="noopener noreferrer" className="text-[10px] text-muted hover:text-ink">Open dashboard &rarr;</a>
                        )}
                        <button onClick={fetchTraces} className="text-[10px] text-muted hover:text-ink cursor-pointer">refresh</button>
                      </div>
                    </div>
                    <div className="divide-y divide-rule-light max-h-[300px] overflow-y-auto">
                      {traces.map(t => (
                        <button key={t.id} onClick={() => setSelectedTrace(t)}
                          className={`w-full px-4 py-3 flex items-center gap-3 text-left cursor-pointer transition-colors hover:bg-surface/50
                            ${selectedTrace?.id === t.id ? 'bg-surface/80' : ''}`}>
                          <div className={`w-2 h-2 rounded-full flex-shrink-0 ${t.outcome === 'success' ? 'bg-sage' : 'bg-wine'}`} />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className={`text-[12px] font-medium truncate ${t.outcome === 'error' ? 'text-wine' : 'text-ink'}`}>{t.template_name}</span>
                              {t.zugferd_profile && <span className="text-[8px] px-1.5 py-0.5 rounded bg-sage/10 text-sage font-mono flex-shrink-0">{t.zugferd_profile}</span>}
                              {t.provenance_hash && <span className="text-[8px] px-1.5 py-0.5 rounded bg-rust/10 text-rust font-mono flex-shrink-0">prov</span>}
                            </div>
                            <div className="text-[10px] text-muted">
                              {t.timestamp?.split('T')[1]?.split('.')[0] || ''}
                              {t.total_ms != null && ` \u00b7 ${t.total_ms}ms`}
                              {t.outcome === 'error' && t.error_code && ` \u00b7 ${t.error_code}`}
                            </div>
                          </div>
                          <span className={`text-[10px] font-mono flex-shrink-0 ${t.outcome === 'success' ? 'text-sage' : 'text-wine'}`}>{t.outcome}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Selected trace detail */}
                {selectedTrace && (
                  <div className="bg-panel rounded-xl border border-rule-light overflow-hidden" style={{ boxShadow: '0 2px 8px rgba(20,18,16,0.04)' }}>
                    <div className="px-4 py-2.5 border-b border-rule-light flex items-center justify-between">
                      <span className="text-[10px] font-mono text-muted">trace: {selectedTrace.id?.slice(0, 8)}</span>
                      <button onClick={() => setSelectedTrace(null)} className="text-[10px] text-muted hover:text-ink cursor-pointer">close</button>
                    </div>
                    <div className="p-4 space-y-3">
                      {/* Metadata */}
                      <div className="grid grid-cols-2 gap-x-6 gap-y-2">
                        {[
                          ['Template', selectedTrace.template_name],
                          ['Outcome', selectedTrace.outcome],
                          ['Duration', selectedTrace.total_ms != null ? `${selectedTrace.total_ms}ms` : '\u2014'],
                          ['PDF size', selectedTrace.pdf_size ? `${(selectedTrace.pdf_size / 1024).toFixed(1)} KB` : '\u2014'],
                          ['Backend', selectedTrace.backend || '\u2014'],
                          ['Validated', selectedTrace.validated ? 'yes' : 'no'],
                          ['ZUGFeRD', selectedTrace.zugferd_profile || '\u2014'],
                          ['Provenance', selectedTrace.provenance_hash ? 'yes' : 'no'],
                        ].map(([label, value]) => (
                          <div key={label} className="flex items-baseline gap-2">
                            <span className="text-[10px] text-muted w-16 flex-shrink-0">{label}</span>
                            <span className={`text-[11px] font-mono ${value === 'success' ? 'text-sage' : value === 'error' ? 'text-wine' : 'text-ink'}`}>{value}</span>
                          </div>
                        ))}
                      </div>

                      {/* Error info */}
                      {selectedTrace.outcome === 'error' && selectedTrace.error_message && (
                        <div className="border-l-[3px] border-wine/30 pl-3 py-2 rounded-r-sm bg-wine/[0.03]">
                          <div className="text-[10px] text-muted mb-0.5">stage: {selectedTrace.error_stage}</div>
                          <div className="font-mono text-[11px] text-wine">{selectedTrace.error_code}</div>
                          <div className="text-[11px] text-mid mt-0.5">{selectedTrace.error_message}</div>
                        </div>
                      )}

                      {/* Stages */}
                      {selectedTrace.stages?.length > 0 && (
                        <div>
                          <div className="text-[10px] text-muted mb-2">Pipeline stages</div>
                          <div className="space-y-1">
                            {selectedTrace.stages.map((s, i) => (
                              <div key={i} className="flex items-center gap-2 py-1">
                                <div className={`w-2 h-2 rounded-full flex-shrink-0 ${s.status === 'pass' ? 'bg-sage' : s.status === 'fail' || s.status === 'error' ? 'bg-wine' : s.status === 'skip' ? 'bg-rule' : 'bg-rust'}`} />
                                <span className="text-[11px] text-ink flex-1">{s.stage}</span>
                                <span className={`text-[10px] font-mono ${s.status === 'pass' ? 'text-sage' : s.status === 'fail' || s.status === 'error' ? 'text-wine' : 'text-muted'}`}>{s.status}</span>
                                {s.duration_ms != null && <span className="text-[10px] font-mono text-muted">{s.duration_ms}ms</span>}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Identity */}
                      <div className="pt-2 border-t border-rule-light">
                        <div className="text-[10px] text-muted mb-1">Identity</div>
                        <div className="font-mono text-[10px] text-muted space-y-0.5">
                          <div>trace: {selectedTrace.id}</div>
                          {selectedTrace.template_hash && <div>template: {selectedTrace.template_hash}</div>}
                          {selectedTrace.data_hash && <div>data: {selectedTrace.data_hash}</div>}
                          {selectedTrace.output_hash ? <div>output: {selectedTrace.output_hash}</div> : <div className="text-muted/40">output hash: not recorded</div>}
                          {selectedTrace.engine_version && <div>engine: trustrender {selectedTrace.engine_version}</div>}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   SECTION 4: COMPLIANCE WEDGE
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
function ComplianceWedge() {
  return (
    <section className="py-20 md:py-28 border-t border-rule">
      <div className="max-w-[1280px] mx-auto px-6 md:px-10">
        <FadeUp>
          <div className="flex flex-col md:flex-row gap-12 md:gap-20">
            <div className="md:w-2/5">
              <p className="text-[11px] tracking-[0.22em] uppercase text-rust mb-4 font-semibold">Compliance</p>
              <h2 className="font-display font-extrabold text-[28px] md:text-[36px] tracking-[-0.03em] leading-[1.08] mb-4">
                Validated e&#8209;invoicing for the supported German B2B path.
              </h2>
              <p className="text-[15px] text-mid leading-relaxed mb-6">
                TrustRender validates invoice data and checks arithmetic consistency before the PDF is created. When the optional facturx library is installed, XSD and Schematron schema validation also run. Structurally invalid data is rejected before a document is produced. Output is PDF/A-3b with embedded CII XML for the supported EN 16931 invoice flow.
              </p>
              <p className="text-[13px] text-mid/70 leading-relaxed">
                Scoped to German domestic B2B invoicing: DE, EUR, mixed VAT rates, standard invoices and credit notes. No Java, no iText, no browser.
              </p>
            </div>
            <div className="md:w-3/5 grid grid-cols-2 gap-4">
              {[
                { l: 'EN 16931 validated', d: 'XSD-checked XML for the supported invoice path' },
                { l: 'ZUGFeRD / Factur-X', d: 'CII XML embedded in PDF/A-3b output' },
                { l: 'German B2B invoice flow', d: 'DE, EUR, mixed VAT rates, invoices and credit notes' },
                { l: 'pip install and go', d: 'Pure Python \u2014 no Java, no iText, no Chromium' },
              ].map(c => (
                <div key={c.l} className="bg-panel rounded-lg border border-rule-light p-5" style={{ boxShadow: '0 1px 4px rgba(20,18,16,0.03)' }}>
                  <div className="text-[14px] font-semibold text-ink">{c.l}</div>
                  <div className="text-[13px] text-mid mt-1.5 leading-relaxed">{c.d}</div>
                </div>
              ))}
            </div>
          </div>
        </FadeUp>

        {/* Scope Matrix */}
        <FadeUp delay={150}>
          <div className="mt-16 bg-panel rounded-xl border border-rule-light overflow-hidden" style={{ boxShadow: '0 2px 8px rgba(20,18,16,0.04)' }}>
            <div className="px-6 py-4 border-b border-rule-light">
              <span className="text-[11px] tracking-[0.15em] uppercase text-muted font-semibold">Supported standards</span>
            </div>
            <div className="divide-y divide-rule-light">
              {[
                { standard: 'ZUGFeRD / Factur-X (EN 16931)', status: 'Supported (narrow scope)', icon: '\u2705', detail: 'DE domestic, EUR, standard VAT only. No reverse charge or cross-border.' },
                { standard: 'Credit notes (type 381)', status: 'Supported', icon: '\u2705', detail: 'Same pipeline, same validation' },
                { standard: 'Mixed VAT rates (7% + 19%)', status: 'Supported', icon: '\u2705', detail: 'Per-item tax rates, multiple tax entries' },
              ].map(r => (
                <div key={r.standard} className="px-6 py-4 flex items-center gap-4">
                  <span className="text-[16px] w-8 text-center">{r.icon}</span>
                  <div className="flex-1">
                    <div className="text-[13px] font-semibold text-ink">{r.standard}</div>
                    <div className="text-[11px] text-muted mt-0.5">{r.detail}</div>
                  </div>
                  <span className={`text-[11px] font-mono font-semibold px-3 py-1 rounded-full ${r.status === 'Production-ready' ? 'bg-sage/10 text-sage' : 'text-muted bg-surface'}`}>
                    {r.status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </FadeUp>
      </div>
    </section>
  )
}

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   SECTION: Performance & Audit Trail
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
function PerformanceProof() {
  return (
    <section className="py-20 md:py-28 bg-ink text-panel">
      <div className="max-w-[1280px] mx-auto px-6 md:px-10">
        <FadeUp>
          <p className="text-[11px] tracking-[0.22em] uppercase text-rust mb-4 font-semibold">Measured, not claimed</p>
          <h2 className="font-display font-extrabold text-[28px] md:text-[40px] tracking-[-0.03em] leading-[1.08] mb-6 max-w-lg">
            1,000 line items. 33 pages. 211ms.
          </h2>
          <p className="text-[15px] text-panel/75 max-w-lg mb-12 leading-relaxed">
            Every number on this page comes from committed benchmarks, not marketing estimates. Soak-tested at 500+ sequential renders with zero errors and zero temp file leaks.
          </p>
        </FadeUp>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-12">
          {/* Performance stats */}
          <FadeUp delay={100}>
            <div className="bg-panel/[0.06] rounded-xl border border-panel/10 p-6">
              <div className="text-[11px] tracking-[0.15em] uppercase text-panel/55 font-semibold mb-5">Render performance</div>
              <div className="space-y-4">
                {[
                  { label: '1,000-row invoice', value: '211ms', detail: '33 pages, 0.21ms/row' },
                  { label: '1,000-row statement', value: '260ms', detail: '29 pages, 0.26ms/row' },
                  { label: 'Simple invoice (warm)', value: '41ms', detail: '1 page, single render' },
                  { label: 'Server throughput', value: '53.8 RPS', detail: '5 concurrent, Apple Silicon' },
                ].map(s => (
                  <div key={s.label} className="flex items-baseline justify-between">
                    <div>
                      <div className="text-[13px] text-panel/90">{s.label}</div>
                      <div className="text-[10px] text-panel/45 font-mono">{s.detail}</div>
                    </div>
                    <div className="text-[18px] font-bold text-rust font-mono">{s.value}</div>
                  </div>
                ))}
              </div>
            </div>
          </FadeUp>

          {/* Ops dashboard preview */}
          <FadeUp delay={200}>
            <div className="bg-panel/[0.06] rounded-xl border border-panel/10 overflow-hidden">
              {/* Dashboard header bar */}
              <div className="px-5 py-3 border-b border-panel/8 flex items-center justify-between">
                <span className="text-[12px] font-semibold text-panel/70">Ops Dashboard</span>
                <div className="flex items-center gap-4 text-[10px] font-mono text-panel/30">
                  <span>6 renders</span>
                  <span className="text-sage">100%</span>
                  <span>84ms avg</span>
                </div>
              </div>
              {/* Trace detail */}
              <div className="p-5">
                <div className="flex items-center gap-2 mb-4">
                  <span className="text-[14px] font-bold text-panel/90">einvoice.j2.typ</span>
                  <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-sage/20 text-sage">OK</span>
                  <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-rust/20 text-rust">EN16931</span>
                </div>
                {/* Pipeline stages */}
                <div className="space-y-2 mb-4">
                  {[
                    { stage: 'zugferd_validation', time: '0ms', meta: 'en16931' },
                    { stage: 'contract_validation', time: '1ms', meta: '' },
                    { stage: 'compilation', time: '54ms', meta: '46KB' },
                    { stage: 'zugferd_postprocess', time: '96ms', meta: '8573B XML' },
                  ].map(s => (
                    <div key={s.stage} className="flex items-center gap-3 px-3 py-2 rounded bg-panel/[0.04] border border-panel/6">
                      <span className="text-sage text-[11px]">{'\u2713'}</span>
                      <span className="text-[11px] font-mono text-panel/60 flex-1">{s.stage}</span>
                      <span className="text-[10px] font-mono text-panel/30">{s.time}{s.meta ? ` \u00b7 ${s.meta}` : ''}</span>
                    </div>
                  ))}
                </div>
                {/* Identity */}
                <div className="border-t border-panel/8 pt-3">
                  <div className="text-[9px] tracking-[0.15em] uppercase text-panel/25 font-semibold mb-2">Identity</div>
                  <div className="space-y-1.5 font-mono text-[10px]">
                    <div className="flex justify-between"><span className="text-panel/30">template</span><span className="text-panel/50">sha256:6958217f022d9d54</span></div>
                    <div className="flex justify-between"><span className="text-panel/30">data</span><span className="text-panel/50">sha256:5184ad6254598a63</span></div>
                    <div className="flex justify-between"><span className="text-panel/30">output</span><span className="text-panel/50">sha256:a23cc650b6d7c7ab</span></div>
                    <div className="flex justify-between"><span className="text-panel/30">engine</span><span className="text-panel/50">trustrender 0.1.2</span></div>
                  </div>
                </div>
              </div>
              <div className="px-5 py-2.5 border-t border-panel/8 text-[10px] text-panel/25">
                Every render is traced. Inspect pipeline stages, hashes, and compliance runs in the ops dashboard.
              </div>
            </div>
          </FadeUp>
        </div>

        <p className="text-[11px] text-panel/45 font-mono mb-8 text-center">
          Benchmarks: macOS, Apple Silicon, Python 3.12, Typst 0.14. Results vary by platform.
        </p>

        {/* Memory + reliability row */}
        <FadeUp delay={300}>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { n: '69.5 MB', d: 'Peak RSS under load' },
              { n: '500+', d: 'Soak renders, zero errors' },
              { n: '854', d: 'Automated tests' },
              { n: '102', d: 'Ugly-data edge cases' },
            ].map(s => (
              <div key={s.d} className="text-center py-4">
                <div className="text-[24px] md:text-[28px] font-bold text-rust font-mono">{s.n}</div>
                <div className="text-[11px] text-panel/40 mt-1">{s.d}</div>
              </div>
            ))}
          </div>
        </FadeUp>
      </div>
    </section>
  )
}

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   SECTION: Developer Setup
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
function DeveloperSetup() {
  return (
    <section className="py-20 md:py-28 border-t border-rule">
      <div className="max-w-[1280px] mx-auto px-6 md:px-10">
        <FadeUp>
          <div className="flex flex-col md:flex-row gap-12 md:gap-20 items-center">
            <div className="md:w-2/5">
              <p className="text-[11px] tracking-[0.22em] uppercase text-rust mb-4 font-semibold">Setup</p>
              <h2 className="font-display font-extrabold text-[28px] md:text-[36px] tracking-[-0.03em] leading-[1.08] mb-4">
                First PDF in 30 seconds.
              </h2>
              <p className="text-[15px] text-mid leading-relaxed mb-4">
                Install, run one command, get a real invoice PDF. No config, no boilerplate, no fighting with dependencies.
              </p>
              <p className="text-[13px] text-mid/70 leading-relaxed">
                <span className="font-mono">quickstart</span> creates a sample template, data file, and rendered PDF in your current directory. Edit the template, change the data, re-render.
              </p>
            </div>
            <div className="md:w-3/5">
              <div className="bg-ink rounded-xl border border-panel/10 overflow-hidden" style={{ boxShadow: '0 4px 20px rgba(20,18,16,0.2)' }}>
                <div className="px-4 py-2.5 border-b border-panel/10 flex items-center gap-2">
                  <div className="flex gap-1.5">
                    <div className="w-2 h-2 rounded-full bg-panel/15" />
                    <div className="w-2 h-2 rounded-full bg-panel/15" />
                    <div className="w-2 h-2 rounded-full bg-panel/15" />
                  </div>
                  <span className="text-[10px] font-mono text-panel/30 ml-2">terminal</span>
                </div>
                <div className="p-5 font-mono text-[11px] leading-[1.9]">
                  <div className="text-panel/50">$ pip install trustrender</div>
                  <div className="text-panel/50">$ trustrender quickstart</div>
                  <div className="text-panel/30 mt-3">Created:</div>
                  <div className="text-panel/70">    trustrender-quickstart/invoice.j2.typ</div>
                  <div className="text-panel/70">    trustrender-quickstart/invoice_data.json</div>
                  <div className="text-panel/70">    trustrender-quickstart/invoice.pdf</div>
                  <div className="mt-3 text-sage font-semibold">Your first PDF: invoice.pdf (34 KB)</div>
                  <div className="text-panel/30 mt-3">Next:</div>
                  <div className="text-panel/70">    open trustrender-quickstart/invoice.pdf</div>
                  <div className="text-panel/70">    trustrender render invoice.j2.typ invoice_data.json -o invoice.pdf</div>
                </div>
              </div>
            </div>
          </div>
        </FadeUp>
      </div>
    </section>
  )
}

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   SECTION 5: CTA
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
function FinalCTA() {
  return (
    <section className="pt-20 md:pt-28 pb-12 md:pb-16 bg-ink text-panel">
      <div className="max-w-[1280px] mx-auto px-6 md:px-10">
        <FadeUp>
          <div className="text-center">
          <h2 className="font-display font-extrabold text-[32px] md:text-[48px] tracking-[-0.03em] leading-[1.05] mb-4 max-w-lg mx-auto">
            Stop shipping documents you cannot trust.
          </h2>
          <p className="text-[15px] text-panel/55 max-w-md mx-auto mb-8">
            Readiness. Compliance. Provenance. Validated by default for Jinja2 templates.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 items-center justify-center">
            <a href="https://github.com/verityengine/trustrender" className="px-7 py-3.5 bg-rust hover:bg-rust-light text-white text-[14px] font-semibold rounded transition-colors inline-block">
              View on GitHub
            </a>
            <a href="#app" className="px-7 py-3.5 bg-panel text-ink text-[14px] font-semibold rounded transition-colors hover:bg-panel/90 inline-block">
              Try the playground
            </a>
          </div>
          <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-lg mx-auto">
            {[
              { label: 'Lean core', cmd: 'pip install trustrender && trustrender quickstart', accent: false },
              { label: 'With e-invoicing', cmd: 'pip install "trustrender[zugferd]" && trustrender quickstart', accent: true },
            ].map(({ label, cmd, accent }) => (
              <button key={label} onClick={() => { navigator.clipboard.writeText(cmd) }}
                className={`px-5 py-4 rounded-lg text-left cursor-pointer transition-colors group ${accent ? 'border border-rust/40 bg-rust/[0.12] hover:bg-rust/[0.18]' : 'border border-panel/25 bg-panel/[0.08] hover:bg-panel/[0.12]'}`}>
                <div className="flex items-center justify-between mb-2">
                  <span className={`text-[10px] tracking-[0.15em] uppercase font-semibold ${accent ? 'text-rust/70' : 'text-panel/50'}`}>{label}</span>
                  <span className="text-[9px] text-panel/30 group-hover:text-panel/60 transition-colors">copy</span>
                </div>
                <code className="font-mono text-[13px] text-panel/90">{cmd}</code>
              </button>
            ))}
          </div>
          </div>
        </FadeUp>
      </div>
    </section>
  )
}

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
function useHash() {
  const [hash, setHash] = useState(window.location.hash)
  useEffect(() => {
    const onHash = () => setHash(window.location.hash)
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  return hash
}

export default function App() {
  const hash = useHash()
  const isApp = hash === '#app' || hash.startsWith('#app/')

  if (isApp) return <AppWorkspace />

  return (
    <div>
      <nav className="sticky top-0 z-50 bg-ink/90 backdrop-blur-md border-b border-panel/10">
        <div className="max-w-[1280px] mx-auto px-6 md:px-10 py-4 flex items-center justify-between">
          <a href="/" className="text-panel"><AnimatedLogo animate /></a>
          <div className="flex items-center gap-4">
            <a href="#app" className="text-[14px] font-semibold px-5 py-2.5 rounded-lg bg-rust hover:bg-rust-light text-white transition-colors hidden md:inline-block">Try the playground</a>
            <a href="https://github.com/verityengine/trustrender" className="text-[14px] font-medium px-5 py-2.5 rounded-lg bg-panel hover:bg-panel/90 text-ink transition-colors">GitHub</a>
          </div>
        </div>
      </nav>
      <HeroReveal />
      <TrustLayers />
      <ReadyDemo />
      <ComplianceWedge />
      <PerformanceProof />
      <DeveloperSetup />
      <FinalCTA />
      <footer className="py-5 bg-ink border-t border-panel/10">
        <div className="max-w-[1280px] mx-auto px-6 md:px-10 flex items-center justify-between">
          <div className="text-panel/50"><AnimatedLogo size="small" /></div>
          <p className="text-panel/40 text-[10px] font-mono">trustrender v0.1</p>
        </div>
      </footer>
    </div>
  )
}

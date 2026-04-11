import { useState, useEffect, useRef } from 'react'
import * as pdfjsLib from 'pdfjs-dist'
import pdfjsWorker from 'pdfjs-dist/build/pdf.worker.mjs?url'

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfjsWorker

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   FORMFORGE — Product site
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
  const outerRef = useRef(null)
  const innerRef = useRef(null)

  useEffect(() => {
    if (!animate) return
    // Draw-on animation for the outer hexagonal frame
    ;[outerRef, innerRef].forEach((ref, i) => {
      const el = ref.current
      if (!el) return
      const len = el.getTotalLength()
      el.style.strokeDasharray = len
      el.style.strokeDashoffset = len
      el.getBoundingClientRect()
      el.style.transition = `stroke-dashoffset ${0.8 + i * 0.4}s ease-out ${0.1 + i * 0.3}s`
      el.style.strokeDashoffset = '0'
    })
  }, [animate])

  const s = size === 'small' ? 'h-7' : 'h-9'
  return (
    <div className="flex items-center gap-3">
      <svg className={`${s} aspect-square`} viewBox="0 0 40 40" fill="none">
        {/* Outer circle — seal */}
        <circle ref={outerRef} cx="20" cy="20" r="18" stroke="currentColor" strokeWidth="1.8" opacity="0.6" />
        {/* Inner structured block */}
        <rect x="12" y="11" width="16" height="18" rx="2" stroke="currentColor" strokeWidth="1.2" opacity="0.3" />
        {/* Data lines */}
        <line x1="15" y1="16" x2="25" y2="16" stroke="currentColor" strokeWidth="1.5" opacity="0.5" strokeLinecap="round">
          {animate && <animate attributeName="x2" from="15" to="25" dur="0.4s" fill="freeze" begin="0.5s" />}
        </line>
        <line x1="15" y1="20" x2="22" y2="20" stroke="currentColor" strokeWidth="1.2" opacity="0.3" strokeLinecap="round">
          {animate && <animate attributeName="x2" from="15" to="22" dur="0.3s" fill="freeze" begin="0.7s" />}
        </line>
        <line x1="15" y1="24" x2="23" y2="24" stroke="currentColor" strokeWidth="1.2" opacity="0.3" strokeLinecap="round">
          {animate && <animate attributeName="x2" from="15" to="23" dur="0.3s" fill="freeze" begin="0.85s" />}
        </line>
        {/* Validation strike — brand accent */}
        <path ref={innerRef} d="M21 26l2.5 2.5L30 22" stroke="#c4622a" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" opacity="0.9" />
      </svg>
      <span className={`font-display tracking-[-0.02em] ${size === 'small' ? 'text-[18px]' : 'text-[24px]'}`}>Formforge</span>
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
    const W = 560, H = 360
    canvas.width = W; canvas.height = H
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
  const canvasRef = useRef(null)
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const W = 560, H = 340
    canvas.width = W; canvas.height = H
    let raf, t = 0

    // Asymmetric, organic layout — not a perfect centered tree
    const nodes = [
      { x: 240, y: 40, label: 'Invoice', r: 30, weight: 700 },
      { x: 100, y: 130, label: 'Seller', r: 24, weight: 500 },
      { x: 260, y: 140, label: 'Buyer', r: 22, weight: 500 },
      { x: 430, y: 125, label: 'Lines', r: 26, weight: 500 },
      { x: 45, y: 230, label: 'VAT', r: 17, weight: 400 },
      { x: 155, y: 240, label: 'Addr', r: 16, weight: 400 },
      { x: 260, y: 245, label: 'Name', r: 16, weight: 400 },
      { x: 380, y: 235, label: 'Item 1', r: 17, weight: 400 },
      { x: 490, y: 225, label: 'Item 2', r: 17, weight: 400 },
    ]
    const edges = [[0,1],[0,2],[0,3],[1,4],[1,5],[2,6],[3,7],[3,8]]

    // Bezier control points for organic curves
    function bezierPoint(a, b, t, cx, cy) {
      const u = 1 - t
      return { x: u*u*a.x + 2*u*t*cx + t*t*b.x, y: u*u*a.y + 2*u*t*cy + t*t*b.y }
    }

    function draw() {
      t += 0.007
      ctx.clearRect(0, 0, W, H)

      // Draw edges as bezier curves with flowing particles
      edges.forEach(([a, b], i) => {
        const na = nodes[a], nb = nodes[b]
        const pulse = Math.sin(t * 2.5 + i * 0.9) * 0.15 + 0.55
        // Control point — offset sideways for organic feel
        const cx = (na.x + nb.x) / 2 + Math.sin(i * 1.7) * 25
        const cy = (na.y + nb.y) / 2

        // Draw bezier
        ctx.beginPath()
        ctx.moveTo(na.x, na.y + na.r * 0.6)
        ctx.quadraticCurveTo(cx, cy, nb.x, nb.y - nb.r * 0.6)
        ctx.strokeStyle = `rgba(28,27,25,${pulse * 0.18})`
        ctx.lineWidth = 1.2
        ctx.stroke()

        // Multiple flowing particles per edge
        for (let p = 0; p < 2; p++) {
          const pt = ((t * (1.2 + i * 0.15) + p * 0.5 + i * 0.2) % 1)
          const pos = bezierPoint(
            { x: na.x, y: na.y + na.r * 0.6 },
            { x: nb.x, y: nb.y - nb.r * 0.6 },
            pt, cx, cy
          )
          const alpha = 0.7 * (1 - Math.abs(pt - 0.5) * 2)
          // Glow trail
          ctx.beginPath()
          ctx.arc(pos.x, pos.y, 8, 0, Math.PI * 2)
          ctx.fillStyle = `rgba(45,110,86,${0.06 * alpha})`
          ctx.fill()
          // Particle
          ctx.beginPath()
          ctx.arc(pos.x, pos.y, 2.5, 0, Math.PI * 2)
          ctx.fillStyle = `rgba(45,110,86,${alpha})`
          ctx.fill()
        }
      })

      // Draw nodes — varying styles by depth
      nodes.forEach((n, i) => {
        const pulse = Math.sin(t * 1.8 + i * 0.7) * 0.1 + 0.9
        const isRoot = i === 0
        const isLeaf = i >= 4

        // Outer breathing glow
        const glowR = n.r + 6 + Math.sin(t * 2 + i) * 3
        ctx.beginPath()
        ctx.arc(n.x, n.y, glowR, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(45,110,86,${(isRoot ? 0.04 : 0.02) * pulse})`
        ctx.fill()

        // Node circle
        ctx.beginPath()
        ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2)
        ctx.fillStyle = isRoot ? `rgba(28,27,25,${0.05 * pulse})` : `rgba(28,27,25,${0.025 * pulse})`
        ctx.strokeStyle = `rgba(28,27,25,${(isRoot ? 0.3 : isLeaf ? 0.12 : 0.18) * pulse})`
        ctx.lineWidth = isRoot ? 1.8 : 1
        ctx.fill(); ctx.stroke()

        // Label
        ctx.font = `${n.weight} ${isRoot ? 13 : isLeaf ? 9.5 : 11}px "JetBrains Mono", monospace`
        ctx.fillStyle = `rgba(28,27,25,${(isRoot ? 0.8 : isLeaf ? 0.45 : 0.6) * pulse})`
        ctx.textAlign = 'center'
        ctx.fillText(n.label, n.x, n.y + (isRoot ? 5 : 4))
      })

      // EN 16931 badge — bottom center, with glow
      const badgeY = 295
      const bp = Math.sin(t * 1.2) * 0.08 + 0.92
      // Glow behind badge
      const bgrd = ctx.createRadialGradient(240, badgeY, 0, 240, badgeY, 60)
      bgrd.addColorStop(0, `rgba(45,110,86,${0.06 * bp})`)
      bgrd.addColorStop(1, 'rgba(45,110,86,0)')
      ctx.fillStyle = bgrd
      ctx.fillRect(180, badgeY - 20, 120, 40)
      // Badge pill
      ctx.beginPath()
      ctx.roundRect(200, badgeY - 12, 80, 24, 12)
      ctx.fillStyle = `rgba(45,110,86,${0.1 * bp})`
      ctx.strokeStyle = `rgba(45,110,86,${0.3 * bp})`
      ctx.lineWidth = 1
      ctx.fill(); ctx.stroke()
      ctx.font = '600 10px "JetBrains Mono", monospace'
      ctx.fillStyle = `rgba(45,110,86,${0.75 * bp})`
      ctx.textAlign = 'center'
      ctx.fillText('EN 16931', 240, badgeY + 4)

      raf = requestAnimationFrame(draw)
    }
    raf = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(raf)
  }, [])
  return <canvas ref={canvasRef} className="w-full" style={{ aspectRatio: '560/340' }} />
}

/* ── Trust Layer Flourish: Provenance (canvas-rendered) ───────────── */
function ProvenanceFlourish() {
  const canvasRef = useRef(null)
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const W = 560, H = 340
    canvas.width = W; canvas.height = H
    let raf, t = 0

    const stages = [
      { x: 70, y: 170, label: 'input', hash: 'a7f3e2' },
      { x: 210, y: 170, label: 'template', hash: 'c2e1b8' },
      { x: 350, y: 170, label: 'render', hash: 'd4f091' },
      { x: 490, y: 170, label: 'output', hash: '9b4d7a' },
    ]

    function draw() {
      t += 0.006
      ctx.clearRect(0, 0, W, H)

      const cycleT = (t * 0.8) % 2.5
      const activeCount = Math.min(Math.floor(cycleT / 0.5), 4)

      // Draw connections
      for (let i = 0; i < stages.length - 1; i++) {
        const s = stages[i], next = stages[i + 1]
        const active = i < activeCount

        // Base line
        ctx.beginPath()
        ctx.moveTo(s.x + 40, s.y)
        ctx.lineTo(next.x - 40, next.y)
        ctx.strokeStyle = active ? `rgba(196,98,42,0.7)` : 'rgba(28,27,25,0.15)'
        ctx.lineWidth = active ? 2.5 : 1.5
        ctx.setLineDash(active ? [] : [5, 5])
        ctx.stroke()
        ctx.setLineDash([])

        // Flowing particles along active connections
        if (active) {
          for (let p = 0; p < 3; p++) {
            const pt = ((t * 3 + p * 0.33 + i * 0.2) % 1)
            const px = (s.x + 40) + (next.x - 40 - s.x - 40) * pt
            ctx.beginPath()
            ctx.arc(px, s.y, 3.5, 0, Math.PI * 2)
            ctx.fillStyle = `rgba(196,98,42,${0.9 * (1 - Math.abs(pt - 0.5) * 2)})`
            ctx.fill()
            // Glow
            ctx.beginPath()
            ctx.arc(px, s.y, 10, 0, Math.PI * 2)
            ctx.fillStyle = `rgba(196,98,42,${0.15 * (1 - Math.abs(pt - 0.5) * 2)})`
            ctx.fill()
          }
        }
      }

      // Draw stage nodes
      stages.forEach((s, i) => {
        const active = i < activeCount
        const current = i === activeCount - 1 && activeCount > 0
        const size = 36
        const pulse = current ? Math.sin(t * 8) * 0.1 + 0.9 : 1

        // Glow for active
        if (active) {
          ctx.beginPath()
          ctx.roundRect(s.x - size - 8, s.y - size/1.2 - 8, (size + 8) * 2, size * 1.9, 10)
          ctx.fillStyle = `rgba(196,98,42,${0.1 * pulse})`
          ctx.fill()
        }

        // Box
        ctx.beginPath()
        ctx.roundRect(s.x - size, s.y - size/1.2, size * 2, size * 1.6, 6)
        ctx.fillStyle = active ? `rgba(196,98,42,0.12)` : 'rgba(28,27,25,0.04)'
        ctx.strokeStyle = active ? `rgba(196,98,42,${0.6 * pulse})` : 'rgba(28,27,25,0.18)'
        ctx.lineWidth = active ? 2 : 1.2
        ctx.fill(); ctx.stroke()

        // Label
        ctx.font = `${active ? '700' : '500'} 12px "JetBrains Mono", monospace`
        ctx.fillStyle = `rgba(28,27,25,${active ? 0.9 : 0.4})`
        ctx.textAlign = 'center'
        ctx.fillText(s.label, s.x, s.y - 4)

        // Hash
        ctx.font = '500 10px "JetBrains Mono", monospace'
        ctx.fillStyle = active ? `rgba(196,98,42,${0.8 * pulse})` : 'rgba(28,27,25,0.2)'
        ctx.fillText(s.hash, s.x, s.y + 14)
      })

      // Chain label
      ctx.font = '400 9px "JetBrains Mono", monospace'
      ctx.fillStyle = 'rgba(28,27,25,0.15)'
      ctx.textAlign = 'center'
      ctx.fillText('input → template → render → output', W/2, H - 20)

      raf = requestAnimationFrame(draw)
    }
    raf = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(raf)
  }, [])
  return <canvas ref={canvasRef} className="w-full" style={{ aspectRatio: '560/340' }} />
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
        Formforge
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
        <span>Generated by Formforge</span>
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
    <section className="bg-ink text-panel relative overflow-hidden">
      {/* Animated particle background */}
      <DocumentField />
      {/* Nav */}
      <nav className="max-w-[1280px] mx-auto px-6 md:px-10 py-5 flex items-center justify-between relative z-10">
        <div className="text-panel"><AnimatedLogo animate /></div>
        <div className="flex items-center gap-5">
          <a href="#app" className="text-[13px] text-panel/60 hover:text-panel transition-colors hidden md:block">Playground</a>
          <a href="https://github.com/verityengine/formforge" className="text-[13px] px-4 py-2 rounded bg-panel/10 hover:bg-panel/15 text-panel transition-colors">GitHub</a>
        </div>
      </nav>

      {/* Hero content */}
      <div className="max-w-[1280px] mx-auto px-6 md:px-10 pt-16 md:pt-24 pb-12 md:pb-16 relative z-10">
        <div className="text-center max-w-4xl mx-auto mb-8 hero-stagger">
          <h1 className="font-display text-[44px] md:text-[72px] lg:text-[88px] leading-[0.98] tracking-tight gradient-text pb-2">
            Bad payloads never become broken documents.
          </h1>
          <p className="text-[16px] md:text-[18px] text-panel/45 max-w-xl mx-auto mt-6 leading-relaxed">
            Validate document data before render. Catch missing fields, broken paths, and structural errors before a bad invoice reaches a customer.
          </p>
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
                ${mode === 'valid' ? 'bg-rust text-white border-rust' : 'text-panel/50 border-panel/20 hover:border-panel/40 bg-transparent'}`}>
              See it pass
            </button>
            <button onClick={() => toggle('invalid')}
              className={`text-[13px] px-6 py-2.5 rounded-full border-2 transition-all font-medium cursor-pointer
                ${mode === 'invalid' ? 'bg-wine text-white border-wine' : 'text-panel/50 border-panel/20 hover:border-panel/40 bg-transparent'}`}>
              See what gets caught
            </button>
            <span className="ml-3 text-[11px] text-panel/50 font-mono hidden md:inline">
              {mode === null ? 'choose a payload' : mode === 'valid' ? 'invoice_data.json' : 'bad_data.json'}{mode !== null ? ' \u2192 invoice.j2.typ' : ''}
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
      stats: ['729 automated tests', '500 soak renders, 0 errors', '56ms avg latency'],
      flourish: <ReadinessFlourish />,
    },
    {
      title: 'Compliance',
      desc: 'Pre-render validated invoice path for German domestic invoicing. EN 16931, ZUGFeRD / Factur-X. No Java, no iText, no browser stack.',
      stats: ['EN 16931 profile', 'Factur-X PDF/A-3b', 'DE / EUR / mixed rates'],
      flourish: <ComplianceFlourish />,
      caption: 'Simplified invoice structure \u2014 not a complete EN 16931 field map',
    },
    {
      title: 'Provenance',
      desc: 'Verifiable lineage from inputs to output. Know what data went in, what template was used, and what artifact was produced.',
      stats: ['Input hash tracking', 'Template versioning', 'Output fingerprint'],
      flourish: <ProvenanceFlourish />,
    },
  ]

  return (
    <section className="py-20 md:py-28">
      <div className="max-w-[1280px] mx-auto px-6 md:px-10">
        <FadeUp>
          <p className="text-[11px] tracking-[0.22em] uppercase text-rust mb-4 font-semibold">Trust layers</p>
          <h2 className="font-display text-[28px] md:text-[40px] tracking-tight leading-[1.1] mb-16 max-w-lg">
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
      sender: { name: "Acme Corp", address_line1: "123 Business Ave", address_line2: "SF, CA 94105", email: "billing@acme.com" },
      recipient: { name: "Contoso Ltd", address_line1: "456 Enterprise Blvd", address_line2: "NY, NY 10001", email: "ap@contoso.com" },
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
      sender: { name: "Acme Corp", address_line1: "123 Business Ave", address_line2: "SF, CA 94105" },
      recipient: { address_line1: "456 Enterprise Blvd", address_line2: "NY, NY 10001", email: "ap@contoso.com" },
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
      company: { name: "Acme Corp", address_line1: "123 Business Ave", address_line2: "SF, CA 94105", email: "accounts@acme.com", phone: "(415) 555-0100" },
      customer: { name: "Contoso Ltd", account_number: "ACCT-78432", address_line1: "456 Enterprise Blvd", address_line2: "NY, NY 10001", email: "ap@contoso.com" },
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
      company: { name: "Acme Corp", address_line1: "123 Business Ave", address_line2: "SF, CA 94105", email: "accounts@acme.com", phone: "(415) 555-0100" },
      customer: { name: "Contoso Ltd", address_line1: "456 Enterprise Blvd", address_line2: "NY, NY 10001", email: "ap@contoso.com" },
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
      company: { name: "Daily Grind Coffee", address_line1: "782 Market St", address_line2: "SF, CA 94102", phone: "(415) 555-0187", website: "dailygrind.com" },
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
      company: { name: "Daily Grind Coffee", address_line1: "782 Market St", address_line2: "SF, CA 94102", phone: "(415) 555-0187" },
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
      sender: { name: "Acme Corp", title: "Accounts Receivable", address_line1: "123 Business Ave", address_line2: "SF, CA 94105", phone: "(415) 555-0100", email: "ar@acme.com" },
      recipient: { name: "Margaret Chen", title: "CFO", company: "Contoso Ltd", address_line1: "456 Enterprise Blvd", address_line2: "NY, NY 10001" },
      date: "April 10, 2026", subject: "Outstanding Balance", salutation: "Dear Ms. Chen,",
      body_paragraphs: ["Your account has an outstanding balance of $18,267.50.", "Please settle at your earliest convenience."],
      closing: "Sincerely,", signature_name: "James Rodriguez", signature_title: "Director of Finance", signature_company: "Acme Corp",
    },
    invalid: {
      sender: { name: "Acme Corp", title: "Accounts Receivable", address_line1: "123 Business Ave", address_line2: "SF, CA 94105", phone: "(415) 555-0100" },
      recipient: { name: "Margaret Chen", title: "CFO", company: "Contoso Ltd", address_line1: "456 Enterprise Blvd", address_line2: "NY, NY 10001" },
      date: "April 10, 2026", subject: "Outstanding Balance", salutation: "Dear Ms. Chen,",
      body_paragraphs: "Your account has an outstanding balance.",
      closing: "Sincerely,", signature_name: "James Rodriguez", signature_title: "Director of Finance",
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
      const res = await fetch('/api/preflight', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ template, data }),
      })
      setVerdict(await res.json()); setChecking(false)
    } catch {
      setVerdict({ ready: false, errors: [{ stage: 'network', check: 'unreachable', severity: 'error', path: 'server', message: 'Server unreachable. Is formforge serve running on port 8190?' }], warnings: [], stages_checked: [] })
      setChecking(false)
    }
  }

  return (
    <section id="playground" className="py-20 md:py-28 bg-surface border-t border-rule">
      <div className="max-w-[1280px] mx-auto px-6 md:px-10">
        <FadeUp>
          <p className="text-[11px] tracking-[0.22em] uppercase text-rust mb-4 font-semibold">Try it</p>
          <h2 className="font-display text-[28px] md:text-[40px] tracking-tight leading-[1.1] mb-3">
            Check readiness before render.
          </h2>
          <p className="text-[14px] text-mid max-w-md leading-relaxed mb-10">
            Toggle to an invalid payload and see what Formforge catches before the renderer is ever invoked.
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
                <a href="#app" className="text-[12px] text-rust hover:text-wine font-medium">
                  Full experience: Ready &middot; Generate &middot; History &rarr;
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
  const [template, setTemplate] = useState('invoice.j2.typ')
  const [payloadMode, setPayloadMode] = useState('valid')
  const [json, setJson] = useState(() => JSON.stringify(FIXTURES['invoice.j2.typ'].valid, null, 2))
  const [parseError, setParseError] = useState(null)

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

  // History state
  const [traces, setTraces] = useState(null) // null=not loaded, []=empty, [...]=data
  const [historyError, setHistoryError] = useState(null) // 'disabled' or 'error'
  const [selectedTrace, setSelectedTrace] = useState(null)

  const fetchTraces = async ({ autoSelect = false } = {}) => {
    try {
      const res = await fetch('/api/history?limit=50')
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
    setJson(JSON.stringify(FIXTURES[tpl][mode === 'valid' ? 'valid' : 'invalid'], null, 2))
    setVerdict(null); setRenderStatus('idle'); setPdfData(null); setRenderError(null)
  }

  // JSON parse check
  useEffect(() => {
    try { JSON.parse(json); setParseError(null) }
    catch (e) { setParseError(e.message.split(' at ')[0]) }
  }, [json])

  // Auto-preflight on valid JSON change (debounced 500ms)
  // Request sequencing: only apply the latest response, ignore stale ones
  const jsonRef = useRef(json)
  const templateRef = useRef(template)
  const preflightSeq = useRef(0)
  jsonRef.current = json
  templateRef.current = template

  useEffect(() => {
    if (parseError) return
    if (preflightTimer.current) clearTimeout(preflightTimer.current)
    preflightTimer.current = setTimeout(() => { runPreflight() }, 500)
    return () => clearTimeout(preflightTimer.current)
  }, [json, template])

  const runPreflight = async () => {
    let data
    try { data = JSON.parse(jsonRef.current) } catch { return }
    const tpl = templateRef.current
    const seq = ++preflightSeq.current
    setChecking(true)
    try {
      const res = await fetch('/api/preflight', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ template: tpl, data }),
      })
      if (seq !== preflightSeq.current) return // stale response, discard
      setVerdict(await res.json())
    } catch {
      if (seq !== preflightSeq.current) return
      setVerdict({ ready: false, errors: [{ stage: 'network', check: 'unreachable', severity: 'error', path: 'server', message: 'Server unreachable' }], warnings: [], stages_checked: [] })
    }
    if (seq === preflightSeq.current) setChecking(false)
  }

  const renderPdf = async () => {
    if (parseError) return
    setRenderStatus('rendering'); setRenderError(null); setCurrentPage(1); setTraceId(null)
    if (pdfData?.downloadUrl) URL.revokeObjectURL(pdfData.downloadUrl)
    setPdfData(null)
    try {
      const data = JSON.parse(json)
      const res = await fetch('/api/render', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ template, data, validate: true, debug: true }),
      })
      if (res.headers.get('X-Trace-ID')) setTraceId(res.headers.get('X-Trace-ID'))
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
      } else {
        setRenderError(await res.json()); setRenderStatus('error')
      }
    } catch (e) {
      const isNet = e instanceof TypeError && e.message.includes('fetch')
      setRenderError({ error: isNet ? 'NETWORK' : 'RENDER_ERROR', message: isNet ? 'Server unreachable' : e.message })
      setRenderStatus('error')
    }
  }

  const STAGES = ['payload', 'template', 'environment', 'compliance', 'semantic']
  const STAGE_SKIP_INFO = {
    compliance: { label: 'not requested', reason: 'No compliance profile selected' },
    semantic: { label: 'not configured', reason: 'Semantic checks are not configured for this template' },
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
    if (status === 'skipped') return <svg className="w-3.5 h-3.5 text-rule" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" d="M5 12h14" /></svg>
    return <div className="w-3 h-3 rounded-full border border-rule-light" />
  }

  return (
    <div className="min-h-screen bg-bg">
      {/* Header */}
      <header className="border-b border-rule-light bg-panel">
        <div className="max-w-[1280px] mx-auto px-6 md:px-10 flex items-center justify-between h-14">
          <a href="#" className="flex items-center gap-2.5">
            <AnimatedLogo size="small" />
            <span className="text-[13px] font-semibold text-ink tracking-tight">Formforge</span>
          </a>
          <div className="flex items-center gap-1 bg-surface rounded-lg p-1 border border-rule-light">
            {[['ready', 'Ready'], ['generate', 'Generate'], ['history', 'History']].map(([key, label]) => (
              <button key={key} onClick={() => setTab(key)}
                className={`text-[12px] px-4 py-1.5 rounded-md font-medium transition-colors cursor-pointer
                  ${tab === key ? 'bg-panel text-ink shadow-sm' : 'text-muted hover:text-mid'}`}>
                {label}
                {key === 'ready' && verdict && !checking && (
                  <span className={`ml-1.5 inline-block w-1.5 h-1.5 rounded-full ${verdict.ready ? 'bg-sage' : 'bg-wine'}`} />
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
              className="w-full p-4 font-mono text-[11px] leading-[1.8] text-ink-2 bg-panel resize-none focus:outline-none min-h-[520px] whitespace-pre overflow-x-auto"
              style={{ tabSize: 2 }} />
            {parseError && <div className="px-4 py-2 border-t border-wine/20 bg-wine/[0.04] text-[11px] text-wine font-mono">JSON: {parseError}</div>}
            {payloadMode === 'invalid' && !parseError && (
              <div className="px-4 py-2 border-t border-rule-light text-[10px] text-muted">Try the broken payload to see what Ready catches.</div>
            )}
          </div>

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
                {verdict && !checking && (
                  <div className={`flex items-center gap-3 px-4 py-3 rounded-lg border ${verdict.ready ? 'bg-sage/[0.06] border-sage/20' : 'bg-wine/[0.04] border-wine/20'}`}>
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${verdict.ready ? 'bg-sage/15' : 'bg-wine/10'}`}>
                      {verdict.ready
                        ? <svg className="w-4 h-4 text-sage" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5"><path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" /></svg>
                        : <svg className="w-4 h-4 text-wine" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5"><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
                      }
                    </div>
                    <div className="flex-1">
                      <div className={`text-[14px] font-semibold ${verdict.ready ? 'text-sage' : 'text-wine'}`}>
                        {verdict.ready ? 'Ready to render' : `${verdict.errors?.length || 0} issue${(verdict.errors?.length || 0) !== 1 ? 's' : ''} must be fixed before this request is ready`}
                      </div>
                      <div className="text-[11px] text-muted">
                        {verdict.stages_checked?.length || 0} stages checked
                        {verdict.warnings?.length > 0 && ` \u00b7 ${verdict.warnings.length} warning${verdict.warnings.length !== 1 ? 's' : ''}`}
                      </div>
                    </div>
                    {verdict.ready ? (
                      <button onClick={() => { setTab('generate'); setTimeout(renderPdf, 100) }}
                        className="text-[11px] px-4 py-1.5 rounded-full font-medium bg-ink text-panel hover:bg-ink-2 transition-colors cursor-pointer flex-shrink-0">
                        Render PDF
                      </button>
                    ) : (
                      <div className="text-[10px] text-muted font-mono flex-shrink-0">{verdict.checked_at?.split('T')[1]?.split('.')[0] || ''}</div>
                    )}
                  </div>
                )}
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
                          <div key={stage} className="px-4 py-3">
                            <div className="flex items-center gap-3">
                              <StageIcon status={s} />
                              <div className="flex-1 min-w-0">
                                <span className="text-[12px] font-medium text-ink capitalize">{stage}</span>
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
                                {issues.map((issue, i) => (
                                  <div key={i} className={`border-l-[3px] pl-3 py-1.5 rounded-r-sm ${issue.severity === 'error' ? 'border-wine/30 bg-wine/[0.03]' : 'border-rust/30 bg-rust/[0.03]'}`}>
                                    <div className="font-mono text-[11px] font-semibold text-ink">{issue.path}</div>
                                    <div className="text-[10px] text-mid">{issue.message}</div>
                                  </div>
                                ))}
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
                    <span className="text-[10px] font-mono text-muted">{renderStatus === 'done' ? 'output.pdf' : renderStatus === 'rendering' ? 'rendering\u2026' : renderStatus === 'error' ? 'error' : 'output'}</span>
                    <div className="flex items-center gap-3">
                      {renderStatus === 'done' && pdfData && pdfData.totalPages > 1 && (
                        <div className="flex items-center gap-1.5">
                          <button onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={currentPage <= 1} className="text-[10px] text-muted hover:text-ink disabled:opacity-30 cursor-pointer disabled:cursor-default px-1">&larr;</button>
                          <span className="text-[10px] text-muted font-mono tabular-nums">{currentPage}/{pdfData.totalPages}</span>
                          <button onClick={() => setCurrentPage(p => Math.min(pdfData.totalPages, p + 1))} disabled={currentPage >= pdfData.totalPages} className="text-[10px] text-muted hover:text-ink disabled:opacity-30 cursor-pointer disabled:cursor-default px-1">&rarr;</button>
                        </div>
                      )}
                      {traceId && <span className="text-[10px] font-mono text-muted">trace: {traceId.slice(0, 8)}</span>}
                      {renderStatus === 'done' && <span className="text-[10px] text-sage font-medium">rendered</span>}
                      {renderStatus === 'error' && <span className="text-[10px] text-wine font-mono font-medium">{renderError?.error}</span>}
                      {pdfData?.downloadUrl && <a href={pdfData.downloadUrl} download="formforge-demo.pdf" className="text-[11px] text-rust hover:text-wine font-medium">Download</a>}
                    </div>
                  </div>
                  <div className="flex-1 flex items-center justify-center p-4">
                    {renderStatus === 'idle' && (
                      <div className="text-center py-16">
                        <div className="w-12 h-12 mx-auto mb-4 rounded-full border-2 border-rule flex items-center justify-center">
                          <svg className="w-5 h-5 text-rule" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5"><path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" /></svg>
                        </div>
                        <p className="text-[13px] text-muted">Run a readiness check, then render from the Ready tab</p>
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
                        Start the server with <code className="font-mono text-[11px] bg-surface px-1 py-0.5 rounded">--history ~/.formforge/history.db</code> to enable render trace storage.
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
                      <button onClick={fetchTraces} className="text-[10px] text-muted hover:text-ink cursor-pointer">refresh</button>
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
                          {selectedTrace.engine_version && <div>engine: formforge {selectedTrace.engine_version}</div>}
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
              <h2 className="font-display text-[28px] md:text-[36px] tracking-tight leading-[1.1] mb-4">
                Validated e&#8209;invoicing for German B2B
              </h2>
              <p className="text-[14px] text-mid leading-relaxed">
                Invoice data validated before render. Wrong data is rejected before a document is produced. Output is a PDF/A-3b with embedded CII XML for automated processing. No Java, no iText, no browser. Scoped to German domestic B2B invoicing: DE, EUR, mixed VAT rates, type 380.
              </p>
            </div>
            <div className="md:w-3/5 grid grid-cols-2 gap-4">
              {[
                { l: 'EN 16931 profile', d: 'Schema-tested CII XML' },
                { l: 'ZUGFeRD / Factur-X', d: 'CII XML embedded in PDF/A-3b' },
                { l: 'Scope', d: 'DE domestic, EUR, mixed VAT rates' },
                { l: 'Pure Python pipeline', d: 'No Java, no iText, no Chromium' },
              ].map(c => (
                <div key={c.l} className="bg-panel rounded-lg border border-rule-light p-5" style={{ boxShadow: '0 1px 4px rgba(20,18,16,0.03)' }}>
                  <div className="text-[14px] font-semibold text-ink">{c.l}</div>
                  <div className="text-[12px] text-muted mt-1.5 leading-relaxed">{c.d}</div>
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
   SECTION 5: CTA
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
function FinalCTA() {
  return (
    <section className="py-20 md:py-28 bg-ink text-panel">
      <div className="max-w-[1280px] mx-auto px-6 md:px-10">
        <FadeUp>
          <h2 className="font-display text-[32px] md:text-[48px] tracking-tight leading-[1.08] mb-4 max-w-lg">
            Stop shipping documents you cannot trust.
          </h2>
          <p className="text-[15px] text-panel/40 max-w-md mb-8">
            Readiness. Compliance. Provenance. Validated by default for Jinja2 templates.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 items-start">
            <a href="https://github.com/verityengine/formforge" className="px-7 py-3.5 bg-rust hover:bg-rust-light text-white text-[14px] font-semibold rounded transition-colors inline-block">
              View on GitHub
            </a>
            <a href="#app" className="px-7 py-3.5 bg-panel text-ink text-[14px] font-semibold rounded transition-colors hover:bg-panel/90 inline-block">
              Try the playground
            </a>
            <div className="px-7 py-3.5 border border-panel/20 rounded inline-block">
              <code className="font-mono text-[13px] text-panel/60">pip install formforge</code>
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
      <HeroReveal />
      <TrustLayers />
      <ReadyDemo />
      <ComplianceWedge />
      <FinalCTA />
      <footer className="py-5 bg-ink border-t border-panel/10">
        <div className="max-w-[1280px] mx-auto px-6 md:px-10 flex items-center justify-between">
          <div className="text-panel/50"><AnimatedLogo size="small" /></div>
          <p className="text-panel/40 text-[10px] font-mono">formforge v0.1</p>
        </div>
      </footer>
    </div>
  )
}

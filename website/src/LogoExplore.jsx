/* Logo exploration — 4 concepts for Formforge */

export function LogoA({ size = 40 }) {
  // Concept A: Monogram "F" with validation strike
  // The F crossbar becomes the checkmark
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" fill="none">
      {/* Chamfered square frame */}
      <path d="M6 2h28l4 4v28l-4 4H6l-4-4V6z" stroke="currentColor" strokeWidth="1.8" opacity="0.8" />
      {/* F letterform — top bar and stem */}
      <path d="M13 10h14" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
      <path d="M13 10v20" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
      {/* Crossbar becomes validation strike — angled upward */}
      <path d="M13 20l5 0l9-7" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" opacity="0.9" />
    </svg>
  )
}

export function LogoB({ size = 40 }) {
  // Concept B: Forge anvil — abstract block with diagonal strike
  // Heavy, industrial, precise
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" fill="none">
      {/* Outer octagon */}
      <path d="M12 2h16l10 10v16l-10 10H12L2 28V12z" stroke="currentColor" strokeWidth="1.8" opacity="0.7" />
      {/* Inner document block */}
      <rect x="11" y="9" width="18" height="22" rx="2" stroke="currentColor" strokeWidth="1.5" opacity="0.4" />
      {/* Three structured lines */}
      <line x1="14" y1="14" x2="26" y2="14" stroke="currentColor" strokeWidth="1.5" opacity="0.35" strokeLinecap="round" />
      <line x1="14" y1="19" x2="22" y2="19" stroke="currentColor" strokeWidth="1.5" opacity="0.25" strokeLinecap="round" />
      <line x1="14" y1="24" x2="24" y2="24" stroke="currentColor" strokeWidth="1.5" opacity="0.25" strokeLinecap="round" />
      {/* Forge strike — bold diagonal */}
      <path d="M22 27l3.5 3.5L33 23" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" opacity="0.85" />
    </svg>
  )
}

export function LogoC({ size = 40 }) {
  // Concept C: Stylized F as a structural bracket/brace
  // The F is formed by brackets — { F } — code meets document
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" fill="none">
      {/* Left bracket */}
      <path d="M14 6c-4 0-6 2-6 6v6c0 2-2 2-2 2s2 0 2 2v6c0 4 2 6 6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" fill="none" opacity="0.5" />
      {/* F inside */}
      <path d="M17 12h10" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
      <path d="M17 12v16" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
      <path d="M17 20h7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" opacity="0.7" />
      {/* Checkmark integrated at bottom right */}
      <path d="M25 24l2.5 2.5L33 21" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" opacity="0.8" />
      {/* Right bracket (partial, implied) */}
      <path d="M34 14c0-2-1-3-3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" fill="none" opacity="0.25" />
    </svg>
  )
}

export function LogoD({ size = 40 }) {
  // Concept D: Abstract seal — concentric shapes implying validation/trust
  // Circle + inner structured form + strike
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" fill="none">
      {/* Outer circle — seal */}
      <circle cx="20" cy="20" r="18" stroke="currentColor" strokeWidth="1.8" opacity="0.6" />
      {/* Inner structured block */}
      <rect x="12" y="11" width="16" height="18" rx="2" stroke="currentColor" strokeWidth="1.2" opacity="0.3" />
      {/* Data lines */}
      <line x1="15" y1="16" x2="25" y2="16" stroke="currentColor" strokeWidth="1.5" opacity="0.4" strokeLinecap="round" />
      <line x1="15" y1="20" x2="22" y2="20" stroke="currentColor" strokeWidth="1.2" opacity="0.25" strokeLinecap="round" />
      <line x1="15" y1="24" x2="23" y2="24" stroke="currentColor" strokeWidth="1.2" opacity="0.25" strokeLinecap="round" />
      {/* Bold validation strike */}
      <path d="M21 26l2.5 2.5L30 22" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" opacity="0.85" />
    </svg>
  )
}

/* ── Preview page ── */
export default function LogoExplore() {
  const concepts = [
    { name: 'A: Monogram F', desc: 'F letterform with crossbar as validation strike', Logo: LogoA },
    { name: 'B: Forge Mark', desc: 'Octagonal seal, document block, diagonal strike', Logo: LogoB },
    { name: 'C: Bracket F', desc: 'F formed by code brackets, checkmark integrated', Logo: LogoC },
    { name: 'D: Seal', desc: 'Circular seal with structured block and strike', Logo: LogoD },
  ]

  return (
    <div style={{ background: '#0e0d0c', color: '#faf8f5', minHeight: '100vh', padding: '60px 40px', fontFamily: 'Inter, sans-serif' }}>
      <h1 style={{ fontFamily: 'DM Serif Display, serif', fontSize: 36, marginBottom: 60 }}>Logo Exploration</h1>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 40 }}>
        {concepts.map(({ name, desc, Logo }) => (
          <div key={name}>
            {/* On dark */}
            <div style={{ background: '#0e0d0c', border: '1px solid rgba(250,248,245,0.1)', borderRadius: 12, padding: 32, marginBottom: 16, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20 }}>
              <Logo size={64} />
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <Logo size={36} />
                <span style={{ fontFamily: 'DM Serif Display, serif', fontSize: 22, letterSpacing: '-0.02em' }}>Formforge</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Logo size={20} />
                <span style={{ fontFamily: 'DM Serif Display, serif', fontSize: 14 }}>Formforge</span>
              </div>
            </div>
            {/* On light */}
            <div style={{ background: '#ede8df', color: '#0e0d0c', border: '1px solid rgba(20,18,16,0.1)', borderRadius: 12, padding: 32, marginBottom: 16, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20 }}>
              <Logo size={64} />
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <Logo size={36} />
                <span style={{ fontFamily: 'DM Serif Display, serif', fontSize: 22, letterSpacing: '-0.02em' }}>Formforge</span>
              </div>
            </div>
            {/* Favicon size */}
            <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginTop: 8 }}>
              <div style={{ background: '#0e0d0c', borderRadius: 4, padding: 4, display: 'inline-flex' }}><Logo size={16} /></div>
              <div style={{ background: '#ede8df', color: '#0e0d0c', borderRadius: 4, padding: 4, display: 'inline-flex' }}><Logo size={16} /></div>
              <span style={{ fontSize: 11, color: 'rgba(250,248,245,0.4)' }}>16px</span>
            </div>
            {/* Label */}
            <div style={{ marginTop: 16 }}>
              <div style={{ fontSize: 14, fontWeight: 600 }}>{name}</div>
              <div style={{ fontSize: 12, color: 'rgba(250,248,245,0.4)', marginTop: 4 }}>{desc}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function PolygonBackground() {
  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 0, pointerEvents: 'none', overflow: 'hidden' }}>

      {/* Layer 1 — Base gradient */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'linear-gradient(180deg, #0b4561 0%, #0a3f59 50%, #08384f 100%)'
      }} />

      {/* Layer 2 — Bright radial zones (light sources) */}
      <div style={{
        position: 'absolute', inset: 0,
        background: `
          radial-gradient(ellipse at 80% 15%, rgba(0,180,255,0.18) 0%, transparent 45%),
          radial-gradient(ellipse at 25% 10%, rgba(0,255,200,0.10) 0%, transparent 38%),
          radial-gradient(ellipse at 60% 70%, rgba(20,120,200,0.10) 0%, transparent 40%)
        `
      }} />

      {/* Layer 3 — Large diamond facets SVG */}
      <svg
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}
        viewBox="0 0 1920 1080"
        preserveAspectRatio="xMidYMid slice"
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* Huge background diamonds — 30-40% screen width */}
        <polygon points="960,80 1340,400 960,720 580,400"
          fill="rgba(255,255,255,0.04)" stroke="rgba(255,255,255,0.03)" strokeWidth="1"
          style={{ mixBlendMode: 'screen' }} />
        <polygon points="300,200 620,460 300,720 -20,460"
          fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.025)" strokeWidth="1"
          style={{ mixBlendMode: 'screen' }} />
        <polygon points="1600,100 1920,380 1600,660 1280,380"
          fill="rgba(255,255,255,0.04)" stroke="rgba(255,255,255,0.03)" strokeWidth="1"
          style={{ mixBlendMode: 'screen' }} />
        <polygon points="700,500 1020,760 700,1020 380,760"
          fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.02)" strokeWidth="1"
          style={{ mixBlendMode: 'screen' }} />
        <polygon points="1400,500 1720,760 1400,1020 1080,760"
          fill="rgba(255,255,255,0.035)" stroke="rgba(255,255,255,0.025)" strokeWidth="1"
          style={{ mixBlendMode: 'screen' }} />

        {/* Medium facets — color varied */}
        <polygon points="0,0 320,0 180,200 0,150"
          fill="rgba(10,82,101,0.55)" stroke="rgba(255,255,255,0.04)" strokeWidth="0.5" />
        <polygon points="320,0 680,0 580,220 180,200"
          fill="rgba(13,107,135,0.45)" stroke="rgba(255,255,255,0.035)" strokeWidth="0.5" />
        <polygon points="680,0 1020,0 960,200 580,220"
          fill="rgba(9,74,100,0.50)" stroke="rgba(255,255,255,0.04)" strokeWidth="0.5" />
        <polygon points="1020,0 1360,0 1280,180 960,200"
          fill="rgba(18,128,191,0.35)" stroke="rgba(255,255,255,0.05)" strokeWidth="0.5" />
        <polygon points="1360,0 1920,0 1920,220 1280,180"
          fill="rgba(42,159,255,0.20)" stroke="rgba(255,255,255,0.06)" strokeWidth="0.5" />

        <polygon points="0,150 180,200 120,440 0,420"
          fill="rgba(7,55,79,0.60)" stroke="rgba(255,255,255,0.03)" strokeWidth="0.5" />
        <polygon points="180,200 580,220 500,460 120,440"
          fill="rgba(11,86,112,0.45)" stroke="rgba(255,255,255,0.04)" strokeWidth="0.5" />
        <polygon points="580,220 960,200 940,480 500,460"
          fill="rgba(15,105,140,0.40)" stroke="rgba(255,255,255,0.05)" strokeWidth="0.5" />
        <polygon points="960,200 1280,180 1320,460 940,480"
          fill="rgba(20,130,185,0.35)" stroke="rgba(255,255,255,0.05)" strokeWidth="0.5" />
        <polygon points="1280,180 1920,220 1920,480 1320,460"
          fill="rgba(42,159,255,0.18)" stroke="rgba(255,255,255,0.06)" strokeWidth="0.5" />

        <polygon points="0,420 120,440 80,680 0,660"
          fill="rgba(7,50,72,0.65)" stroke="rgba(255,255,255,0.03)" strokeWidth="0.5" />
        <polygon points="120,440 500,460 440,700 80,680"
          fill="rgba(10,80,105,0.50)" stroke="rgba(255,255,255,0.04)" strokeWidth="0.5" />
        <polygon points="500,460 940,480 920,720 440,700"
          fill="rgba(13,100,130,0.42)" stroke="rgba(255,255,255,0.04)" strokeWidth="0.5" />
        <polygon points="940,480 1320,460 1380,720 920,720"
          fill="rgba(18,120,170,0.38)" stroke="rgba(255,255,255,0.05)" strokeWidth="0.5" />
        <polygon points="1320,460 1920,480 1920,740 1380,720"
          fill="rgba(30,142,216,0.22)" stroke="rgba(255,255,255,0.06)" strokeWidth="0.5" />

        <polygon points="0,660 80,680 60,920 0,900"
          fill="rgba(7,48,69,0.70)" stroke="rgba(255,255,255,0.025)" strokeWidth="0.5" />
        <polygon points="80,680 440,700 400,940 60,920"
          fill="rgba(9,68,92,0.58)" stroke="rgba(255,255,255,0.03)" strokeWidth="0.5" />
        <polygon points="440,700 920,720 900,980 400,940"
          fill="rgba(11,85,112,0.48)" stroke="rgba(255,255,255,0.04)" strokeWidth="0.5" />
        <polygon points="920,720 1380,720 1420,980 900,980"
          fill="rgba(15,108,148,0.40)" stroke="rgba(255,255,255,0.04)" strokeWidth="0.5" />
        <polygon points="1380,720 1920,740 1920,1080 1420,980"
          fill="rgba(25,135,200,0.25)" stroke="rgba(255,255,255,0.05)" strokeWidth="0.5" />

        <polygon points="0,900 60,920 0,1080"
          fill="rgba(6,44,64,0.75)" />
        <polygon points="60,920 400,940 360,1080 0,1080"
          fill="rgba(8,60,84,0.65)" stroke="rgba(255,255,255,0.025)" strokeWidth="0.5" />
        <polygon points="400,940 900,980 880,1080 360,1080"
          fill="rgba(10,78,104,0.55)" stroke="rgba(255,255,255,0.03)" strokeWidth="0.5" />
        <polygon points="900,980 1420,980 1440,1080 880,1080"
          fill="rgba(13,96,130,0.48)" stroke="rgba(255,255,255,0.035)" strokeWidth="0.5" />
        <polygon points="1420,980 1920,1080 1440,1080"
          fill="rgba(20,120,175,0.35)" stroke="rgba(255,255,255,0.04)" strokeWidth="0.5" />
        <polygon points="1420,980 1920,740 1920,1080"
          fill="rgba(25,135,200,0.28)" stroke="rgba(255,255,255,0.04)" strokeWidth="0.5" />
      </svg>

      {/* Layer 4 — Vertical glass strips (right side crystal effect) */}
      <div style={{ position: 'absolute', inset: 0 }}>
        {[1680, 1740, 1800, 1860].map((x, i) => (
          <div key={i} style={{
            position: 'absolute',
            left: x,
            top: '5%',
            width: 28 - i * 4,
            height: '45%',
            background: `linear-gradient(180deg, rgba(255,255,255,${0.07 - i * 0.01}) 0%, rgba(255,255,255,0.01) 100%)`,
            filter: 'blur(1.5px)',
            borderRadius: 4,
            transform: `rotate(${-8 + i * 2}deg)`,
          }} />
        ))}
      </div>

      {/* Layer 5 — Dot matrix */}
      <div style={{
        position: 'absolute', inset: 0,
        backgroundImage: 'radial-gradient(rgba(255,255,255,0.07) 1px, transparent 1px)',
        backgroundSize: '28px 28px',
      }} />

    </div>
  );
}

# ExaSignal UI/UX Documentation

> "Predição de mercados tão simples como ver a meteorologia"

---

## Design Principles

1. **3 Second Rule** - User understands the main insight in 3 seconds
2. **Human Language** - "Market says: Unlikely" not "28% probability"
3. **One Focus** - Single hero metric per view
4. **Progressive Disclosure** - Details on demand, not upfront

---

## Navigation Structure

```
🏠 Home (Today's Picks)
├── 🔥 Today's Picks (default)
├── 🤖 AI Markets
├── 🚗 Autonomous
├── 💰 Crypto
└── 🗳️ Politics

📊 Markets (Full List)
├── Search
├── Filter by category
└── Sort by movement/odds

🔔 Alerts
├── Active alerts
└── History

👤 Profile
├── Settings
└── Telegram link
```

---

## Color System

| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| `--bg-primary` | #FFFFFF | #0F0F14 | Main background |
| `--bg-secondary` | #F8FAFC | #1A1A24 | Cards |
| `--accent` | #7C3AED | #7C3AED | CTAs, highlights |
| `--success` | #10B981 | #10B981 | YES, positive |
| `--danger` | #EF4444 | #EF4444 | NO, negative |
| `--warning` | #F59E0B | #F59E0B | Neutral, caution |
| `--text-primary` | #0F172A | #F8FAFC | Headings |
| `--text-muted` | #64748B | #94A3B8 | Secondary text |

---

## Typography

| Element | Size (Desktop) | Size (Mobile) | Weight |
|---------|----------------|---------------|--------|
| Hero Number | 72px | 56px | 800 |
| Card Title | 24px | 20px | 600 |
| Body | 16px | 16px | 400 |
| Caption | 14px | 14px | 400 |
| Label | 12px | 12px | 500 |

Font Family: `Inter, -apple-system, sans-serif`

---

## Spacing Scale

```
4px   (0.25rem)  → micro
8px   (0.5rem)   → tight
16px  (1rem)     → base
24px  (1.5rem)   → comfortable
32px  (2rem)     → relaxed
48px  (3rem)     → spacious
80px  (5rem)     → generous
```

---

## Components

### Market Card

```
┌─────────────────────────────────┐
│  OpenAI IPO by June?       🔥   │  ← Title + Hot indicator
│                                 │
│           28%                   │  ← Hero number (success color)
│  ━━━━━━━━━━░░░░░░░░░░░         │  ← Probability bar
│                                 │
│  Market says: Unlikely          │  ← Human interpretation
│                                 │
│  📰 3 sources  ⬆️ +5% today     │  ← Meta info
└─────────────────────────────────┘
```

### Category Tab

```
┌────────────────┐    ┌────────────────┐
│ 🔥 Today's     │    │ 🤖 AI          │
│    Picks       │    │                │
└────────────────┘    └────────────────┘
   ↑ Selected            ↑ Default
   (filled bg)           (outline)
```

### Probability Bar

```
YES ━━━━━━━━━━░░░░░░░░░░░ NO
    ← Green      Red →
         ● ← Current position
```

### CTA Button

```
┌─────────────────────────────┐
│    Get Full Analysis  →     │
└─────────────────────────────┘
Background: gradient(accent)
Text: white
Shadow: 0 4px 12px rgba(124, 58, 237, 0.3)
```

---

## Breakpoints

| Name | Width | Layout |
|------|-------|--------|
| `mobile-s` | 320px | Single column |
| `mobile-l` | 428px | Single column |
| `tablet` | 768px | 2 columns |
| `desktop` | 1024px | Sidebar + content |
| `desktop-l` | 1440px | Sidebar + content + panel |

---

## Animations

| Element | Animation | Duration |
|---------|-----------|----------|
| Card Hover | translateY(-2px) + shadow | 200ms |
| Number Load | Count up | 800ms |
| Tab Switch | Fade + slide | 300ms |
| Alert In | Slide from right | 400ms |
| Pull Refresh | Spin icon | continuous |

Easing: `cubic-bezier(0.4, 0, 0.2, 1)`

---

## Accessibility

- Minimum touch target: 48x48px
- Color contrast ratio: ≥ 4.5:1
- Focus states on all interactive elements
- Screen reader labels for icons
- Reduced motion option

---

## File Structure

```
dashboard/
├── app/
│   ├── layout.tsx
│   ├── page.tsx (Home)
│   ├── markets/
│   └── alerts/
├── components/
│   ├── ui/ (shadcn)
│   ├── MarketCard.tsx
│   ├── CategoryTabs.tsx
│   ├── ProbabilityBar.tsx
│   └── AlertFeed.tsx
├── lib/
│   ├── api.ts
│   └── utils.ts
└── styles/
    └── globals.css
```

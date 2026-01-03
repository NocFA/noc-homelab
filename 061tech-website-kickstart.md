# 061 Tech Website Kickstart

**Business**: Courier-based PC & laptop repair service
**Location**: Limerick, Ireland
**Owner**: Adam Looney
**Target Launch**: Q2 2026

---

## Current Implementation Status

> **Last Updated**: January 2026

### Completed
- [x] Astro project setup with full structure
- [x] Colour system implemented (Light + Shannon Teal dark theme)
- [x] Typography and CSS custom properties
- [x] Header, Footer, Base layout components
- [x] Theme toggle (defaults to light mode)
- [x] All 7 pages built and functional
- [x] SEO meta tags with local Limerick keywords
- [x] LocalBusiness JSON-LD structured data
- [x] Symptom-based services approach (layman-friendly)
- [x] Full pricing tables with turnaround times
- [x] Remote services section
- [x] Service packages (Basic, Standard, Premium)

### Live Pages

| Page | Path | Status |
|------|------|--------|
| Homepage | `/` | Complete |
| Services & Pricing | `/services` | Complete |
| How It Works | `/how-it-works` | Complete |
| Book a Repair | `/book` | Complete (needs Formspree ID) |
| Contact | `/contact` | Complete (needs Formspree ID) |
| About | `/about` | Complete |
| FAQ | `/faq` | Complete |

### Pending
- [ ] Register domain (061tech.ie)
- [x] Remove phone number placeholders (no phone - digital-first)
- [ ] Set up Formspree and add form IDs
- [ ] Deploy main website to Coolify
- [ ] Deploy Chatwoot to Coolify (chat.061tech.ie)
- [ ] Deploy Cal.com to Coolify (book.061tech.ie)
- [ ] Configure CloudFlare for all subdomains
- [ ] Add Chatwoot widget to website
- [ ] Add Cal.com booking links
- [ ] Set up WhatsApp Business link
- [x] Create Open Graph images (og-image.png 1200x630, og-image-square.png 600x600)
- [x] Create favicon (favicon.svg, favicon.ico, apple-touch-icon.png)
- [x] 404 page with Limerick slang ("Story bud?")
- [x] FAQ schema markup for Google rich results
- [x] SEO competitor analysis and keyword optimization
- [x] AI fingerprint removal from source code
- [x] CLAUDE.md project documentation created

### Project Location
```
/Users/noc/noc-homelab/061tech/
```

### Development Commands
```bash
# Start dev server
cd /Users/noc/noc-homelab/061tech && npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

---

## Source Code Quality

### AI Fingerprint Removal

The source code has been cleaned to look human-written. Removed patterns:
- Verbose explanatory comments (e.g., `/* This handles the dropdown menu */`)
- Section dividers (e.g., `/* ========== BUTTONS ========== */`)
- Inline comments explaining obvious code
- Docblocks stating the obvious

**Retained**: Simple one-line section markers like `/* Tables */` which humans write too.

### CLAUDE.md

Project documentation for AI assistants is in `/Users/noc/noc-homelab/061tech/CLAUDE.md`. This provides context about the tech stack, project structure, commands, and design system without requiring inspection of source files.

### Version Control

The project is tracked in the main noc-homelab repository. For standalone development:
```bash
cd /Users/noc/noc-homelab/061tech
git init  # If separating from parent repo
```

---

## 1. Business Name: 061 Tech

**Why this works:**
- 061 is Limerick's area code - instantly recognizable to locals
- Short, professional, memorable
- Doesn't try too hard or sound gimmicky
- Works internationally without explanation needed
- Domain candidates: `061tech.ie` (primary), `061.tech`, `061-tech.ie`

**Tagline options:**
- "Limerick's courier repair service" (direct, explains the model)
- "We collect. We fix. We deliver." (action-focused)
- "Repair without the hassle" (benefit-focused)

---

## 2. Design Philosophy: Anti-AI Patterns

The goal is a website that looks like a skilled human built it, not a template or AI output. This means deliberately avoiding common AI/template tells.

### What to AVOID

| Pattern | Why it screams "AI-generated" |
|---------|-------------------------------|
| Hover glow effects on everything | Every Tailwind template has these |
| Purple-blue gradients | The AI default colour scheme |
| Perfectly symmetrical 3-column cards | Cookie-cutter layout |
| "Hero → Features → Testimonials → CTA → Footer" | The exact same structure as 10,000 other sites |
| Excessive whitespace with giant rounded corners | Modern template syndrome |
| Animations on every scroll | Distracting, slows performance |
| Vague marketing copy ("We're here to help you succeed") | Says nothing, AI filler |
| Icon-heavy feature grids | Every SaaS landing page |
| Floating elements, parallax backgrounds | Adds complexity, no value |
| Generic stock photos of people on laptops | Instantly recognizable as fake |

### What to EMBRACE

| Pattern | Why it works |
|---------|--------------|
| Asymmetric layouts occasionally | Feels hand-crafted |
| Real information upfront (prices, process) | Humans want answers, not fluff |
| System fonts for body text | Fast, familiar, professional |
| Subtle, purposeful interactions | Only animate what matters |
| Dense information where appropriate | Tables for pricing, specs |
| Direct language | "Book a Repair" not "Get Started Today" |
| Personality in the copy | Sounds like a real person wrote it |
| Functional over decorative | Every element earns its place |
| Custom CSS properties | Not utility class soup |
| Semantic HTML | Proper structure, accessibility |

### Specific Design Rules

1. **No more than 2 interactive states per element** (default + hover, that's it)
2. **Animations under 200ms** - if any at all
3. **Prices visible without clicking anything**
4. **Contact information in footer and header**
5. **No "testimonials" section until you have real ones**
6. **Forms that work without JavaScript**
7. **Tables where tables make sense** (pricing, services)
8. **No carousels** - they're universally hated and ignored
9. **No chatbots or floating widgets**
10. **Page loads under 1 second on 3G**

---

## 3. Technical Stack

### Framework: Astro

**Why Astro over alternatives:**
- Ships 0KB JavaScript by default
- Components still work (use Vue/Svelte/React inside Astro when needed)
- Static output = no server runtime = smaller attack surface
- Coolify supports Astro natively
- Excellent lighthouse scores out of the box
- Markdown content support built-in

**Project structure:**
```
061tech/
├── src/
│   ├── components/
│   │   ├── Header.astro
│   │   ├── Footer.astro
│   │   ├── ServiceCard.astro
│   │   ├── PriceTable.astro
│   │   ├── BookingForm.astro      # Could be Vue/Svelte for interactivity
│   │   ├── ContactInfo.astro
│   │   └── ThemeToggle.astro      # Small JS island for dark/light
│   ├── layouts/
│   │   ├── Base.astro             # HTML shell, meta, theme
│   │   └── Page.astro             # Standard page wrapper
│   ├── pages/
│   │   ├── index.astro            # Homepage
│   │   ├── services.astro         # Full service list + pricing
│   │   ├── how-it-works.astro     # Process explanation
│   │   ├── book.astro             # Booking form
│   │   ├── about.astro            # About Adam/the business
│   │   ├── contact.astro          # Contact details + form
│   │   └── faq.astro              # Common questions
│   ├── styles/
│   │   ├── global.css             # CSS custom properties, reset
│   │   └── components.css         # Component-specific styles
│   ├── data/
│   │   └── config.ts              # Centralized brands, prices, services
│   └── content/
│       └── services/              # Markdown files for each service
│           ├── screen-replacement.md
│           ├── ssd-upgrade.md
│           └── ...
├── public/
│   ├── favicon.ico
│   ├── og-image.png              # Social share image
│   └── robots.txt
├── astro.config.mjs
└── package.json
```

### Centralized Configuration (`src/data/config.ts`)

All brand names, prices, and service data are stored in one file for easy updates:

```typescript
// src/data/config.ts

// BRANDS - Change these to update brand mentions across the site
export const brands = {
  gpu: ['Nvidia GeForce RTX', 'AMD Radeon RX', 'Intel ARC'],
  cpu: ['Intel Core i5/i7/i9', 'AMD Ryzen 5/7/9'],
  ssd: ['Samsung', 'Crucial', 'WD'],
  ram: ['DDR4', 'DDR5'],
  motherboard: ['Intel', 'AMD', 'ASUS', 'MSI', 'Gigabyte'],
  psu: ['Corsair', 'EVGA', 'Seasonic'],
};

// PRICING - All prices in one place
export const pricing = {
  upgrades: {
    ssd: '€60-90 + parts',
    ram: '€40-60 + parts',
    gpu: '€60-100 + parts',
    // ... etc
  },
  remote: {
    videoDiagnosis: '€20',
    ongoingSupport: '€30/hr',  // Flat hourly rate
    // ... etc
  },
  // ... other categories
};
```

**Benefits:**
- Change "Nvidia GeForce RTX" to "Nvidia RTX" in one place, updates everywhere
- Adjust pricing without hunting through multiple files
- Add new GPU brands (like Intel ARC) once, appears in all relevant pages
- SEO keywords auto-generated from brand lists

**Usage in components:**
```astro
---
import { brands, pricing, services } from '../data/config';
---
<p>GPU brands: {brands.gpu.join(', ')}</p>
<p>SSD Upgrade: {pricing.upgrades.ssd}</p>
```

### No external CSS frameworks

- No Tailwind (too recognizable, utility soup)
- No Bootstrap (dated, heavy)
- Write custom CSS with CSS custom properties
- Keep it under 20KB total CSS

### Minimal JavaScript

- Theme toggle (localStorage, ~20 lines)
- Form validation (progressive enhancement)
- Mobile menu (if needed, CSS-only preferred)
- That's it. No analytics scripts, no third-party widgets.

---

## 4. Colour System

### Philosophy

Amber/gold accent is excellent because:
- Warm and trustworthy (unlike cold tech blues)
- Stands out from typical tech websites
- Works beautifully in both dark and light themes
- Subtle connection to Irish gold/Celtic heritage without being cheesy

### Light Theme

```css
:root {
  /* Backgrounds */
  --bg-primary: #fafaf9;           /* Warm off-white, not pure white */
  --bg-secondary: #f5f5f4;         /* Slightly darker for sections */
  --bg-elevated: #ffffff;          /* Cards, modals */

  /* Text */
  --text-primary: #1c1917;         /* Near-black, warm undertone */
  --text-secondary: #57534e;       /* Grey for secondary content */
  --text-muted: #a8a29e;           /* Captions, hints */

  /* Accent - Amber/Gold */
  --accent: #d97706;               /* Primary amber - buttons, links */
  --accent-hover: #b45309;         /* Darker on interaction */
  --accent-subtle: #fef3c7;        /* Backgrounds for highlights */

  /* Functional */
  --success: #16a34a;
  --error: #dc2626;
  --border: #e7e5e4;

  /* Shadows */
  --shadow-sm: 0 1px 2px rgba(28, 25, 23, 0.05);
  --shadow-md: 0 4px 6px rgba(28, 25, 23, 0.07);
}
```

### Dark Theme - Shannon Teal

> **Note**: Changed from black/grey to deep teal to avoid Pornhub colour association (black + orange + white).
> Shannon teal chosen as a local connection to the River Shannon.

```css
[data-theme="dark"] {
  /* Backgrounds - Shannon Teal (deep river-inspired) */
  --bg-primary: #0a2e30;           /* Deep teal */
  --bg-secondary: #0f3d40;         /* Slightly lighter for sections */
  --bg-elevated: #145252;          /* Cards, modals */

  /* Text */
  --text-primary: #f0fdfa;         /* Soft cyan-white */
  --text-secondary: #99e0d9;       /* Teal-tinted grey */
  --text-muted: #5eaba3;           /* Muted content */

  /* Accent - Amber pops beautifully against teal */
  --accent: #f59e0b;               /* Amber */
  --accent-hover: #fbbf24;         /* Brighter on hover */
  --accent-subtle: #134545;        /* Dark teal for amber highlights */

  /* Functional */
  --success: #34d399;
  --error: #f87171;
  --border: #1a5456;

  /* Shadows */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
  --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.4);
}
```

### Logo Colours

```
Light mode: 061 (amber #d97706) + Tech (dark text #1c1917)
Dark mode:  061 (amber #f59e0b) + Tech (light text #f0fdfa)
```

This reverses the original "white 061 + orange Tech" which looked too similar to Pornhub's branding.

### Usage Rules

1. **Accent sparingly** - Only for CTAs, links, and key highlights. Never backgrounds.
2. **Text on accent** - Always use `--text-primary` (near-black) on amber backgrounds.
3. **No gradients** - Flat colours only. Gradients scream template.
4. **Borders subtle** - 1px, muted colours, only where needed.

---

## 5. Typography

### Font Stack

```css
:root {
  /* System fonts - fast, familiar, no flash of unstyled text */
  --font-body: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
               "Helvetica Neue", Arial, sans-serif;

  /* Monospace for technical details, prices */
  --font-mono: ui-monospace, "SF Mono", "Cascadia Code", Consolas,
               "Liberation Mono", Menlo, monospace;
}
```

### Type Scale

```css
:root {
  --text-xs: 0.75rem;      /* 12px - captions */
  --text-sm: 0.875rem;     /* 14px - secondary text */
  --text-base: 1rem;       /* 16px - body */
  --text-lg: 1.125rem;     /* 18px - lead paragraphs */
  --text-xl: 1.25rem;      /* 20px - subheadings */
  --text-2xl: 1.5rem;      /* 24px - section headings */
  --text-3xl: 1.875rem;    /* 30px - page titles */
  --text-4xl: 2.25rem;     /* 36px - hero text */

  --leading-tight: 1.25;
  --leading-normal: 1.6;
  --leading-relaxed: 1.75;
}
```

### Rules

1. **Body text: 16px minimum** - Accessibility requirement
2. **Line height: 1.5-1.7 for body** - Readability
3. **No more than 3 font sizes per page** - Consistency
4. **Bold sparingly** - For emphasis, not decoration
5. **Prices in monospace** - Aligns numbers, looks deliberate

---

## 6. Page Structure

### Homepage (IMPLEMENTED)

**Goal**: Immediately answer "What is this? How does it work? How much?"

```
[Header: Logo (061Tech) | Services | How it Works | Book | Contact | Theme toggle]

[Hero section]
  - Headline: "PC & Laptop Repair, Collected and Delivered"
  - Subhead: "We pick up your device, fix it, and bring it back. Serving Limerick city and county."
  - Two buttons: "Book a Repair" (primary) | "See Pricing" (secondary)

[How it Works - 4 steps, horizontal on desktop, vertical on mobile]
  1. Book (Online or call)
  2. Collection (Courier picks up)
  3. Repair (We fix it)
  4. Return (Delivered back)

[What's Wrong With Your Computer? - SYMPTOM-BASED APPROACH]
  Layman-friendly cards showing problems, not technical services.
  Uses Gandi-style "From" label: small caps, muted, stacked above price.

  - Won't turn on (From €100) → Hardware Diagnosis & Repair
  - Running really slow (From €60) → SSD Upgrade or Tune-up
  - Virus or pop-ups (From €60) → Virus Removal & Security
  - Lost important files (From €80) → Data Recovery
  - Need a fresh start (From €65) → Windows Reinstall
  - Something else? (€20 - flat rate, no "From") → Video Diagnosis [HIGHLIGHTED]
  - Link: "View full pricing breakdown →"

[Want More Power? - Upgrades section]
  - SSD Upgrade (From €60) - The #1 speed boost for any computer
  - RAM Upgrade (From €40) - More memory for multitasking
  - GPU Upgrade (From €60) - Better graphics - Nvidia, AMD, Intel
  - Custom PC Build (From €100) - I build it, you game on it
  - Link: "See all upgrades - CPU, motherboard, PSU →"

[Remote Services]
  - Security Setup (From €30) - VPN, password manager, secure browsing
  - Performance Tune-up (From €40) - Remove bloatware, speed up startup
  - Software Install (From €40) - Office 365, email, printers
  - Ongoing Support (€30/hr - flat rate, no "From") - Remote help when you need it

[Why Courier-Based Repair?]
  Intro: "You shouldn't have to rearrange your day to get your computer fixed."
  - No driving across town to drop it off
  - No waiting around in a shop
  - No trying to find parking
  - No taking time off work
  Summary: "I send a courier to collect it, fix it at my workshop, and send it back. You stay home."

[About snippet]
  - "10+ years in IT. Based in Limerick. I fix computers because I enjoy it.
     No upselling, no jargon, just honest repairs at fair prices."
  - Link: "More about 061 Tech →"

[Footer]
  - Contact: hello@061tech.ie (primary email), WhatsApp, Live Chat
  - Availability: Monday - Friday, Replies within 24 hours
  - "Book a Consultation" button → Cal.com
  - Links: Services, How It Works, Book, Contact, About, FAQ
  - Copyright with theme toggle
```

### Services Page (IMPLEMENTED)

**Goal**: Full pricing transparency. No hidden costs.

```
[Page Header]
  - Title: "Services & Pricing"
  - Intro: "Transparent pricing. No hidden fees. If I can't fix it, you don't pay."

[Not Sure? Callout - PROMINENT]
  Highlighted box:
  "Not sure what's wrong? Don't worry - most people aren't. Book a €20 video
   diagnosis and I'll help figure out the problem and give you an honest quote.
   If you go ahead with the repair, the €20 comes off your bill."
  - Button: "Book Video Diagnosis" → Cal.com

[Sticky Quick Jump Navigation]
  - Centered pills with Gandi-style offset shadows (press effect on hover)
  - Sticky nav bar that stays at top when scrolling
  - Pull tab dismiss: appears only when sticky, auto-restores when scrolled back up
  - Floating restore button (top-right) to manually bring back if needed
  - Shadow appears when sticky (IntersectionObserver for performance)
  - Mobile: more compact pills, smaller shadows
  - Pills: Won't turn on | Running slow | Virus/pop-ups | Lost files |
           Upgrade parts | Custom PC build | Remote help

  **FIXED - Pull tab & mobile UX redesigned:**
  - Changed from down chevron to grab handle (two horizontal lines) - universal "drag me" indicator
  - Tab now seamlessly extends from nav's bottom edge
  - Hover highlights with accent color for clear affordance
  - **Mobile**: Horizontal scroll instead of wrapping (single row)
  - **Mobile**: Fade gradients on edges indicate more content (dynamic left/right)
  - **Mobile**: Larger touch targets for better usability

[Section: Hardware Repairs] #hardware
  | Service               | Description                          | Price           | Turnaround* |
  |-----------------------|--------------------------------------|-----------------|-------------|
  | Hardware Diagnostics  | Full system assessment               | €40-65          | 1-2 days    |
  | Component Replacement | Fans, batteries, power jacks, ports  | €50-100 + parts | 1-3 days    |
  | Deep Cleaning         | Dust removal, thermal paste          | €40-65          | 1-2 days    |
  | Screen Replacement    | Laptop LCD/LED panel                 | Coming Soon     | -           |

[Section: Component Upgrades] #upgrades
  | Service              | Description                                              | Price            | Turnaround* |
  |----------------------|----------------------------------------------------------|------------------|-------------|
  | SSD Upgrade          | Samsung, Crucial, WD + data migration                    | €60-90 + parts   | 1-2 days    |
  | RAM Upgrade          | DDR4, DDR5                                               | €40-60 + parts   | 1-2 days    |
  | GPU Upgrade          | Nvidia GeForce RTX, AMD Radeon RX, Intel ARC             | €60-100 + parts  | 1-2 days    |
  | CPU Upgrade          | Intel Core i5/i7/i9, AMD Ryzen 5/7/9                     | €80-120 + parts  | 2-3 days    |
  | Motherboard Upgrade  | Intel, AMD, ASUS, MSI, Gigabyte                          | €100-150 + parts | 2-3 days    |
  | Power Supply (PSU)   | Corsair, EVGA, Seasonic                                  | €50-80 + parts   | 1-2 days    |

[Section: Build & Assembly Services] #builds
  | Service              | Description                                    | Price      | Turnaround* |
  |----------------------|------------------------------------------------|------------|-------------|
  | Case Swap            | Move components to new case                    | €80-120    | 2-3 days    |
  | Custom PC Build      | I build from parts you provide or spec         | €100-200   | 3-5 days    |
  | Full System Overhaul | Multiple upgrades + clean Windows install      | €150-250   | 3-5 days    |

[Section: Software & Security] #software
  | Service              | Description                        | Price    | Turnaround* |
  |----------------------|------------------------------------|----------|-------------|
  | Virus & Malware      | Deep clean, restore security       | €60-80   | 1-2 days    |
  | Windows Reinstall    | Fresh Windows 10/11, drivers       | €65-100  | 1-2 days    |
  | Performance Tune-up  | Remove bloatware, optimise startup | €30-40   | 1-2 days    |
  | Software Install     | Office 365, browsers, printers     | €30-80   | 1-2 days    |

[Section: Data Recovery & Backup] #data
  | Service               | Description                      | Price     | Turnaround* |
  |-----------------------|----------------------------------|-----------|-------------|
  | Data Recovery (Basic) | Recover from accessible drives   | €80-120   | 1-3 days    |
  | Data Recovery (Adv)   | Recover from failing drives      | €120-200  | 3-5 days    |
  | Data Migration        | Transfer files to new PC         | €50-80    | 1-2 days    |
  | Backup Setup          | Configure automatic backups      | €40-50    | 1-2 days    |

[Section: Remote Services] #remote
  | Service              | Description                        | Price      | Note                 |
  |----------------------|------------------------------------|------------|----------------------|
  | Video Diagnosis      | Figure out what's wrong via call   | €20        | Credited toward repair |
  | Security Hardening   | VPN, password manager, secure DNS  | €20-40     |                      |
  | Remote Tune-up       | Bloatware removal, cleanup         | €30-40     |                      |
  | Software Setup       | Install programs remotely          | €30-60     |                      |
  | Ongoing Support      | Remote help when you need it       | €30/hr     | Flat hourly rate     |

[Section: Service Packages] #packages
  Three cards:
  - Basic: Repair only, standard warranty (Repair cost only)
  - Standard [POPULAR]: Repair + Security + Tune-up + 30-day warranty (Repair + €50)
  - Premium: Above + Backup + 1 hour remote support + 60-day warranty (Repair + €100)

[Section: Courier Collection & Delivery]
  Laptops:
  - Limerick City: €30-40 total (collection + return)
  - County Limerick: €40-50 total

  Desktop PCs:
  - Limerick City: €50-60 total (heavier, need careful handling)
  - County Limerick: €60-70 total

  Note: "Exact costs quoted when you book. You can also arrange your own courier,
        or drop off/collect in person by arrangement."

[CTA Section]
  - "Ready to get your computer fixed?"
  - Buttons: "Book a Repair" | "Contact Me"
```

**SEO Keywords in page description:**
- SSD, RAM, GPU (Nvidia GeForce, AMD Radeon, Intel ARC)
- CPU (Intel Core, AMD Ryzen)
- Motherboard, PSU
- Custom PC builds, case swaps
- Virus removal, data recovery
- Courier collection, Limerick

### How It Works Page (IMPLEMENTED)

**Goal**: Explain the process, reduce anxiety about sending device away.

```
[Page Header]
  - Title: "How It Works"
  - Intro: "Computer repair without leaving your house. Here's the process from start to finish."

[5 Detailed Steps with bullet points]
  Step 1: Book Online
    - Fill in the booking form or chat/email/WhatsApp
    - Describe the problem as best you can
    - Get an estimate before committing
    - Not sure what's wrong? €20 video diagnosis available via Cal.com

  Step 2: Courier Collects Your Device
    - Collection scheduled at a time that suits you
    - Weekdays, flexible timing
    - Laptops and desktops both collected
    - Device is handled carefully and insured in transit

  Step 3: Diagnosis & Quote
    - Full diagnostic within 1-2 days of receiving device
    - You get a clear quote with no hidden fees
    - If it's not worth fixing, I'll tell you honestly
    - No work starts until you approve the quote

  Step 4: Repair
    - Quality parts used (no cheap knockoffs)
    - Full testing before sign-off
    - Updates via text or email
    - You can ask questions anytime

  Step 5: Courier Returns Your Device
    - Return scheduled when device is ready
    - Pay on delivery or online beforehand
    - All repairs come with warranty
    - Support available if any issues

[Typical Timeline - Visual]
  Day 1: You book, courier collects
  Day 2: Device arrives, diagnosis starts
  Day 2-3: Quote sent, you approve
  Day 3-5: Repair completed, tested
  Day 5-7: Courier returns device

[Common Questions - 4 FAQ preview cards]
  - What if you can't fix it?
  - How long does the whole process take?
  - Is my data safe?
  - Can I drop off instead of using courier?

[CTA Section]
```

### Book Page (IMPLEMENTED)

**Goal**: Simple form that captures essential info.

```
[Page Header]
  - Title: "Book a Repair"
  - Intro: "Tell me what's wrong and I'll get back to you within 24 hours."

[Two-column layout: Form + Sidebar]

[Form - Left column]
  - Name *
  - Phone * / Email (row)
  - Address (for courier collection) *
  - Device Type: Laptop / Desktop / Other
  - What's the problem? * (textarea with hint)
  - Service needed (if you know): dropdown
    - Not sure / Other
    - Video Diagnosis (€20) - Help me figure it out
    - Hardware Repair
    - Virus / Malware Removal
    - Speed Issues
    - Data Recovery
    - Windows Reinstall
    - Upgrade (SSD, RAM, GPU, etc.)
    - Custom PC Build
  - Preferred Collection Date
  - Submit: "Send Booking Request"
  - Note: "I'll respond within 24 hours with a rough quote..."

[Sidebar - Right column]
  Card 1: "Not sure what's wrong?"
    Video Diagnosis explanation - book via Cal.com

  Card 2: "What happens next?"
    1. I'll review your request
    2. Reply within 24 hours with a quote
    3. If you approve, I'll arrange courier collection
    4. Repair, test, and return via courier

  Card 3: "Need to talk it through?"
    "Book a free 15-minute video call" → Cal.com
```

### Contact Page (IMPLEMENTED - NEEDS UPDATE)

**Goal**: Multiple ways to get in touch - all digital, no phone.

```
[Page Header]
  - Title: "Contact"
  - Intro: "Got a question? Get in touch. I reply within 24 hours."

[Four contact option cards]
  - Live Chat (highlighted): "Chat now" - Chatwoot widget trigger
  - WhatsApp: "Message on WhatsApp" - wa.me link
  - Email: info@061tech.ie, "Replies within 24 hours"
  - Book a Call: "Schedule a video consultation" → Cal.com

[Contact Form]
  - Name / Email (row)
  - Subject
  - Message
  - Submit: "Send Message"

[Why No Phone?]
  Brief explanation: "I focus on fixing computers, not fielding calls.
  Digital communication means everything is documented, nothing gets lost,
  and you can reach out anytime - even at 2am. I'll respond within 24 hours."

[Service Area section]
  - Limerick city and county with courier
  - Nearby counties possible - ask for quote
  - Remote services: anywhere in Ireland
```

### About Page (IMPLEMENTED)

**Goal**: Humanize the business. Build trust.

```
[Page Header]
  - Title: "About 061 Tech"

[Main content - prose style]
  - Lead: "I'm Adam. I've been working in IT for over 10 years..."
  - Why I started this (convenience, no shop queues)
  - How I work (no upselling, honest, quality parts)
  - What I won't do:
    - Apple/Mac repairs (focus on Windows)
    - Data recovery from encrypted drives
    - Repairs that aren't worth it (I'll tell you)
  - The name: 061 is Limerick's area code

[Values grid - 4 cards]
  - Honest assessments
  - Fair prices
  - Plain English
  - Quality work

[CTA Section]
```

### FAQ Page (IMPLEMENTED)

**Goal**: Answer real questions before they're asked.

```
[Page Header]
  - Title: "Frequently Asked Questions"
  - Intro: "Common questions about how this works, pricing, and what to expect."

[4 Categories with questions]

Booking & Process:
  - How do I book a repair?
  - How long does the whole process take?
  - Do I have to use the courier?
  - What areas do you cover?

Pricing & Payment:
  - How much will my repair cost?
  - What if you can't fix it?
  - When do I pay?
  - How much is the courier?

About the Repair:
  - Is my data safe?
  - What warranty do you offer?
  - What if something goes wrong after you return it?
  - Do you repair Macs/Apple devices?

Not Sure What's Wrong?:
  - I don't know what's wrong with my computer
  - My computer is slow - what do I need?
  - Is it worth repairing or should I buy new?

[CTA Section]
  - "Still have questions?" → Contact Me
```

---

## 7. Component Patterns

### Buttons

> **Note**: Inspired by Gandi's button style - hard offset shadows that create a subtle 3D/pressed effect.

```css
.btn {
  display: inline-block;
  padding: 0.75rem 1.5rem;
  font-size: var(--text-base);
  font-weight: 600;
  text-decoration: none;
  border-radius: 4px;
  cursor: pointer;
  position: relative;
  top: 0;
  transition: top 150ms ease, box-shadow 150ms ease;
}

/* Primary button - amber with dark border/shadow (works in both themes) */
.btn-primary {
  background: var(--accent);
  color: #1c1917;  /* Always dark text on amber for contrast */
  border: 2px solid #92400e;  /* Dark amber border */
  box-shadow: 3px 3px 0 #92400e;  /* Dark amber shadow */
}

.btn-primary:hover {
  top: 2px;
  background: var(--accent-hover);
  box-shadow: 1px 1px 0 #92400e;
}

.btn-primary:active {
  top: 3px;
  box-shadow: 0 0 0 #92400e;
}

/* Secondary button - adapts to theme */
.btn-secondary {
  background: var(--bg-elevated);
  color: var(--text-primary);
  border: 2px solid var(--text-secondary);
  box-shadow: 3px 3px 0 var(--text-secondary);
}

.btn-secondary:hover {
  top: 2px;
  background: var(--bg-secondary);
  box-shadow: 1px 1px 0 var(--text-secondary);
}

.btn-secondary:active {
  top: 3px;
  box-shadow: 0 0 0 var(--text-secondary);
}
```

**Key decisions for dark/light theme compatibility:**
- Primary button uses fixed dark amber (`#92400e`) for border/shadow - works on both backgrounds
- Primary button text is always dark (`#1c1917`) for contrast against amber
- Secondary button uses `--text-secondary` which adapts naturally to each theme
- Hard offset shadow (no blur) creates tactile, 3D feel
- On hover/active, button "presses down" by moving and reducing shadow
- **Important:** Use `a.btn-primary:hover` selectors to override global `a:hover` color rules

### Cards

```css
.card {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  padding: 1.5rem;
  border-radius: 6px;
}

/* No hover effect by default. Cards don't need to glow. */
```

### Price Display (Gandi-style)

> **Inspiration**: Gandi.net uses "From" as a small, muted label stacked above the main price. This looks cleaner than inline "from €X" and builds trust.

```css
/* Price container */
.price {
  display: block;
  font-family: var(--font-mono);
  font-weight: 500;
}

/* "From" label - small caps, muted, stacked above price */
.price-from {
  display: block;
  font-size: var(--text-xs);
  font-weight: 400;
  font-family: var(--font-body);
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.125rem;
}
```

**Usage in templates:**
```astro
<span class="price">
  {item.priceFrom && <span class="price-from">From</span>}
  {item.price}
</span>
```

**Result:**
```
FROM        ← small, muted, uppercase
€60         ← large, prominent, accent color
```

**When to use "From":**
- Services with variable pricing (upgrades, repairs)
- Use `priceFrom: true` in config

**When NOT to use "From":**
- Flat rates (€20 video diagnosis, €30/hr support)
- Use `priceFrom: false` in config

### Tables

```css
table {
  width: 100%;
  border-collapse: collapse;
}

th, td {
  padding: 0.75rem 1rem;
  text-align: left;
  border-bottom: 1px solid var(--border);
}

th {
  font-weight: 600;
  color: var(--text-secondary);
  font-size: var(--text-sm);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

/* Zebra striping optional - only if table is long */
```

### Sticky Quick Jump Navigation

> **Used on**: Services page - allows users to jump between sections without scrolling back up.

```css
.quick-jump-nav {
  position: sticky;
  top: 0;
  z-index: 100;
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border);
  transition: transform 150ms ease, opacity 150ms ease;
}

.quick-jump-nav.hidden {
  transform: translateY(-100%);  /* Slides up out of view */
  opacity: 0;
  pointer-events: none;
}

.quick-jump-nav.scrolled {
  box-shadow: var(--shadow-md);  /* Shadow when sticky */
}

/* Floating show button (appears when nav hidden) */
.quick-jump-show {
  position: fixed;
  top: var(--space-sm);
  right: var(--space-md);
  opacity: 0;
  pointer-events: none;
}

.quick-jump-show.visible {
  opacity: 1;
  pointer-events: auto;
}
```

**Features:**
- **Centered pills** - Gandi-style offset shadow that "presses down" on hover
- **Sticky positioning** - stays at top when scrolling
- **Pull tab dismiss** - small tab at bottom center (TODO: needs redesign)
  - Only appears when nav is sticky (not when static)
  - **FIX NEEDED:** arrow wrong direction, tab looks disconnected from nav
- **Auto-restore** - nav reappears when scrolled back to original position
- **Manual restore** - floating button (top-right) if you want it back early
- **Shadow on scroll** - uses IntersectionObserver (no scroll listener)
- **Mobile-optimised** - smaller pills, reduced shadows

**JavaScript** (~30 lines):
- Tracks `userDismissed` state
- Dismiss: hides nav (slides up), shows floating button
- Show: restores nav, hides floating button
- Auto-restore: when scrolled back up past sentinel, resets dismiss state
- Shadow: IntersectionObserver watches a sentinel element

### Forms

```css
input, textarea, select {
  width: 100%;
  padding: 0.75rem;
  font-size: var(--text-base);
  border: 1px solid var(--text-muted);  /* Use text-muted for dark mode visibility */
  border-radius: 4px;
  background: var(--bg-elevated);
  color: var(--text-primary);
}

input:focus, textarea:focus, select:focus {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
  border-color: var(--accent);
}

label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
}
```

**Note:** Using `--text-muted` instead of `--border` for form field borders ensures visibility in dark mode, where `--border` is too close to `--bg-elevated`.

---

## 8. Security Hardening

### Build-time security (Astro advantage)

- Static HTML = no server-side code execution
- No database connections
- No user sessions on the main site
- Attack surface is minimal

### Headers (configure in Coolify/Nginx)

```nginx
# Security headers
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;

# Content Security Policy
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'self';" always;
```

### CloudFlare settings

- **SSL/TLS**: Full (strict)
- **Always Use HTTPS**: On
- **HSTS**: Enable with long max-age
- **Minimum TLS Version**: 1.2
- **Bot Fight Mode**: On
- **Browser Integrity Check**: On
- **Email Address Obfuscation**: On (protects email in HTML)
- **Hotlink Protection**: On
- **Under Attack Mode**: Available when needed

### Form handling

Options for the booking form (since site is static):
1. **Formspree** - Simple, handles spam, free tier available
2. **Netlify Forms** - If ever hosted there
3. **Custom endpoint** - Small API in Coolify (separate container)
4. **Email link fallback** - `mailto:` always works

Recommendation: Start with Formspree, migrate to custom if volume grows.

### No tracking

- No Google Analytics (use privacy-respecting alternative if needed: Plausible, Umami)
- No Facebook Pixel
- No third-party scripts
- This is a selling point: "We don't track you"

---

## 9. Communication Strategy: No Phone Number

> **Decision**: 061 Tech will not use a traditional phone number for customer contact. Instead, all communication is digital-first, allowing focused work time and full documentation of all customer interactions.

### Why No Phone?

- **Focus**: Can't fix computers while fielding calls
- **Documentation**: Every conversation is recorded and searchable
- **Async-friendly**: Customers can reach out anytime, responses within 24 hours
- **No missed calls**: Everything comes to one inbox
- **Professional**: Modern businesses communicate digitally

### Communication Channels

| Channel | Purpose | Tool |
|---------|---------|------|
| Live Chat | Instant questions on website | Chatwoot widget |
| WhatsApp | Quick messages, photos of issues | Chatwoot WhatsApp integration |
| Email | Formal inquiries, quotes, invoices | Chatwoot unified inbox |
| Video Consultations | Remote diagnosis, complex discussions | Cal.com → Google Meet |
| Booking Forms | Repair requests | Website forms → Chatwoot tickets |

### Chatwoot Setup (Self-Hosted on Coolify)

Chatwoot provides unified inbox for all channels - live chat, WhatsApp, email, and converts everything into trackable tickets.

**Coolify Deployment:**
1. In Coolify dashboard → Create New Resource → One-Click Services → Chatwoot
2. Or deploy via Docker Compose with custom configuration

**System Requirements:**
- Minimum: 2 CPU cores, 4GB RAM, 20GB SSD
- Recommended: 4+ cores, 8GB RAM, 50GB SSD

**Required Services (auto-provisioned by Coolify template):**
- PostgreSQL 12+
- Redis 6+
- Rails web server (port 3000)
- Sidekiq worker (background jobs)

**Essential Environment Variables:**
```bash
# Database
POSTGRES_PASSWORD=<secure-password>
REDIS_PASSWORD=<secure-password>

# Application
SECRET_KEY_BASE=<generate-with-openssl>
FRONTEND_URL=https://chat.061tech.ie
RAILS_ENV=production

# Email (for notifications)
SMTP_ADDRESS=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_DOMAIN=061tech.ie
MAILER_SENDER_EMAIL=support@061tech.ie

# WhatsApp Business API (optional, configure later)
# Requires WhatsApp Business account and API access
```

**Post-Deployment Setup:**
1. Access Chatwoot at configured domain (e.g., `chat.061tech.ie`)
2. Create admin account
3. Add Website inbox → Get embed code for live chat widget
4. Add Email inbox → Configure SMTP/IMAP
5. Add WhatsApp channel (requires WhatsApp Business API)

**Website Widget Integration:**
```html
<!-- Add before </body> in Base.astro -->
<script>
  window.chatwootSettings = {
    position: "right",
    type: "standard",
    launcherTitle: "Chat with us"
  };
  (function(d,t) {
    var BASE_URL="https://chat.061tech.ie";
    var g=d.createElement(t),s=d.getElementsByTagName(t)[0];
    g.src=BASE_URL+"/packs/js/sdk.js";
    g.defer=true;
    g.async=true;
    s.parentNode.insertBefore(g,s);
    g.onload=function(){
      window.chatwootSDK.run({
        websiteToken: '<your-website-token>',
        baseUrl: BASE_URL
      })
    }
  })(document,"script");
</script>
```

### Cal.com Setup (Self-Hosted on Coolify)

Cal.com handles consultation booking with automatic Google Meet link generation.

**Coolify Deployment:**
1. In Coolify dashboard → Create New Resource → One-Click Services → Cal.com
2. Important: For x86/amd64 servers, specify platform in docker-compose:
   ```yaml
   services:
     calcom:
       image: 'calcom/cal.com:latest'
       platform: linux/amd64
   ```

**Required Environment Variables:**
```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/calcom

# Authentication (generate both with: openssl rand -base64 32)
NEXTAUTH_SECRET=<generated-secret>
CALENDSO_ENCRYPTION_KEY=<generated-key>

# URLs
NEXTAUTH_URL=https://book.061tech.ie
NEXT_PUBLIC_WEBAPP_URL=https://book.061tech.ie

# Google Calendar Integration
GOOGLE_API_CREDENTIALS=<oauth-credentials-json>

# Email
EMAIL_FROM=bookings@061tech.ie
EMAIL_SERVER_HOST=smtp.example.com
EMAIL_SERVER_PORT=587
EMAIL_SERVER_USER=
EMAIL_SERVER_PASSWORD=
```

**Post-Deployment Setup:**
1. Access Cal.com at configured domain (e.g., `book.061tech.ie`)
2. Create admin account
3. Connect Google Calendar
4. Create event types:
   - "Free 15-min Chat" (quick questions)
   - "Remote Diagnosis" (€20, 30 mins, Google Meet)
   - "Consultation Call" (complex issues, 45 mins)
5. Configure booking page appearance
6. Get embed code or booking link

**Website Integration Options:**

Option A - Link button:
```html
<a href="https://book.061tech.ie/adam" class="btn btn-secondary">
  Book a Consultation
</a>
```

Option B - Embed inline:
```html
<div id="cal-embed"></div>
<script>
  (function (C, A, L) {
    let p = function (a, ar) { a.q.push(ar); };
    let d = C.document;
    C.Cal = C.Cal || function () {
      let cal = C.Cal;
      let ar = arguments;
      if (!cal.loaded) {
        cal.ns = {}; cal.q = cal.q || [];
        d.head.appendChild(d.createElement("script")).src = A;
        cal.loaded = true;
      }
      if (ar[0] === L) { const api = function () { p(api, arguments); }; const namespace = ar[1]; api.q = api.q || []; typeof namespace === "string" ? (cal.ns[namespace] = api) && p(api, ar) : p(cal, ar); return; }
      p(cal, ar);
    };
  })(window, "https://book.061tech.ie/embed/embed.js", "init");
  Cal("init");
  Cal("inline", { elementOrSelector: "#cal-embed", calLink: "adam" });
</script>
```

### Subdomains Configuration

| Subdomain | Service | Port |
|-----------|---------|------|
| `061tech.ie` | Main website (Astro) | 80/443 |
| `chat.061tech.ie` | Chatwoot | 3000 |
| `book.061tech.ie` | Cal.com | 3000 |

Configure all three in Coolify with SSL via Let's Encrypt.

### Updated Contact Methods (Website Copy)

**Instead of phone number, display:**
- 💬 **Live Chat** - "Chat with me directly" (bottom-right widget)
- 📱 **WhatsApp** - wa.me link with pre-filled message
- 📧 **Email** - hello@061tech.ie
- 📅 **Book a Call** - "Schedule a video consultation" → Cal.com

**WhatsApp Link Format:**
```
https://wa.me/353XXXXXXXXX?text=Hi%2C%20I%20need%20help%20with%20my%20computer
```
(Use personal WhatsApp Business number when ready, or omit number for WhatsApp-less link)

---

## 10. Deployment: Coolify Setup (Main Website)

### Repository structure

```
.
├── src/
├── public/
├── astro.config.mjs
├── package.json
├── Dockerfile          # Optional, Nixpacks handles Astro
└── .env.example
```

### Coolify configuration

1. Create new Application in Coolify
2. Connect to GitHub/GitLab repository
3. Build Pack: **Nixpacks** (auto-detects Astro)
4. Build Command: `npm run build`
5. Output Directory: `dist`
6. Static Site: **Yes**

### Environment variables

```
PUBLIC_SITE_URL=https://061tech.ie
PUBLIC_CONTACT_EMAIL=hello@061tech.ie
PUBLIC_CONTACT_PHONE=061-XXX-XXXX
# Form handling
PUBLIC_FORM_ENDPOINT=https://formspree.io/f/xxxxx
```

### Domain setup

1. Add domain in Coolify: `061tech.ie`, `www.061tech.ie`
2. Point DNS to Coolify server (or CloudFlare if proxied)
3. If using CloudFlare:
   - Proxy enabled (orange cloud)
   - SSL: Full (strict)
   - Create origin certificate in CloudFlare, install in Coolify

### CI/CD

Coolify handles this automatically:
- Push to main → Coolify rebuilds → Deploys
- Zero-downtime deployments
- Rollback available if needed

---

## 11. Content Guidelines

### Voice and Tone

- **Direct**: Say what you mean. No corporate fluff.
- **Confident**: You know what you're doing. It shows.
- **Honest**: If something is uncertain, say so.
- **Local**: You're from Limerick. Sound like it (slightly).
- **Not salesy**: Information, not persuasion.

### Examples

**Bad (AI-speak):**
> "At 061 Tech, we're passionate about providing innovative solutions for all your technology needs. Our dedicated team of experts is here to help you navigate the complex world of computer repair."

**Good (human):**
> "Your laptop's broken. You don't want to drive across town and wait in a queue. I get it. So I'll send a courier to pick it up, I'll fix it, and you'll get it back. Simple."

**Bad:**
> "Get Started Today!"

**Good:**
> "Book a Repair"

**Bad:**
> "We leverage cutting-edge diagnostic tools..."

**Good:**
> "I run full hardware diagnostics before quoting. No guessing."

### Photography

- No stock photos
- If using images: real photos of your workspace, tools, the local area
- No images is better than fake images
- Icons sparingly, only when they genuinely help (e.g., phone icon next to number)

---

## 12. Implementation Phases

### Phase 1: Foundation ✅ COMPLETE
- [ ] Register domain (061tech.ie) ← **PENDING**
- [x] Set up Astro project with base structure
- [x] Implement colour system and typography
- [x] Create Header, Footer, Base layout components
- [x] Build Homepage with placeholder content
- [ ] Deploy to Coolify ← **PENDING**
- [ ] Configure CloudFlare ← **PENDING**

### Phase 2: Core Pages ✅ COMPLETE
- [x] Services page with full pricing tables
- [x] How It Works page
- [x] About page
- [x] Contact page with form (Formspree integration ready)
- [x] FAQ page

### Phase 3: Booking System ✅ COMPLETE
- [x] Book page with form
- [x] Form validation (HTML5 native)
- [ ] Confirmation page/message ← Optional
- [ ] Email notifications working ← **NEEDS FORMSPREE SETUP**

### Phase 4: Polish ✅ COMPLETE
- [x] Dark/light theme toggle (defaults to light)
- [x] Mobile navigation (responsive)
- [x] SEO meta tags for all pages (competitor analysis, keywords optimized)
- [x] Open Graph images (1200x630 + square, Gandi-style with offset shadows)
- [x] 404 page (with Limerick slang: "Story bud?")
- [x] Favicon and app icons (SVG + ICO + apple-touch-icon)
- [x] FAQ schema markup for Google rich results
- [x] LocalBusiness JSON-LD with services, knowsAbout array
- [x] AI fingerprint removal (source code looks human-written)
- [x] CLAUDE.md project documentation for AI assistants

### Phase 5: Communication Infrastructure
- [ ] Deploy Chatwoot to Coolify (chat.061tech.ie)
- [ ] Deploy Cal.com to Coolify (book.061tech.ie)
- [ ] Configure Chatwoot inbox and widget
- [ ] Configure Cal.com event types (Free 15-min, Video Diagnosis €20)
- [ ] Connect Cal.com to Google Calendar + Meet
- [ ] Add Chatwoot widget to website
- [ ] Update website pages to remove phone, add new contact methods
- [ ] Set up WhatsApp Business link

### Phase 6: Pre-launch
- [x] Real content and pricing (structure complete, needs final review)
- [x] Remove phone number placeholders (digital-first approach)
- [ ] Set up Formspree and add form IDs
- [ ] Test all forms
- [ ] Security audit (headers, CSP)
- [ ] Performance audit (Lighthouse)
- [ ] Accessibility check
- [ ] Test on real devices

### Phase 7: Launch
- [ ] Go live
- [ ] Google Business Profile
- [ ] Local directory listings
- [ ] Monitor for issues

---

## 13. Resources

### Astro
- [Astro Docs](https://docs.astro.build)
- [Astro + Coolify](https://coolify.io/docs/builds/packs/static)

### Design reference (sites that don't look AI-generated)
- [Linear](https://linear.app) - Clean, functional, fast
- [Basecamp](https://basecamp.com) - Direct, personality
- [Stripe](https://stripe.com) - Dense information, well organized
- [gov.uk](https://gov.uk) - Brutally clear, no nonsense

### Colour tools
- [Realtime Colors](https://realtimecolors.com) - Test palettes on real layouts
- [Contrast checker](https://webaim.org/resources/contrastchecker/)

### Performance
- [PageSpeed Insights](https://pagespeed.web.dev)
- [WebPageTest](https://webpagetest.org)

---

## Summary

You're building a website for a real business that solves a real problem. The website should reflect that: clear, fast, honest, and functional.

The anti-AI approach isn't about being different for its own sake. It's about building something that feels crafted, trustworthy, and genuinely useful. Template sites all look the same because they're optimized for the template seller, not the end user.

**Key principles:**
1. Information over decoration
2. Speed over fancy
3. Honest over salesy
4. Functional over trendy
5. Human over polished

When in doubt, ask: "Would a real person actually find this useful?" If yes, keep it. If no, cut it.

---

*Kickstart created: January 2026*
*Ready for implementation*

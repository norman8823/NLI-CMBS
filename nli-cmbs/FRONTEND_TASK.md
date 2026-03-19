Build the NLI-CMBS React frontend dashboard. This is the primary UI for the CMBS portfolio intelligence tool. The dashboard has 5 tabs: Overview, Property, Credit, Maturities, Loans.

STACK:
- React 18 + TypeScript + Vite
- Tailwind CSS + shadcn/ui components
- Chart.js for charts (already in package.json)
- React Router for navigation (already configured)
- API calls to FastAPI backend at /api/v1

PROJECT CONTEXT:
- Frontend already scaffolded at frontend/ directory
- Backend running on port 8000, frontend dev server on port 5173
- API endpoints exist: GET /api/v1/deals, GET /api/v1/deals/{ticker}, GET /api/v1/deals/{ticker}/loans, GET /api/v1/deals/{ticker}/report
- Docker Compose runs both services

TAB 1: OVERVIEW

Layout:
- Deal header: ticker (large), trust name, filing date, EDGAR link
- 8 metric cards in 2 rows of 4:
  Row 1: Current UPB (with orig below), Loan count (defeased below), WA coupon (vs orig), WA DSCR (vs orig)
  Row 2: Delinquency rate (balance + count), Specially serviced pct (balance + count), WA LTV (vs orig), IO loans pct (balance + count)
- Top 10 loans table: Property, Type (badge), Location, Balance, pct pool, Status (badge)
- Generate AI report button calls /api/v1/deals/{ticker}/report

Color coding:
- Delinquency rate, SS pct: red text if greater than 5 pct
- DSCR: red if less than 1.25x
- Status badges: Current=green, 30-day=amber, 60-day=orange, 90+=red, SS=red

TAB 2: PROPERTY

Layout:
- Two side-by-side charts:
  Left: Donut chart by property type (Office, Retail, Multifamily, Industrial, Hotel)
  Right: Horizontal bar chart by state (top 7 states)
- Property selector dropdown (list all properties from API)
- Conditional loan context banner (only show if property_count > 1):
  - Translucent gray background: rgba(128,128,128,0.08)
  - Text: Part of [Loan Name] - N properties - $XM total
  - Link: View all properties
  - NO emoji, NO maturity date
- Property header card: name, location, type badge, SF, year built
- 4 metric cards: Appraised value (with date), NOI (with YoY trend), Occupancy (with YoY trend), Year renovated
- Top 3 tenants table: rank, tenant name, SF, pct NRA, lease expiration with visual bar
  - Bar color: green if greater than 2 years, amber if less than 2 years
  - Show X.X yrs remaining
- Performance history table: Period, NOI, delta, Occupancy, delta

IMPORTANT - Property tab shows ONLY property-level data:
- YES: NOI, occupancy, appraised value, tenants, SF, year built
- NO: Balance, LTV, DSCR, rate, maturity (these are loan-level, stay on Loans tab)

TAB 3: CREDIT

Layout:
- 4 metric cards: Current pct (green), 30-59 days pct, 60-89 days pct (amber), 90+ days pct (red)
  Each shows balance and loan count below
- Delinquency trend line chart (12 months): 3 lines for 30-day, 60-day, 90+ buckets
- Section: Delinquent loans
  Definition subtitle (italic): Loans 30+ days past due on scheduled payments
  Table: Property (with location + type below), Balance, Status badge, Days DQ, DSCR, In SS? (Yes/No)
- Section: Specially serviced loans
  Definition subtitle: Loans transferred to special servicer for workout due to default, imminent default, or maturity default
  Summary bar: SS loans count, SS balance pct, Total advances, Avg time in SS
  Table: Property, Balance, Workout strategy (tags), Servicer, Advances, Time in SS
  - If loan is modified (is_modified=true): show Modified badge inline
  - Show modification details in expanded sub-row below the loan row
  - Sub-row format: Modification (date): Rate: old to new, Maturity: old to new etc.
- Section: Modified loans (performing)
  Definition subtitle: Performing loans with restructured terms, currently with master servicer
  Summary bar: count, balance, principal forgiven, principal deferred
  Table: Property, Balance, Mod date, Modification type (tags), Changed terms
  - Changed terms show strikethrough old to new values

Modification tags (use neutral gray badges):
- Rate reduction, Term extension, Principal forgiveness, Principal deferral, A/B split, Forbearance

TAB 4: MATURITIES

Layout:
- 4 metric cards: Maturing 0-12mo (balance + count + pct), Maturing 13-24mo, WA in-place rate (Fixed vs Floating breakdown), DSCR less than 1.25x maturing (amber)
- Maturity wall stacked bar chart: X-axis = quarters, Y-axis = $M, stacked by property type
- Section: Maturing loans (next 24 months)
  Definition subtitle: Sorted by maturity date
  Table columns: Property, Type badge, Balance, Rate type (Fixed/Floating badge + IO badge if applicable), In-place rate (show spread for floating: S+250), DSCR, Maturity date, Months to maturity

Months badge colors:
- 3 months or less: red background
- 4-6 months: amber background
- 7+ months: gray background
- Matured (negative months): red Matured badge

NO refi assumptions, NO rate gap, NO estimated refi DSCR. Keep it factual.

TAB 5: LOANS

Layout:
- Count display: X loans (updates with filters)
- Full loan table with Excel-style per-column sort + filter
- Columns: Properties, Type, Location, Balance, Orig bal, Rate, IO, DSCR, LTV, Status, Orig, Maturity

Column behaviors:
- All columns sortable (click header to toggle asc/desc)
- Type column: dropdown filter with checkboxes (Office, Retail, Multifamily, Industrial, Hotel)
- Status column: dropdown filter with checkboxes (Current, 30-day, 60-day, 90+, SS)
- Properties column: show property name for single-property loans, ABC Portfolio (4) for multi-property loans (property_count > 1)

NO occupancy column (that is property-level, not loan-level)

Color coding:
- DSCR less than 1.25x: red text
- LTV greater than 75 pct: amber text
- Status badges: same colors as Overview tab

COMPONENT STRUCTURE

frontend/src/
  components/
    DealHeader.tsx - Ticker, trust name, filing date, EDGAR link
    MetricCard.tsx - Reusable metric card component
    DataTable.tsx - Reusable sortable/filterable table
    Badge.tsx - Status/type badges with color variants
    charts/
      DonutChart.tsx - Property type distribution
      BarChart.tsx - State distribution, maturity wall
      LineChart.tsx - Delinquency trend
    tabs/
      OverviewTab.tsx
      PropertyTab.tsx
      CreditTab.tsx
      MaturitiesTab.tsx
      LoansTab.tsx
  pages/
    DealDashboard.tsx - Main dashboard with tab navigation
  hooks/
    useDeal.ts - Fetch deal summary
    useLoans.ts - Fetch loans for a deal
    useReport.ts - Generate AI report
  types/
    index.ts - TypeScript interfaces for Deal, Loan, Property, etc.
  lib/
    api.ts - API client functions

API INTEGRATION

Base URL: /api/v1 (proxied in vite.config.ts)

Endpoints to use:
- GET /deals - list deals for search/autocomplete
- GET /deals/{ticker} - deal summary metrics
- GET /deals/{ticker}/loans - all loans with snapshots
- GET /deals/{ticker}/report - AI surveillance report (may take 10-15 seconds)

Handle loading states:
- Show skeleton loaders while fetching
- Show Generating report spinner for AI report (it is slow)
- Show error states with retry button

STYLING GUIDELINES

Aesthetic: Institutional, dense, professional. NOT startup/consumer app.
- Neutral colors, minimal decoration
- Dense information display
- No animations except loading spinners
- Typography: clean, readable, no playful fonts

Colors (use CSS variables or Tailwind):
- Office badge: blue (E6F1FB bg, 0C447C text)
- Retail badge: green (E1F5EE bg, 085041 text)
- Multifamily badge: orange (FAECE7 bg, 712B13 text)
- Industrial badge: purple (EEEDFE bg, 3C3489 text)
- Hotel badge: pink (FBEAF0 bg, 72243E text)
- Current status: green
- 30-day: amber
- 60-day: orange
- 90+/SS: red
- Modification tags: neutral gray

VERIFICATION STEPS (run these yourself)

1. Frontend dev server starts: cd frontend and npm run dev
2. No TypeScript errors: npm run type-check (or tsc --noEmit)
3. No ESLint errors: npm run lint
4. Dashboard loads at http://localhost:5173/deals/JPMCC-2016-JP4
5. All 5 tabs render without console errors
6. Overview tab: 8 metric cards display, top 10 table renders
7. Property tab: both charts render, property selector works, tenant table shows
8. Credit tab: delinquency trend chart renders, all 3 tables (delinquent, SS, modified) render
9. Maturities tab: maturity wall chart renders, maturing loans table shows with month badges
10. Loans tab: table renders, column sorting works (click Balance header), type filter dropdown works
11. Generate AI report button calls API and displays report (may show loading for 10-15s)

SUCCESS CRITERIA

When ALL of these pass, output FRONTEND_DONE:

- npm run dev starts without errors
- npm run type-check passes (no TS errors)
- npm run lint passes (no ESLint errors)
- All 5 tabs render with mock or real data
- Charts render (donut, bar, line, stacked bar)
- Tables are sortable (click header toggles sort)
- Type and Status filter dropdowns work on Loans tab
- Metric cards display with correct color coding
- Badges render with correct colors for each type/status
- Property tab shows loan context banner only for portfolio loans (property_count > 1)
- Credit tab shows modification details in sub-rows for modified SS loans
- Maturities tab shows months badges with correct urgency colors
- No console errors on any tab
- API calls to /api/v1/deals/{ticker} work (or gracefully handle if backend not running)

If stuck after 20 iterations with no progress, write blockers to BLOCKERS.md and output FRONTEND_DONE.

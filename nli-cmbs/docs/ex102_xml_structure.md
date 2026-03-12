# EX-102 XML Structure Reconnaissance Report

Analyzed from real ABS-EE EX-102 filings downloaded from SEC EDGAR on 2026-03-12.

## Source Files

| File | Deal | Depositor | Filing Date | Size | Loans |
|------|------|-----------|-------------|------|-------|
| `tests/fixtures/ex102_bmark_2024_v6.xml` | BMARK 2024-V6 | Deutsche Mortgage & Asset Receiving Corp (CIK 1013454) | 2026-02-18 | 509,544 bytes | 129 |
| `tests/fixtures/ex102_bank5_second_deal.xml` | BANK5 (Morgan Stanley, CIK 1547361) | Morgan Stanley Capital I Inc. | 2025-12-04 | 368,680 bytes | 94 |

## A. Root Element

```xml
<?xml version="1.0" encoding="UTF-8"?>
<assetData xmlns="http://www.sec.gov/edgar/document/absee/cmbs/assetdata"
           xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
```

- **Root tag:** `assetData`
- **Default namespace:** `http://www.sec.gov/edgar/document/absee/cmbs/assetdata`
- **Additional namespace:** `xsi` = `http://www.w3.org/2001/XMLSchema-instance`

## B. Loan Container

Each loan/asset is wrapped in an `<assets>` element, direct child of `<assetData>`.

```
assetData (root)
 └── assets (one per loan, repeats N times)
      ├── [loan-level fields]
      └── property (nested sub-element, one per property)
           └── [property-level fields]
```

**XPath to iterate loans:** `/assetData/assets` (with namespace)

## C. Field Mapping

All elements use the default namespace `http://www.sec.gov/edgar/document/absee/cmbs/assetdata`.
XPaths below are relative to each `<assets>` element.

### Loan Identity

| Target Field | XML Element | XPath | Sample Value (BMARK) |
|---|---|---|---|
| prospectus_loan_id | `assetTypeNumber` | `./assetTypeNumber` | `Prospectus Loan ID` (label, not ID) |
| asset_number | `assetNumber` | `./assetNumber` | `1` |
| originator | `originatorName` | `./originatorName` | `German American Capital Corporation` |
| original_amount | `originalLoanAmount` | `./originalLoanAmount` | `70000000.00` |
| origination_date | `originationDate` | `./originationDate` | `02-11-2026` |

**Note:** `assetTypeNumber` contains the string `"Prospectus Loan ID"` as a label — it is NOT the actual loan ID value. The actual prospectus loan ID appears to be the `assetNumber` field itself. There is no separate prospectus-specific ID field in either file.

### Property (nested under `./property`)

| Target Field | XML Element | XPath | Sample Value |
|---|---|---|---|
| property_name | `propertyName` | `./property/propertyName` | `215 Park Avenue South` |
| property_city | `propertyCity` | `./property/propertyCity` | `New York` |
| property_state | `propertyState` | `./property/propertyState` | `NY` |
| property_type | `propertyTypeCode` | `./property/propertyTypeCode` | `OF` (Office) |
| property_address | `propertyAddress` | `./property/propertyAddress` | `215 Park Avenue South` |
| property_zip | `propertyZip` | `./property/propertyZip` | `10003` |
| property_county | `propertyCounty` | `./property/propertyCounty` | `New York` |

**Property type codes observed:** `OF` (Office), `RT` (Retail), `MF` (Multifamily), `IN` (Industrial), `MU` (Mixed Use), `LO` (Lodging), `SS` (Self Storage), `MH` (Manufactured Housing)

### Borrower / Obligor

**No borrower or obligor fields exist** in either XML file. The EX-102 CMBS schema does not include borrower name data. The closest identifier is `originatorName` (the loan originator, not the borrower).

### Current Status / Reporting Period

| Target Field | XML Element | XPath | Sample Value |
|---|---|---|---|
| reporting_period_begin | `reportingPeriodBeginningDate` | `./reportingPeriodBeginningDate` | `02-12-2026` |
| reporting_period_end | `reportingPeriodEndDate` | `./reportingPeriodEndDate` | `03-11-2026` |
| beginning_balance | `reportPeriodBeginningScheduleLoanBalanceAmount` | `./reportPeriodBeginningScheduleLoanBalanceAmount` | `70000000.00` |
| ending_balance | `reportPeriodEndScheduledLoanBalanceAmount` | `./reportPeriodEndScheduledLoanBalanceAmount` | `70000000.00` |
| ending_actual_balance | `reportPeriodEndActualBalanceAmount` | `./reportPeriodEndActualBalanceAmount` | `70000000.00` |
| current_rate | `reportPeriodInterestRatePercentage` | `./reportPeriodInterestRatePercentage` | `0.06055000` |
| delinquency_status | `paymentStatusLoanCode` | `./paymentStatusLoanCode` | `A` (current) or `0` |
| interest_paid_through_date | `paidThroughDate` | `./paidThroughDate` | `03-06-2026` |
| servicer_advanced_amount | `totalPrincipalInterestAdvancedOutstandingAmount` | `./totalPrincipalInterestAdvancedOutstandingAmount` | `0.00` |
| servicer_name | `primaryServicerName` | `./primaryServicerName` | `Midland` |

### Maturity / Terms

| Target Field | XML Element | XPath | Sample Value |
|---|---|---|---|
| maturity_date | `maturityDate` | `./maturityDate` | `03-06-2036` |
| original_term | `originalTermLoanNumber` | `./originalTermLoanNumber` | `120` |
| original_amort_term | `originalAmortizationTermNumber` | `./originalAmortizationTermNumber` | `0` (interest-only) |
| original_rate | `originalInterestRatePercentage` | `./originalInterestRatePercentage` | `0.06055000` |

### Payment

| Target Field | XML Element | XPath | Sample Value |
|---|---|---|---|
| scheduled_interest | `scheduledInterestAmount` | `./scheduledInterestAmount` | `0.00` |
| scheduled_principal | `scheduledPrincipalAmount` | `./scheduledPrincipalAmount` | `0.00` |
| total_scheduled_p_and_i | `totalScheduledPrincipalInterestDueAmount` | `./totalScheduledPrincipalInterestDueAmount` | `0.00` |
| unscheduled_principal | `unscheduledPrincipalCollectedAmount` | `./unscheduledPrincipalCollectedAmount` | `0.00` |
| other_interest_adj | `otherInterestAdjustmentAmount` | `./otherInterestAdjustmentAmount` | `0.00` |
| other_principal_adj | `otherPrincipalAdjustmentAmount` | `./otherPrincipalAdjustmentAmount` | `0.00` |

**Note:** There are no separate `actual_interest_collected` or `actual_principal_collected` elements. The scheduled amounts appear to serve as actuals in this schema. The `unscheduledPrincipalCollectedAmount` captures prepayments.

## D. Namespace Handling

- **All elements use a default (unprefixed) namespace:** `http://www.sec.gov/edgar/document/absee/cmbs/assetdata`
- **No element prefixes** — elements are like `<assetNumber>` not `<abs-ee:assetNumber>`
- **Parser must register the default namespace** when using XPath:
  ```python
  NS = {"ns": "http://www.sec.gov/edgar/document/absee/cmbs/assetdata"}
  root.findall(".//ns:assets", NS)
  ```
  Or use lxml's `{namespace}element` syntax:
  ```python
  root.findall("{http://www.sec.gov/edgar/document/absee/cmbs/assetdata}assets")
  ```

**IMPORTANT:** The existing `xml_parser.py` uses namespace `http://xbrl.sec.gov/abs-ee/2024` — this is WRONG. The real namespace is `http://www.sec.gov/edgar/document/absee/cmbs/assetdata`.

## E. Data Types

| Type | Format | Examples |
|---|---|---|
| Dates | `MM-DD-YYYY` | `02-11-2026`, `03-06-2036` |
| Amounts | Decimal with 2 decimal places | `70000000.00`, `24315974.96` |
| Rates | Decimal (NOT percentage) | `0.06055000` (= 6.055%) |
| Percentages | Decimal | `0.899` (= 89.9% occupancy) |
| Integers | Plain integer | `120`, `1`, `0` |
| Booleans | `true` / `false` (lowercase) | `true`, `false` |
| Codes | Short string codes | `OF`, `RT`, `A`, `PP` |
| Null/empty | Element absent (not present in XML) | — |

**Date format note:** Dates are `MM-DD-YYYY`, NOT ISO 8601. Parser must convert with `strptime("%m-%d-%Y")`.

## F. Differences Between BMARK and BANK5 XML

### Structural (both issuers use identical schema)

Both files share the same root element, namespace, and `<assets>` container pattern.

### Element Differences

| Element | BMARK | BANK5 |
|---|---|---|
| `GroupID` | Present (values: `0`, `1`, `2`) | **Absent** |
| `assetAddedIndicator` | Present | **Absent** |
| `hyperAmortizingDate` | Present (on some loans) | **Absent** |
| `realizedLossToTrustAmount` | **Absent** | Present |
| `workoutStrategyCode` | **Absent** | Present |
| `valuationSecuritizationDate` (property) | Present | Present on some, absent on others |
| `mostRecentPhysicalOccupancyPercentage` | **Absent** | Present |
| `mostRecentRevenueAmount` | **Absent** | Present |
| `operatingExpensesAmount` | **Absent** | Present |
| `mostRecentNetOperatingIncomeAmount` | **Absent** | Present |
| `mostRecentNetCashFlowAmount` | **Absent** | Present |
| `mostRecentDebtServiceAmount` | **Absent** | Present |
| `mostRecentDebtServiceCoverageCode` | **Absent** | Present |
| `mostRecentDebtServiceCoverageNetOperatingIncomePercentage` | **Absent** | Present |
| `mostRecentDebtServiceCoverageNetCashFlowpercentage` | **Absent** | Present |
| `mostRecentFinancialsStartDate` | **Absent** | Present |
| `mostRecentFinancialsEndDate` | **Absent** | Present |

### Data Differences

| Aspect | BMARK | BANK5 |
|---|---|---|
| `paymentStatusLoanCode` values | `A` (alphabetic) | `0` (numeric) |
| `originatorName` style | Full name (`German American Capital Corporation`) | Abbreviated (`JPMCB`) |
| Property type codes | `OF`, `MF`, `RT`, `IN`, `MU`, `LO` | `RT`, `OF`, `MF`, `IN`, `MU`, `SS`, `MH` |

### Implications for Parser

1. **Must handle optional elements** — use `.find()` with None checks, not `.text` directly
2. **`GroupID` is optional** — only BMARK includes it (used for loan groups / pari passu)
3. **`paymentStatusLoanCode`** has inconsistent types across issuers — treat as string
4. **BANK5 includes "mostRecent" financial fields** that BMARK omits — these are periodic updates vs. securitization-time data
5. **`realizedLossToTrustAmount` and `workoutStrategyCode`** appear only for deals with distressed loans

## G. Total Loan Count

| Deal | Loan Count |
|---|---|
| BMARK 2024-V6 | **129** |
| BANK5 (Morgan Stanley) | **94** |

## Complete Element Inventory

### Asset-Level Elements (union of both files, 60 unique)

```
NumberProperties
NumberPropertiesSecuritization
GroupID                                          # BMARK only
assetAddedIndicator                              # BMARK only
assetNumber
assetSubjectDemandIndicator
assetTypeNumber
balloonIndicator
firstLoanPaymentDueDate
graceDaysAllowedNumber
hyperAmortizingDate                              # BMARK only, rare
interestAccrualMethodCode
interestOnlyIndicator
interestRateSecuritizationPercentage
lienPositionSecuritizationCode
loanStructureCode
maturityDate
modifiedIndicator
negativeAmortizationIndicator
nonRecoverabilityIndicator
originalAmortizationTermNumber
originalInterestOnlyTermNumber
originalInterestRatePercentage
originalInterestRateTypeCode
originalLoanAmount
originalTermLoanNumber
originationDate
originatorName
otherExpensesAdvancedOutstandingAmount
otherInterestAdjustmentAmount
otherPrincipalAdjustmentAmount
paidThroughDate
paymentFrequencyCode
paymentStatusLoanCode
paymentTypeCode
periodicPrincipalAndInterestPaymentSecuritizationAmount
prepaymentLockOutEndDate
prepaymentPremiumIndicator
prepaymentPremiumsEndDate
primaryServicerName
property                                         # nested element
realizedLossToTrustAmount                        # BANK5 only
reportPeriodBeginningScheduleLoanBalanceAmount
reportPeriodEndActualBalanceAmount
reportPeriodEndScheduledLoanBalanceAmount
reportPeriodInterestRatePercentage
reportPeriodModificationIndicator
reportingPeriodBeginningDate
reportingPeriodEndDate
scheduledInterestAmount
scheduledPrincipalAmount
scheduledPrincipalBalanceSecuritizationAmount
servicerTrusteeFeeRatePercentage
servicingAdvanceMethodCode
totalPrincipalInterestAdvancedOutstandingAmount
totalScheduledPrincipalInterestDueAmount
totalTaxesInsuranceAdvancesOutstandingAmount
underwritingIndicator
unscheduledPrincipalCollectedAmount
workoutStrategyCode                              # BANK5 only
yieldMaintenanceEndDate
```

### Property-Level Elements (union of both files, 51 unique)

```
DefeasedStatusCode
debtServiceCoverageNetCashFlowSecuritizationPercentage
debtServiceCoverageNetOperatingIncomeSecuritizationPercentage
debtServiceCoverageSecuritizationCode
defeasanceOptionStartDate
financialsSecuritizationDate
largestTenant
leaseExpirationLargestTenantDate
leaseExpirationSecondLargestTenantDate
leaseExpirationThirdLargestTenantDate
mostRecentAnnualLeaseRolloverReviewDate
mostRecentDebtServiceAmount                      # BANK5 only
mostRecentDebtServiceCoverageCode                # BANK5 only
mostRecentDebtServiceCoverageNetCashFlowpercentage    # BANK5 only
mostRecentDebtServiceCoverageNetOperatingIncomePercentage  # BANK5 only
mostRecentFinancialsEndDate                      # BANK5 only
mostRecentFinancialsStartDate                    # BANK5 only
mostRecentNetCashFlowAmount                      # BANK5 only
mostRecentNetOperatingIncomeAmount               # BANK5 only
mostRecentPhysicalOccupancyPercentage            # BANK5 only
mostRecentRevenueAmount                          # BANK5 only
netCashFlowFlowSecuritizationAmount
netOperatingIncomeNetCashFlowCode
netOperatingIncomeNetCashFlowSecuritizationCode
netOperatingIncomeSecuritizationAmount
netRentableSquareFeetNumber
netRentableSquareFeetSecuritizationNumber
operatingExpensesAmount                          # BANK5 only
operatingExpensesSecuritizationAmount
physicalOccupancySecuritizationPercentage
propertyAddress
propertyCity
propertyCounty
propertyName
propertyState
propertyStatusCode
propertyTypeCode
propertyZip
revenueSecuritizationAmount
secondLargestTenant
squareFeetLargestTenantNumber
squareFeetSecondLargestTenantNumber
squareFeetThirdLargestTenantNumber
thirdLargestTenant
unitsBedsRoomsNumber
unitsBedsRoomsSecuritizationNumber
valuationSecuritizationAmount
valuationSecuritizationDate
valuationSourceSecuritizationCode
yearBuiltNumber
yearLastRenovated
```

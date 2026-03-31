# Skill: Credit Transaction System with Expiration Logic

## Summary
A comprehensive credit-based billing system that manages user credit balances through purchases, consumption, and automatic monthly refreshes. The system tracks credit transactions with expiration dates, enforces time-based credit expiry, and provides UI components for purchasing credit packages via Stripe, viewing transaction history with expiration status, and monitoring current balances. Credits automatically expire after a configured timeframe (CREDITS_EXPIRATION_YEARS), and users receive automatic monthly credit refreshes (FREE_MONTHLY_CREDITS) tracked via lastCreditRefreshAt timestamps.

## Key Components

**Database Schema (Drizzle ORM)**
- `creditTransactionTable` - Core transaction ledger with fields: `id`, `userId`, `amount`, `remainingAmount`, `type` (PURCHASE/USAGE/MONTHLY_REFRESH), `description`, `paymentIntentId` (Stripe), `expirationDate`, `expirationDateProcessedAt`, `createdAt`
- `userTable` - User credit state with `currentCredits` (balance) and `lastCreditRefreshAt` (monthly refresh tracking)
- `CREDIT_TRANSACTION_TYPE` - Enum constant defining transaction categories: MONTHLY_REFRESH, PURCHASE, USAGE, REFUND
- `creditTransactionRelations` - Drizzle relations linking transactions to users

**Business Logic Utilities**
- `isTransactionExpired(transaction)` - Boolean check comparing current date against `transaction.expirationDate`
- `shouldRefreshCredits(session, user)` - Determines if monthly free credits should be granted based on `lastCreditRefreshAt`
- `purchaseAction` - Server action handling Stripe payment intent creation and pending transaction records
- `confirmPurchaseAction` - Validates Stripe payment success and finalizes credit allocation

**UI Components**
- `TransactionHistory` - DataTable component displaying transaction logs with columns: type (Badge), amount (color-coded +/-/), remainingAmount (with expired Badge), description, createdAt (formatted), expirationDate
- `CreditPackages` - Card grid displaying purchasable tiers (Starter/Pro/Enterprise) with credit amounts, prices in cents, and Stripe checkout initiation
- `PaymentForm` / `StripePaymentForm` - Stripe Elements wrapper handling payment confirmation with loading states and success/error toasts
- `CreditSystemDisabled` - Alert component displayed when credit billing is disabled system-wide

**Configuration Constants**
- `CREDIT_PACKAGES` - Array defining purchasable tiers: `{id, name, credits, price (cents), description}`
- `CREDITS_EXPIRATION_YEARS` - Number (1) defining default expiration timeframe from purchase date
- `FREE_MONTHLY_CREDITS` - Number (50) defining automatic monthly allocation amount
- `MAX_TRANSACTIONS_PER_PAGE` - Pagination limit for transaction history queries

## Behaviors & Rules

**Credit Expiration Logic**
- Credits expire exactly `CREDITS_EXPIRATION_YEARS` (1 year) from purchase date
- `expirationDate` is calculated at purchase time: `new Date().setFullYear(currentYear + 1)`
- Expired transactions display "Expired" Badge in UI and retain `remainingAmount` of 0
- `expirationDateProcessedAt` timestamp records when expiration was enforced (cron job or lazy check)

**Monthly Refresh Logic**
- Users receive `FREE_MONTHLY_CREDITS` (50) automatically each month
- Refresh eligibility determined by `shouldRefreshCredits` comparing `user.lastCreditRefreshAt` to current month/year
- Refresh transactions are recorded with type `MONTHLY_REFRESH` and null `expirationDate` (never expire) or separate expiration policy
- Updates `user.currentCredits` and `user.lastCreditRefreshAt` atomically

**Purchase Flow**
- Selecting a package calls `purchaseAction` creating a Stripe PaymentIntent
- Transaction record created immediately with `type: "PURCHASE"`, `remainingAmount: package.credits`, and calculated `expirationDate`
- `clientSecret` returned to frontend for Stripe Elements
- On payment success, `confirmPurchaseAction` updates `expirationDateProcessedAt` and adds credits to `user.currentCredits`
- Stripe `paymentIntentId` stored for reconciliation

**Transaction History Display**
- Amounts color-coded: green for PURCHASE (positive), red for USAGE (negative)
- Type badges use variants: default (PURCHASE), secondary (USAGE), outline (REFUND)
- Expiration column shows "Never" for null dates or formatted date for expiring credits
- Pagination enforced via `MAX_TRANSACTIONS_PER_PAGE` with page size options [10, 20, 50]

**Balance Calculation**
- `user.currentCredits` is the live balance (sum of non-expired remainingAmounts)
- `remainingAmount` decrements as credits are consumed (usage transactions)
- Expired credits are filtered from usable balance calculations but retained in history

## Inputs & Outputs

**purchaseAction**
- Input: `{ packageId: string, userId: string }`
- Output: `{ success: boolean, clientSecret: string, transactionId: string }` or throws error

**confirmPurchaseAction**
- Input: `{ paymentIntentId: string, userId: string }`
- Output: `{ success: boolean }` with side effects updating user credits

**TransactionHistory Component**
- Input: `userId: string` (fetched via server action)
- Output: Rendered DataTable with `Transaction[]` rows including computed `isExpired` status

**isTransactionExpired**
- Input: `transaction: { expirationDate: Date | null }`
- Output: `boolean` (true if `new Date() > new Date(expirationDate)`)

**shouldRefreshCredits**
- Input: `session: { user: { lastCreditRefreshAt: Date } }, user: { lastCreditRefreshAt: Date }`
- Output: `boolean` indicating if monthly refresh is due

## Dependencies

**External Services**
- Stripe SDK (`stripe`) for PaymentIntent creation and payment processing
- Cloudflare KV (implied by session management patterns) for caching credit balances
- D1 Database (implied by Drizzle ORM usage) for persistent transaction storage

**Libraries**
- `drizzle-orm` for database schema definition and queries (eq, and, desc, lt, gt operators)
- `date-fns` for date formatting in transaction history (`format`, `formatDistanceToNow`)
- `@stripe/stripe-js` and `@stripe/react-stripe-js` for PaymentForm UI
- `zod` for input validation on purchase actions
- `zsa` (Zod Server Actions) for type-safe server action definitions
- `sonner` for toast notifications on purchase success/failure
- `@tanstack/react-table` for TransactionHistory DataTable implementation

**Internal Dependencies**
- `userTable` schema for credit balance fields
- `getStripe()` utility for Stripe client initialization
- `withRateLimit` utility for purchase action rate limiting (RATE_LIMITS.PURCHASE)
- `useTransactionStore` (Zustand) for client-side transaction state refresh triggers

## Code Patterns

**Database Query Pattern (Expiration Check)**
```typescript
const expiredTransactions = await db
  .select()
  .from(creditTransactionTable)
  .where(
    and(
      lt(creditTransactionTable.expirationDate, new Date()),
      isNull(creditTransactionTable.expirationDateProcessedAt)
    )
  );
```

**Transaction Creation with Expiration**
```typescript
const expirationDate = new Date();
expirationDate.setFullYear(expirationDate.getFullYear() + CREDITS_EXPIRATION_YEARS);

await db.insert(creditTransactionTable).values({
  userId: input.userId,
  amount: creditPackage.credits,
  remainingAmount: creditPackage.credits,
  type: "PURCHASE",
  description: `Purchased ${creditPackage.name} package`,
  paymentIntentId: paymentIntent.id,
  expirationDate: expirationDate,
});
```

**Monthly Refresh Logic**
```typescript
if (shouldRefreshCredits(session, user)) {
  await db.update(userTable)
    .set({ 
      currentCredits: sql`${userTable.currentCredits} + ${FREE_MONTHLY_CREDITS}`,
      lastCreditRefreshAt: new Date()
    })
    .where(eq(userTable.id, userId));
    
  await db.insert(creditTransactionTable).values({
    userId,
    amount: FREE_MONTHLY_CREDITS,
    remainingAmount: FREE_MONTHLY_CREDITS,
    type: "MONTHLY_REFRESH",
    description: "Monthly free credits",
    expirationDate: null // or calculated expiration
  });
}
```

**Transaction History Column Definition**
```typescript
const columns = [
  {
    accessorKey: "type",
    cell: ({ row }) => {
      const type = row.original.type;
      const variant = type === "PURCHASE" ? "default" : 
                      type === "USAGE" ? "secondary" : "outline";
      return <Badge variant={variant}>{type.toLowerCase()}</Badge>;
    }
  },
  {
    accessorKey: "remainingAmount",
    cell: ({ row }) => {
      const expired = isTransactionExpired(row.original);
      return (
        <div className="flex items-center gap-2">
          <span>{row.original.remainingAmount}</span>
          {expired && <Badge variant="destructive">Expired</Badge>}
        </div>
      );
    }
  }
];
```

**Stripe Payment Flow**
```typescript
const handleSubmit = async (e: React.FormEvent) => {
  if (!stripe || !elements) return;
  
  const { error, paymentIntent } = await stripe.confirmPayment({
    elements,
    confirmParams: { return_url: `${window.location.origin}/dashboard/billing` },
    redirect: "if_required",
  });

  if (paymentIntent?.status === "succeeded") {
    await confirmPurchaseAction({ paymentIntentId: paymentIntent.id, userId });
    toast.success(`Successfully purchased ${credits} credits!`);
  }
};
```
# Skill: Stripe Payment Integration with Credit System

## Summary
This skill implements a complete credit-based billing system integrated with Stripe PaymentIntents. It enables users to purchase credit packages (Starter, Pro, Enterprise) using Stripe's secure payment elements, tracks credit balances and transaction history with expiration dates in a Drizzle ORM database schema, and manages the full payment lifecycle from package selection through payment confirmation to credit allocation. The system supports partial credit usage tracking, transaction expiration (1 year from purchase), and monthly credit refreshes, with server-side actions handling PaymentIntent creation and client-side React components managing the Stripe Elements integration and UI state.

## Key Components

**Database Schema & Constants:**
- `CREDIT_PACKAGES::CONST` - Tiered pricing configuration (Starter: 100 credits/$10, Pro: 500 credits/$45, Enterprise: 2000 credits/$160)
- `CREDITS_EXPIRATION_YEARS::CONST` - Credit validity period (1 year)
- `FREE_MONTHLY_CREDITS::CONST` - Monthly free credit allocation (50 credits)
- `creditTransactionTable::CALL` - Drizzle ORM table for transaction records
- `userTable.currentCredits::CALL` - User balance tracking field
- `userTable.lastCreditRefreshAt::CALL` - Monthly refresh timestamp tracking

**Server Actions:**
- `purchaseAction::CONST` - Creates Stripe PaymentIntent and pending transaction record
- `confirmPurchaseAction::CALL` - Verifies payment success and credits user account
- `getCreditPackage::CALL` - Utility to retrieve package details by ID

**Client Components:**
- `CreditPackages::DEF` - Package selection UI with pricing cards
- `PaymentForm::DEF` - Stripe PaymentElement wrapper with confirmation handling
- `TransactionHistory::DEF` - Data table displaying transaction history with expiration status
- `useTransactionStore::CALL` - Zustand store for managing selected package and client secret state

**Utilities:**
- `isTransactionExpired::CALL` - Date comparison utility for credit expiration
- `getStripe::CALL` - Stripe SDK initialization with STRIPE_SECRET_KEY
- `loaderVariants::CONST` - Framer Motion animation states for payment processing UI

## Behaviors & Rules

**Credit Package Rules:**
- Credits are sold in fixed tiers only (Starter: 100 credits/$1000 cents, Pro: 500 credits/$4500 cents, Enterprise: 2000 credits/$16000 cents)
- Price per credit decreases with volume (Starter: 10¢/credit, Pro: 9¢/credit, Enterprise: 8¢/credit)
- All purchased credits expire after 1 year (CREDITS_EXPIRATION_YEARS = 1)
- Users receive 50 free credits monthly (FREE_MONTHLY_CREDITS)

**Transaction Lifecycle:**
1. User selects package → `purchaseAction` creates Stripe PaymentIntent with metadata (userId, packageId, credits)
2. Server creates pending transaction record with `type: "PURCHASE"`, `amount` (credits), `remainingAmount` (credits), calculated `expirationDate` (current date + 1 year), and `paymentIntentId`
3. Client receives `clientSecret` and displays `PaymentForm` with Stripe PaymentElement
4. User completes payment → Stripe confirms → `confirmPurchaseAction` verifies PaymentIntent status is "succeeded"
5. Server updates transaction `expirationDateProcessedAt` and increments user `currentCredits`
6. Page revalidates `/dashboard/billing` to reflect new balance

**Credit Tracking & Expiration:**
- `remainingAmount` tracks unused credits from each purchase (decrements as credits are consumed)
- `isTransactionExpired` compares current date against `expirationDate` to determine validity
- Expired transactions retain record but credits are no longer usable
- Transaction types include: "PURCHASE", "USAGE", "MONTHLY_REFRESH"

**Edge Cases & Validation:**
- PaymentIntent creation requires valid `STRIPE_SECRET_KEY` environment variable
- `purchaseAction` validates packageId exists in CREDIT_PACKAGES before creating PaymentIntent
- `confirmPurchaseAction` rejects if PaymentIntent status !== "succeeded"
- Transactions include `paymentIntentId` for idempotency and reconciliation
- Credit balance updates occur in database transaction to prevent race conditions

## Inputs & Outputs

**purchaseAction:**
- Input: `{ packageId: string, userId: string }`
- Output: `{ success: boolean, clientSecret: string | null, transactionId: string }`
- Side Effects: Creates Stripe PaymentIntent, inserts pending record into `creditTransactionTable`

**confirmPurchaseAction:**
- Input: `{ paymentIntentId: string, userId: string }`
- Output: `{ success: boolean }`
- Side Effects: Updates transaction status, increments user `currentCredits`, revalidates billing page

**CreditPackages Component:**
- Props: None (self-contained, uses `useTransactionStore`)
- State: `selectedPackage` (string | null), `clientSecret` (string | null), `isLoading` (boolean)
- Renders: Grid of pricing cards or PaymentForm when clientSecret exists

**PaymentForm Component:**
- Props: `{ packageId: string, clientSecret: string, credits: number, price: number, onSuccess: () => void, onCancel: () => void }`
- Uses: `useStripe()`, `useElements()` from @stripe/react-stripe-js
- Returns: JSX with PaymentElement, amount display, and Cancel/Pay buttons

**TransactionHistory Component:**
- Props: `{ userId: string }`
- Data: Array of transactions with fields: `id`, `amount`, `remainingAmount`, `type`, `description`, `createdAt`, `expirationDate`
- Columns: Type (badge), Amount (colored +/-), Remaining (with expired badge), Description, Date, Expires

## Dependencies

**External Libraries:**
- `"stripe"::Stripe` - Server-side Stripe SDK for PaymentIntent management
- `@stripe/stripe-js` (implied by `loadStripe` and `process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY`)
- `@stripe/react-stripe-js` (implied by `useStripe`, `useElements`, `PaymentElement`, `Elements` provider)
- `drizzle-orm` - Database ORM for transaction and user table operations
- `zustand` - State management for transaction flow (`useTransactionStore`)
- `date-fns` - Date formatting in TransactionHistory (`format`)
- `sonner` - Toast notifications for payment success/failure
- `framer-motion` (implied by `loaderVariants` and `motion` references)

**Internal Dependencies:**
- `@/db/schema` - Database table definitions (creditTransactionTable, userTable, CREDIT_TRANSACTION_TYPE)
- `@/lib/utils` - `cn()` utility for class merging
- `@/components/ui/*` - Button, Card, Badge, Table components
- `@/components/data-table` - TanStack React Table wrapper for transaction history

**Environment Variables:**
- `process.env.STRIPE_SECRET_KEY` - Server-side Stripe authentication
- `process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` - Client-side Stripe initialization

## Code Patterns

**Stripe Client Initialization:**
```typescript
// src/lib/stripe.ts
import Stripe from "stripe";

export const getStripe = (): Stripe => {
  if (!process.env.STRIPE_SECRET_KEY) {
    throw new Error("STRIPE_SECRET_KEY is not defined");
  }
  return new Stripe(process.env.STRIPE_SECRET_KEY, {
    apiVersion: "2024-06-20",
  });
};
```

**Credit Package Configuration:**
```typescript
// src/lib/constants/billing.ts
export const CREDIT_PACKAGES = [
  {
    id: "starter",
    name: "Starter",
    credits: 100,
    price: 1000, // $10.00 in cents
    description: "Perfect for trying out the platform",
  },
  {
    id: "pro",
    name: "Pro",
    credits: 500,
    price: 4500, // $45.00 in cents
    description: "Best value for regular users",
  },
  {
    id: "enterprise",
    name: "Enterprise",
    credits: 2000,
    price: 16000, // $160.00 in cents
    description: "For high-volume usage",
  },
] as const;

export const CREDITS_EXPIRATION_YEARS = 1;
export const FREE_MONTHLY_CREDITS = 50;
```

**Database Schema Pattern:**
```typescript
// src/db/schema.ts (inferred from traces)
export const creditTransactionTable = pgTable("credit_transactions", {
  id: uuid("id").defaultRandom().primaryKey(),
  userId: uuid("user_id").notNull(),
  amount: integer("amount").notNull(), // Total credits purchased
  remainingAmount: integer("remaining_amount").notNull(), // Unused credits
  type: varchar("type", { length: 50 }).notNull(), // 'PURCHASE' | 'USAGE' | 'REFUND'
  description: text("description"),
  paymentIntentId: varchar("payment_intent_id", { length: 255 }),
  expirationDate: timestamp("expiration_date"),
  expirationDateProcessedAt: timestamp("expiration_date_processed_at"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  updatedAt: timestamp("updated_at").defaultNow().notNull(),
});
```

**Server Action Pattern (Purchase Flow):**
```typescript
// src/app/actions/billing.ts
"use server";

export const purchaseAction = async (input: {
  packageId: string;
  userId: string;
}) => {
  const stripe = getStripe();
  const creditPackage = CREDIT_PACKAGES.find((pkg) => pkg.id === input.packageId);
  
  if (!creditPackage) throw new Error("Invalid credit package");

  const paymentIntent = await stripe.paymentIntents.create({
    amount: creditPackage.price,
    currency: "usd",
    automatic_payment_methods: { enabled: true },
    metadata: {
      userId: input.userId,
      packageId: input.packageId,
      credits: creditPackage.credits.toString(),
    },
  });

  const expirationDate = new Date();
  expirationDate.setFullYear(expirationDate.getFullYear() + CREDITS_EXPIRATION_YEARS);

  const [transaction] = await db
    .insert(creditTransactionTable)
    .values({
      userId: input.userId,
      amount: creditPackage.credits,
      remainingAmount: creditPackage.credits,
      type: "PURCHASE",
      description: `Purchased ${creditPackage.name} package (${creditPackage.credits} credits)`,
      paymentIntentId: paymentIntent.id,
      expirationDate: expirationDate,
    })
    .returning();

  return {
    success: true,
    clientSecret: paymentIntent.client_secret,
    transactionId: transaction.id,
  };
};
```

**Client-Side Payment Form Pattern:**
```typescript
// src/app/dashboard/dashboard/billing/components/stripe-payment-form.tsx
"use client";

import { useStripe, useElements, PaymentElement } from "@stripe/react-stripe-js";
import { useState } from "react";
import { toast } from "sonner";

export function PaymentForm({ clientSecret, credits, price, onSuccess, onCancel }) {
  const stripe = useStripe();
  const elements = useElements();
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!stripe || !elements) return;

    setIsLoading(true);
    const { error, paymentIntent } = await stripe.confirmPayment({
      elements,
      confirmParams: {
        return_url: `${window.location.origin}/dashboard/billing?success=true`,
      },
      redirect: "if_required",
    });

    if (error) {
      toast.error(error.message || "Payment failed");
    } else if (paymentIntent?.status === "succeeded") {
      toast.success(`Successfully purchased ${credits} credits!`);
      onSuccess();
    }
    setIsLoading(false);
  };

  return (
    <form onSubmit={handleSubmit}>
      <PaymentElement />
      <div>${(price / 100).toFixed(2)}</div>
      <button type="button" onClick={onCancel}>Cancel</button>
      <button type="submit" disabled={!stripe || isLoading}>
        Pay ${(price / 100).toFixed(2)}
      </button>
    </form>
  );
}
```

**Transaction State Management:**
```typescript
// src/state/transaction.ts
import { create } from 'zustand';
import { combine } from 'zustand/middleware';

export const useTransactionStore = create(
  combine(
    {
      selectedPackage: null as string | null,
      clientSecret: null as string | null,
    },
    (set) => ({
      setSelectedPackage: (pkg: string | null) => set({ selectedPackage: pkg }),
      setClientSecret: (secret: string | null) => set({ clientSecret: secret }),
    })
  )
);
```

**Expiration Check Utility:**
```typescript
// src/lib/utils/transaction.ts
export const isTransactionExpired = (transaction: { expirationDate: Date | null }): boolean => {
  if (!transaction.expirationDate) return false;
  return new Date() > new Date(transaction.expirationDate);
};
```
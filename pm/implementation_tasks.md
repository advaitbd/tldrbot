# TLDRBot Freemium + Stripe Implementation Tasks

**Status**: 🔄 In Progress  
**Target Release**: T + 4 weeks  
**Total Tasks**: 47

---

## 📊 Progress Overview
- [x] **Database & Models** (6/6 completed) ✅
- [x] **Redis Caching & Quota Management** (7/7 completed) ✅
- [x] **Usage Tracking & Limits** (6/6 completed) ✅
- [x] **Stripe Integration** (8/8 completed) ✅
- [x] **Bot Commands & UX** (6/6 completed) ✅
- [x] **Core Bot Logic** (4/4 completed) ✅
- [x] **Configuration & Environment** (3/3 completed) ✅
- [ ] **Testing** (0/4 completed)
- [ ] **Monitoring & Analytics** (0/3 completed)

---

## 🗄️ Database & Models

### Task 1.1: PostgreSQL Schema Setup ✅
- [x] Create `users` table migration with fields:
  - `telegram_id BIGINT PRIMARY KEY`
  - `premium BOOLEAN DEFAULT FALSE`
  - `premium_expires_at TIMESTAMP`
  - `stripe_customer_id TEXT`
  - `created_at TIMESTAMP DEFAULT now()`
- [x] Create database migration script
- [x] Test migration on local database

### Task 1.2: User Model Implementation ✅
- [x] Create `User` model/entity class
- [x] Implement CRUD operations for users
- [x] Add premium status checking methods
- [x] Add Stripe customer ID management

### Task 1.3: Database Connection Setup ✅
- [x] Configure PostgreSQL connection in bot application
- [x] Set up connection pooling
- [x] Add database health check endpoint
- [x] Test database connectivity

### Task 1.4: User Management Functions ✅
- [x] Implement `get_or_create_user(telegram_id)` function
- [x] Implement `update_premium_status(telegram_id, premium, expires_at)` function
- [x] Implement `get_premium_users()` function for monitoring
- [x] Add database error handling and retries

### Task 1.5: Premium Status Utilities ✅
- [x] Implement `is_premium(telegram_id)` function
- [x] Implement `check_premium_expiry(telegram_id)` function
- [x] Add automatic premium expiry checking
- [x] Add premium status logging

### Task 1.6: Database Testing ✅
- [x] Write unit tests for User model
- [x] Write integration tests for database operations
- [x] Test premium status transitions
- [x] Test database error scenarios

---

## 🚀 Redis Caching & Quota Management

### Task 2.1: Redis Connection Setup ✅
- [x] Configure Redis connection
- [x] Set up Redis connection pooling
- [x] Add Redis health check
- [x] Test Redis connectivity and failover

### Task 2.2: Daily Usage Counter Implementation ✅
- [x] Implement `usage:daily:<uid>` key management
- [x] Set 24-hour TTL with reset at 00:00 Asia/Singapore
- [x] Implement `increment_daily_usage(telegram_id)` function
- [x] Implement `get_daily_usage(telegram_id)` function

### Task 2.3: Monthly Usage Counter Implementation ✅
- [x] Implement `usage:monthly:<uid>` key management  
- [x] Set monthly TTL to expire on 1st at 00:05
- [x] Implement `increment_monthly_usage(telegram_id)` function
- [x] Implement `get_monthly_usage(telegram_id)` function

### Task 2.4: Group Tracking Implementation ✅
- [x] Implement `groups:<uid>` SET management
- [x] Implement `add_user_to_group(telegram_id, chat_id)` function
- [x] Implement `get_user_group_count(telegram_id)` function
- [x] Implement `clear_user_groups(telegram_id)` for downgrades

### Task 2.5: DM Throttling Implementation ✅
- [x] Implement `dm_throttle:<uid>` timestamp tracking
- [x] Set 15-minute TTL for throttling
- [x] Implement `can_send_dm(telegram_id)` function
- [x] Implement `mark_dm_sent(telegram_id)` function

### Task 2.6: Counter Reset Logic ✅
- [x] Implement daily reset job for 00:00 Asia/Singapore
- [x] Implement monthly reset job for 1st of month
- [x] Add timezone handling for Singapore time
- [x] Test reset timing accuracy

### Task 2.7: Redis Error Handling ✅
- [x] Implement Redis failure detection
- [x] Add fail-safe quota blocking when Redis is down
- [x] Implement Redis reconnection logic
- [x] Add Redis error logging and alerting

---

## 📈 Usage Tracking & Limits

### Task 3.1: Quota Checking Functions ✅
- [x] Implement `within_daily_quota(telegram_id)` function (5 limit)
- [x] Implement `within_monthly_quota(telegram_id)` function (100 limit)
- [x] Implement `within_group_quota(telegram_id, chat_id)` function (3 limit)
- [x] Implement combined `within_quota(telegram_id, chat_id)` function

### Task 3.2: Counter Increment Functions ✅
- [x] Implement `increment_counters(telegram_id, chat_id)` function
- [x] Ensure atomic operations for counter updates
- [x] Add counter increment logging
- [x] Handle Redis errors in counter updates

### Task 3.3: Premium User Bypass Logic ✅
- [x] Integrate premium status check in quota functions
- [x] Ensure premium users bypass all quota checks
- [x] Add premium bypass logging
- [x] Test premium user unlimited access

### Task 3.4: Per-User Isolation ✅
- [x] Ensure quota enforcement is per Telegram user ID
- [x] Verify group context doesn't affect individual limits
- [x] Test quota isolation between users in same group
- [x] Add user isolation verification tests

### Task 3.5: Quota Enforcement ✅
- [x] Implement hard-block logic for over-quota commands
- [x] Add command deletion in group chats
- [x] Implement immediate DM sending to over-quota users
- [x] Ensure other group members continue using bot normally

### Task 3.6: Usage Statistics ✅
- [x] Implement `get_usage_stats(telegram_id)` function
- [x] Return formatted usage strings for commands
- [x] Add usage statistics logging
- [x] Create usage summary for monitoring

---

## 💳 Stripe Integration

### Task 4.1: Webhook Endpoint Setup ✅
- [x] Create `/webhook/stripe` endpoint
- [x] Implement Stripe webhook signature verification
- [x] Add proper HTTP status code responses
- [x] Test webhook endpoint accessibility

### Task 4.2: Checkout Session Completed Handler ✅
- [x] Implement `checkout.session.completed` event handler
- [x] Extract customer ID and subscription details
- [x] Update user premium status in database
- [x] Send success notification to user

### Task 4.3: Subscription Lifecycle Handler ✅
- [x] Implement `customer.subscription.updated` event handler
- [x] Handle subscription renewals
- [x] Handle subscription cancellations
- [x] Handle subscription modifications

### Task 4.4: Premium Activation Logic ✅
- [x] Implement `activate_premium(telegram_id, expires_at)` function
- [x] Clear Redis quota counters for new premium users
- [x] Send premium welcome message to user
- [x] Log premium activation events

### Task 4.5: Premium Deactivation Logic ✅
- [x] Implement `deactivate_premium(telegram_id)` function
- [x] Revert user to free tier immediately
- [x] Clear premium-related Redis keys
- [x] Send downgrade notification to user

### Task 4.6: Webhook Error Handling ✅
- [x] Implement webhook retry logic for failures
- [x] Add failure counting (max 3 retries)
- [x] Implement Sentry error alerting
- [x] Implement Slack notification for critical failures

### Task 4.7: Stripe API Integration ✅
- [x] Set up Stripe API client
- [x] Implement customer lookup functions
- [x] Implement subscription status checking
- [x] Add Stripe API error handling

### Task 4.8: Webhook Testing ✅
- [x] Set up Stripe webhook testing environment
- [x] Test all webhook event types
- [x] Test webhook signature verification
- [x] Test webhook failure scenarios

---

## 🤖 Bot Commands & UX

### Task 5.1: Enhanced /help Command ✅
- [x] Add "Account & Usage" section to help text
- [x] Implement dynamic usage display: `Today: X/5 · Month: Y/100 · Groups: G/3 (Free)`
- [x] Show `✅ Premium user (unlimited)` for premium users
- [x] Add "Upgrade anytime with /upgrade" text
- [x] Test help command with different user states

### Task 5.2: /upgrade Command Implementation ✅
- [x] Create `/upgrade` command handler
- [x] Create `/subscribe` alias for upgrade command
- [x] Ensure command only works in private chats
- [x] Create premium pitch message text
- [x] Implement InlineKeyboardButton with Stripe payment link

### Task 5.3: /usage Command Implementation ✅
- [x] Create `/usage` command handler
- [x] Mirror quota display from /help command
- [x] Show real-time usage statistics
- [x] Handle both free and premium user displays
- [x] Test usage command accuracy

### Task 5.4: Limit-Hit DM Implementation ✅
- [x] Create over-quota DM message template
- [x] Implement DM sending with throttling check
- [x] Add upgrade CTA with inline button
- [x] Handle DM send failures gracefully
- [x] Test DM throttling (max 1 per 15 min)

### Task 5.5: First-Time Welcome Message ✅
- [x] Detect first-time bot usage per user
- [x] Implement welcome message after first summary
- [x] Add small footer about free plan limits
- [x] Include upgrade call-to-action
- [x] Test welcome message timing

### Task 5.6: Inline Keyboard Implementation ✅
- [x] Create reusable inline keyboard for upgrade CTA
- [x] Implement payment link button
- [x] Add button click tracking
- [x] Style buttons for better UX
- [x] Test button functionality across different Telegram clients

---

## ⚙️ Core Bot Logic

### Task 6.1: Summary Command Modification ✅
- [x] Identify all existing summary-triggering commands
- [x] Integrate quota checking before processing
- [x] Add quota enforcement to each command
- [x] Ensure premium users bypass quota checks
- [x] Test modified commands with different user states

### Task 6.2: Block and DM Flow Implementation ✅
- [x] Implement `block_and_dm(telegram_id, update)` function
- [x] Delete over-quota command from group
- [x] Send DM with upgrade CTA to user
- [x] Log blocked command attempts
- [x] Test blocking flow end-to-end

### Task 6.3: Group vs Private Chat Handling ✅
- [x] Detect chat type (group vs private)
- [x] Handle quota enforcement differently for each type
- [x] Ensure private chat commands work normally
- [x] Test bot behavior in different chat contexts
- [x] Add chat type logging

### Task 6.4: Command Flow Integration ✅
- [x] Integrate quota checking into main command handler
- [x] Implement the pseudo-code logic from PRD:
  ```
  if is_premium(uid): return summarize()
  if not within_quota(uid, chat_id): block_and_dm(uid, update); return
  increment_counters(uid, chat_id)
  summarize()
  ```
- [x] Test complete command flow
- [x] Add performance monitoring for quota checks

---

## 🔧 Configuration & Environment

### Task 7.1: Environment Variables Setup ✅
- [x] Add `STRIPE_PAYMENT_LINK` environment variable
- [x] Add `STRIPE_WEBHOOK_SECRET` environment variable  
- [x] Add `REDIS_URL` environment variable
- [x] Update existing `BOT_TOKEN` usage
- [x] Add `ENV=production` variable for environment detection

### Task 7.2: Configuration Management ✅
- [x] Create configuration loading module
- [x] Validate required environment variables on startup
- [x] Add configuration error handling
- [x] Create development vs production config separation
- [x] Document all required environment variables

### Task 7.3: Secrets Management ✅
- [x] Secure storage of Stripe webhook secret
- [x] Secure storage of bot token
- [x] Implement secret rotation capability
- [x] Add secret validation
- [x] Document secrets management process

---

## 🧪 Testing

### Task 8.1: Unit Tests for Quota Logic
- [ ] Test quota checking functions with various scenarios
- [ ] Test counter increment and reset logic
- [ ] Test premium user bypass functionality
- [ ] Test Redis error handling in quota functions
- [ ] Achieve >90% coverage for quota logic

### Task 8.2: Unit Tests for Webhook Handlers
- [ ] Test Stripe webhook signature verification
- [ ] Test premium activation/deactivation logic
- [ ] Test webhook error handling and retries
- [ ] Test database updates from webhooks
- [ ] Achieve >90% coverage for webhook handlers

### Task 8.3: Integration Tests
- [ ] Test end-to-end upgrade flow
- [ ] Test quota enforcement in real bot environment
- [ ] Test Stripe webhook integration
- [ ] Test Redis and PostgreSQL integration
- [ ] Test bot command responses

### Task 8.4: End-to-End Testing
- [ ] Test complete user journey from free to premium
- [ ] Test quota limits and blocking behavior
- [ ] Test subscription lifecycle events
- [ ] Test error scenarios and recovery
- [ ] Load test quota checking performance (<50ms p99)

---

## 📊 Monitoring & Analytics

### Task 9.1: Logging Implementation
- [ ] Add structured logging for quota limit hits
- [ ] Add logging for upgrade button clicks
- [ ] Add logging for payment success events
- [ ] Add logging for premium activations/deactivations
- [ ] Implement log aggregation and analysis

### Task 9.2: Metrics Collection
- [ ] Track `daily_active_free` and `daily_active_premium` users
- [ ] Track `free_limit_hits` per unique user
- [ ] Track `checkout_clicks` to `payment_success_rate` conversion
- [ ] Track subscription churn rate
- [ ] Implement metrics dashboard

### Task 9.3: Alerting Setup
- [ ] Set up alerts for webhook failures
- [ ] Set up alerts for Redis/database connectivity issues
- [ ] Set up alerts for unusual error rates
- [ ] Set up alerts for payment processing issues
- [ ] Configure Sentry and Slack integrations

---

## ✅ Acceptance Criteria Verification

### Final Testing Checklist
- [ ] **Quota Enforcement**: Free users capped at 5/day, 100/month, 3 groups; Premium unlimited
- [ ] **Block & DM Flow**: Hard-block works, DM sent to user, group stays clean for others
- [ ] **Dynamic Commands**: `/help`, `/upgrade`, `/usage` show real-time data
- [ ] **Stripe Integration**: Checkout → webhook → premium flag updates within 30s
- [ ] **Test Coverage**: Automated test suite passes with >90% coverage
- [ ] **Monitoring**: Metrics visible and alerting working
- [ ] **Performance**: Quota checks <50ms p99
- [ ] **Reliability**: Webhook processing >99.9% success rate

---

## 📅 Implementation Timeline

### Week 1 (T+0.5): Foundation
- [x] Complete Database & Models (Tasks 1.1-1.6) ✅
- [x] Complete Redis Setup (Tasks 2.1-2.4) ✅
- [x] Complete Basic Usage Tracking (Tasks 3.1-3.3) ✅

### Week 2 (T+1): Core Logic  
- [x] Complete Stripe Integration (Tasks 4.1-4.8) ✅
- [x] Complete Usage Enforcement (Tasks 3.4-3.6) ✅
- [x] Complete Core Bot Logic (Tasks 6.1-6.4) ✅

### Week 3 (T+2): User Experience
- [x] Complete Bot Commands & UX (Tasks 5.1-5.6) ✅
- [x] Complete Configuration (Tasks 7.1-7.3) ✅
- [ ] Begin Testing (Tasks 8.1-8.2)

### Week 4 (T+3): Testing & Launch
- [ ] Complete All Testing (Tasks 8.3-8.4)
- [ ] Complete Monitoring (Tasks 9.1-9.3)
- [ ] Final Acceptance Criteria Verification
- [ ] Production Deployment

---

**Next Steps**: Complete the final Core Bot Logic task (6.4), then proceed with comprehensive testing. 
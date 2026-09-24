---
title: "Compute cost: the buy-vs-rent calculation everyone gets wrong"
date: 2026-05-21
tags: ["cost-engineering", "cloud", "on-prem", "gpu", "capacity-planning", "tco"]
categories: ["engineering"]
description: "Why most buy-vs-rent compute cost models are wrong, the variables that actually decide the answer, and a concrete GPU case study with a real cost matrix."
cover: "/images/og/compute-cost-calculation-buy-vs-rent.png"
draft: false
---

## The question gets framed wrong

Every couple of years the same question lands on an architect's desk, dressed up in a fresh deck:

> "Should we move to the cloud?"

or, lately, the inverted version:

> "Should we move *off* the cloud?"

Both are the wrong question. The right question is:

> "Which of our workloads belong on owned iron, which belong on rented capacity, and what is the *workload-shape threshold* that flips one into the other?"

A binary buy-vs-rent answer is almost always a sign that someone is selling something - a cloud migration, a reverse migration, or a CFO narrative. Real infrastructure ends up as a portfolio, and the only interesting work is figuring out where the boundaries between the buckets belong.

This post is about why the standard TCO (Total Cost of Ownership) spreadsheet lies, where the lie hides, and the variables that actually decide the answer in production. It closes with a concrete worked example: sizing a 24 GB FP16 GPU for a live-transcription pipeline, using a real cost matrix.

## The cost surfaces nobody puts on the slide

Both sides of the calculation have visible costs and hidden costs. The visible ones go on the slide. The hidden ones decide your budget.

| Rented compute | Owned compute |
|---|---|
| Compute hours (on-demand / RI / savings plan) | Capex - servers, accelerators, switches, ToR, PDUs, cabling |
| Storage - block, object, snapshots, multi-AZ replication | Colo or in-house DC - rack-units, kW draw, cross-connects, remote-hands |
| **Egress** - data leaving the cloud: $0.05-0.09/GB out (inbound is free); even traffic between zones is billed | Power and cooling - typically **30-40%** of run-rate; PUE matters |
| IOPS and throughput for managed storage | Spares and RMA - **5-10%** spare inventory minimum |
| Managed-service premium (RDS, MSK, EKS, NAT GW hours) | Refresh cycle - 3-5y general, *much shorter* for accelerators |
| Observability ingest + retention (often the 3rd largest line item) | Headcount - SRE, DC techs, procurement |
| Support contract (Business / Enterprise = % of total spend) | Cost of capital - capex is money that could fund something else |
| | Stranded capacity - gap between provisioned and used |

**Abbreviations:**

- **RI** - reserved instance
- **AZ** - availability zone
- **IOPS** - I/O operations per second
- **capex** - capital expenditure
- **ToR** - top-of-rack switch
- **PDU** - power distribution unit
- **colo** - colocation (your hardware in rented DC space)
- **DC** - data center
- **RMA** - hardware replacement
- **PUE** - datacenter energy overhead
- **RDS / MSK / EKS / NAT GW** - AWS managed services
- **SRE** - site reliability engineer

The two surfaces are not symmetric. The cloud surface is dense with small recurring charges that are easy to model individually and easy to miss collectively. The owned surface is dominated by a few large capex events with long-tailed opex underneath. The accounting departments treat them differently, the engineering teams treat them differently, and the comparison only becomes honest when both are reduced to the same `$ per unit-of-work per year`.

## The variables that actually decide

Most TCO models compare a single unit price - `$/vCPU/hour`, `$/GPU/hour`, `$/GB` - cloud against owned, and stop there. This is a category error. Unit price is not a decision input; it is a number that *falls out* of deeper variables. Compare the unit prices and you are reading the answer off the wrong line. The variables below are what actually move it.

### Workload shape - the hidden multiplier

Workload shape is the ratio of peak demand to sustained demand, plus the predictability of the peaks. A workload running 24/7 at 80% utilization has the opposite cost profile from one running 4 hours a day at 95% peak and idle the rest of the time.

The three shapes that matter:

```text
  STEADY-STATE                SPIKY UNPREDICTABLE         SPIKY PREDICTABLE
  (own it)                    (rent it)                   (hybrid)

util                          util                        util
100│                          100│   █        █          100│      ▄        ▄
 80│████████████████████       80│   █        █           80│     ███      ███
 60│████████████████████       60│   █  █  █  █           60│    █████    █████
 40│████████████████████       40│ █ █  █  █  █           40│ ▄▄██████▄▄▄██████▄
 20│████████████████████       20│ █ █  █  ███ █          20│███████████████████
  0└─────────────────────►      0└─────────────────►       0└─────────────────►
       time (24/7)                    time                       time (diurnal)

  production databases,        a new product launch,   Black Friday sales,
  email & file servers,        a marketing campaign,   streaming sport events,
  ERP / CRM systems            breaking-news traffic   busy by day, idle at night
```

- **Steady-state, high-utilization**: owned iron wins by a wide margin once utilization passes ~50-60%. The crossover happens because cloud pricing implicitly charges you for elasticity you aren't using.
- **Spiky, unpredictable**: cloud almost always wins, even at uncomfortable unit prices, because the alternative is overprovisioning owned capacity to the peak.
- **Spiky but predictable**: the optimal answer is hybrid - own the baseline, rent the burst. Pure cloud or pure on-prem are both bad here.

Engineering implication: before any TCO math, build a workload-shape inventory. For each workload, compute `p50/p99 demand` and `peak/sustained ratio` over a representative period. Those two numbers tell you which bucket the workload belongs in before you ever look at price.

### Breakeven in hours, not years

Most TCO models report payback in *years*. That hides the answer. The useful framing is:

> "How many hours of actual usage does it take before the one-time purchase is cheaper than continuing to rent?"

Divide purchase price by rental rate, get a number of hours. Then compare against the workload's realistic utilization.

```text
  cumulative
  cost ($)              rent (linear: rate × hours)
       ▲                              ╱
       │                            ╱
       │                          ╱
       │                        ╱
       │                      ╱
       │                    ╳────────── breakeven
       │                  ╱│
       │                ╱  │
       │              ╱    │           buy (flat: capex + power)
       │            ╱──────┼─────────────────────────────
       │          ╱        │
       │        ╱          │
       │      ╱            │
       │    ╱              │
       │  ╱                │
       │╱                  │
       └───────────────────┴────────────────────────────►
                       hours of use            
                    (e.g. ~1,500h ≈ 60-75 days continuous)
```

A box that breaks even at 1,500 hours pays for itself in 60-75 days of continuous use; one that needs 8,000 hours might never pay for itself before the hardware is obsolete.

This framing also surfaces a brutal truth: hardware that has a long buy-vs-rent breakeven on cheap silicon (consumer GPUs, mid-range CPUs) is *more* attractive to buy than premium silicon with expensive cloud equivalents - because the cloud premium on premium silicon is what extends the breakeven.

### MVP-tier vs SaaS-tier pricing - the rate that doesn't survive contact with production

Cloud pricing is not one curve. It is at least two:

| Tier | Providers | Typical rate vs hyperscaler | What you get | What's missing |
|---|---|---|---|---|
| **MVP-tier** | RunPod, Vast.ai, Lambda, lower Nebius | 30-60% | Raw compute, low friction, fast spin-up | No SLA, no GDPR DPA, no VPC, no enterprise support |
| **SaaS-tier** | AWS, GCP, Azure, SOC 2 providers | 100% (baseline) | Financially-backed SLA, GDPR DPA, VPC, enterprise support, CISO-acceptable procurement | Pays 2-4x the neo-cloud rate |

The TCO spreadsheet collapses if you build it on MVP-tier numbers but the production deployment needs SaaS-tier guarantees. Neo-cloud rates are not contractual long-term - capacity, region, and pricing can all move under you. Treat them as a snapshot, not a commitment. The same workload that costs $0.80/hr on neo-cloud may cost $2.50/hr the moment it has to live behind a hyperscaler load balancer with a real SLA attached.

### Accelerator depreciation - the 3-5 year lie

Finance amortizes hardware over 3-5 years on a straight line. For CPUs and storage that is roughly right. For accelerators - GPUs, ASICs (application-specific integrated circuits), NPUs (neural processing units) - it is silently wrong, and the error always makes buying look better than it is.

Why: an accelerator's performance per watt and per dollar improves ~1.5-2x per generation, and a new generation lands every 18-24 months. Take NVIDIA's datacenter GPUs as the obvious example: an A100 was cost-competitive in 2020; the H100 reset the economics by 2023, the B200 again by 2025. Your card still runs - it just loses money against a more efficient replacement every hour it stays powered on.

So model owned accelerators on a **2-3 year horizon, not 5**. If the purchase still wins at 2 years, the decision is real. If it only wins at 5, you are booking value the next chip will erase.

### Egress - the silent killer

For any workload that emits more bytes than it ingests - video delivery, data export, off-cloud backups, multi-region replication - egress is the line item that breaks the model.

Order of magnitude. A 5 Mbps live stream to 1,000 concurrent viewers for one hour:

- 5 Mbps × 3,600 s = 18,000 Mb = 2.25 GB per viewer-hour.
- 1,000 viewers × 2.25 GB = 2,250 GB ≈ 2.25 TB.
- At $0.085/GB egress: ~$191 per hour, per 1,000 viewers.

Scale that to a million viewers across a workday and egress alone justifies an owned CDN. Where egress dominates compute, it decides buy-vs-rent before you ever price a server.

## Tradeoffs and failure modes

Where the model blows up in production:

| Failure mode | Symptom on the bill | What it actually means | Fix |
|---|---|---|---|
| **Egress surprise** | Monthly bill triples | "Safety" cross-region replication enabled | Alert on egress *rate*, not just total |
| **Stranded capacity** | Owned box at 20% util | Bought for a peak that never came | Colocate other workloads onto the spare |
| **Stranded commitment** | RI on a deprecated instance family | 3-year forecast was wrong at 18 months | Match RI duration to workload predictability |
| **Refresh stall** | GPU TCO sliding behind cloud over time | Bought accelerators on 5y, silicon moves on 2y | Budget refresh on 2-3y horizon, not 5y |
| **Headcount drift** | "Cloud was supposed to cut SRE cost" | Same ops work, different shape | Don't model headcount cuts into cloud TCO |
| **CDN-as-compute** | "Transcoding" line item dominated by delivery | Egress hidden in a managed video service | Break out delivery cost separately from compute |

Two more that don't fit the table:

- **Stateless is portable; stateful is sticky.** Moving stateless workers is a Terraform exercise; moving 50 TB of hot Postgres is a quarter of work. Decide early where the data lives - gravity is permanent.
- **Reserved / savings plans are a forecast, not a discount.** A 3-year commit assumes you still need that exact instance shape in 36 months - almost never true for accelerators. Match commit duration to *workload predictability*, not maximum discount.

## Worked example: sizing a GPU for real-time audio transcription & translation

Time to put the framework to work on a real decision. A recent project needed real-time audio transcription - a Whisper-class speech-to-text model feeding machine translation, FP16 inference, 2-3 parallel streams per host. That pins working VRAM at around 24 GB, with 48 GB wanted where several translation models stay hot at once. The catch: the buy-vs-rent question landed *before* the MVP shipped, so there was no utilization data to lean on - exactly the situation where the framework has to do the heavy lifting.

So we shortlisted every GPU that clears the 24-48 GB bar and priced each one both ways - buy and rent. Here is the matrix that came out of it (GPU market as of mid-2026; re-validate before any purchase):

| GPU | VRAM | Purchase (USD) | Power @ 1000 h | Buy total @ 1000 h | MVP rate (USD/h) | SaaS rate (USD/h) | Rent total @ 1000 h | Buy beats rent after (h) |
|---|---|---|---|---|---|---|---|---|
| A10 / A10G | 24 GB | ~1,900-2,300 | ~$17 | ~1,920-2,320 | ~1.26 (AWS g5.xlarge) | ~1.26 (AWS - already SaaS-grade) | 1,260 | **~1,500-1,800** |
| L4 | 24 GB | ~2,500-3,000 | ~$8 | ~2,510-3,010 | ~0.80 (GCP g2) | ~0.80 (GCP - already SaaS-grade) | 800 | **~3,100-3,800** |
| L40S | 48 GB | ~7,500-9,500 | ~$39 | ~7,540-9,540 | ~1.10 (RunPod) | ~1.70 (Nebius FI) | 1,100 | **~6,800-8,600** |
| A100 80 GB PCIe | 80 GB | ~9,200-12,000 | ~$33 | ~9,230-12,030 | ~1.50 (RunPod) | ~3.43 (AWS p4de) | 1,500 | **~6,100-8,000** |
| RTX 4090 | 24 GB | ~2,500 | ~$50 | ~2,550 | ~0.40 (Vast.ai) | n/a - consumer tier | 400 | **~6,300** |
| H100 80 GB PCIe | 80 GB | ~25,000-32,000 | ~$39 | ~25,040-32,040 | ~3.00 (EU neocloud) | ~12.25 (AWS p5) | 3,000 | **~8,300-10,700** |

Read the matrix through that framework and four things jump out, roughly in the order you should weigh them:

**Breakeven in hours is the right unit.** The A10 pays for itself in 1,500-1,800 hours - 60-75 days of continuous use. The L4 needs 3,100-3,800 despite being cheaper to *rent*, because its rental rate is lower too. The H100 needs 8,300-10,700 against the cheapest neo-cloud rate - over a year of full-duty use to break even on silicon that has 18-24 months before a successor lands.

**The 4090 trap.** Cheapest box, lowest neo-cloud rate, fastest raw breakeven - and almost certainly wrong for production, because there is no SaaS-grade rent path. The moment compliance, SLA, or VPC isolation enters the room, it drops off the list. Fine for an internal dev box; wrong for a customer-facing service.

**Tier matters more than the headline rate.** The A100 looks great at $1.50/hr on neo-cloud - until the same workload behind AWS p4de is $3.43/hr (2.3x). The H100 gap is worse: $3 vs $12.25 (4x). A TCO model built on neo-cloud rates but promising hyperscaler reliability is fiction. Same trap outside GPUs: R2 vs S3 + egress, neo-CDNs vs CloudFront, indie Postgres vs RDS. The neo-tier rate is real - it just isn't the production rate.

**The non-GPU overhead.** At ~1,000 GPU-hours/month, a production deployment adds $50-230/month of supporting infrastructure - load balancer, NAT gateway, registry, log ingest, DNS, TLS. Small alone, real in aggregate, and never on the napkin.

Put those four together and the answer writes itself: **rent A10 / A10G on AWS Frankfurt for the MVP** - low upfront cost, SaaS-grade out of the box, EU region for GDPR proximity, no on-call rota. Buying gets revisited only when all three of these hold: sustained utilization above ~50% (~360 GPU-hours/month), a single-region deployment, and an on-call rotation to own host uptime.

The pattern generalizes: **rent until the workload is proven, then re-tier**. Not laziness - sequencing. Buying before the shape is observable is a bet on a forecast; renting buys the data that makes the forecast unnecessary.

## Lessons learned

A few hard-earned ones:

- **Reduce to `$ per unit-of-work per year`, not `$/hour`.** Unit of work = stream-hour, transcribed minute, request, GB processed - whatever the business actually charges for. Anything else is theater.
- **Workload-shape numbers (`p50/p99`, `peak/sustained`) are non-negotiable inputs.** Walking into a buy-vs-rent meeting without them means you will lose to whoever has them, even if their analysis is otherwise worse.
- **Egress is the first thing to model, not the last.** If egress dominates, the rest of the spreadsheet is decoration.
- **Amortize accelerators on 2-3 year horizons.** Anything longer is borrowing optimism from finance.
- **Hybrid is the steady state, not a transition phase.** Treat it as the target architecture, not a compromise you intend to clean up later.
- **Forecast errors are asymmetric.** Underprovisioning owned iron is a 6-month problem; overprovisioning is a 5-year problem. Buy lean, rent the spikes.

## If I were redesigning today

I would stop treating the TCO spreadsheet as a one-shot artifact and build a **continuous cost model** as a first-class service: workload-shape telemetry per service, a planner that maps each workload to a tier (owned / committed-cloud / on-demand) from observed shape rather than tribal memory, and quarterly re-tiering against real data. The question doesn't go away - but once the platform produces honest inputs, the answer stops being a debate and becomes a derived number. That is the only version of this calculation worth running twice.

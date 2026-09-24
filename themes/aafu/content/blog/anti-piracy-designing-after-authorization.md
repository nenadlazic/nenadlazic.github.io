---
title: "Anti-piracy after authorization: fingerprinting, watermarking and what to build first"
date: 2026-08-25T20:00:00+02:00
tags: ["security", "fingerprinting", "watermarking", "anti-piracy", "system-design", "architecture"]
categories: ["engineering"]
description: "The engineering half: requester fingerprinting ranked by what a forgery costs, the watermark capacity arithmetic that decides whether marking can work at all, content fingerprinting as a search problem, and the two loops that get confused for one."
cover: "/images/og/anti-piracy-designing-after-authorization.png"
draft: false
---

The [first part](/blog/content-piracy-by-authorized-users/) of this series established the problem: why the abuser usually holds valid access, the four shapes that abuse actually takes, and the three unrelated technologies that all get called {{< hl blue >}}fingerprinting{{< /hl >}}.

This part moves from the problem to the system. Before getting into the engineering, there are four things from part one worth keeping in mind:

- An **artifact** is whatever you deliver: a stream, a document, a dataset, a build, an image catalogue, a set of weights.
- Abuse takes four shapes. **Sharing** and **leeching** are still moving through your infrastructure, so they can be **interrupted**. **Mirroring** and **republication** are already over when you find out, so all that is left is **attribution**.
- Those are two separate systems with different latency budgets, and merging them is the most common architectural mistake here.
- **Requester fingerprinting** serves the interruption side: stopping a suspicious client mid-delivery. **Recipient marking** and **content fingerprinting** serve the attribution side, as a pair: finding a leaked copy, then tracing it to its recipient.

That distinction is the foundation for everything that follows. The rest is the engineering: each technology taken apart, its limits made explicit, and the pieces wired back together into something you could actually build.

The three technologies, in order:

1. [Fingerprinting the requester](#1-fingerprinting-the-requester)
2. [Marking the copy](#2-marking-the-copy)
3. [Finding the leak](#3-finding-the-leak-content-fingerprinting)

Then [how they fit together](#putting-it-together-designs-that-hold-up).

---

## 1. Fingerprinting the requester

*Interruption side*

Only one technology applies here.

A fingerprint is simply a set of details about the caller that you never explicitly asked them to provide. Their software reveals them simply by running.

Its layers are worth ranking not by how accurate they are, but by **what it costs the abuser to fake them**.

![The signal stack ranked by cost to fake, from TLS up to platform attestation](/images/antipiracy-signal-stack.png)

Note the inversion in that picture. The two layers vendors talk about most are the two cheapest to defeat.

### The layers you can read without any help from the client

{{< hl amber >}}TLS: from JA3 to JA4{{< /hl >}}

When a client opens a TLS connection, its first message lists the version, the ciphers it supports, the extensions and the curves. Different software produces a different list.

**JA3** hashed that list into one short string, so you could recognise the same software again later.

It worked until January 2023. Chromium began permuting the order of TLS extensions on every connection, and within days nearly every Chrome connection was producing a different JA3 value.

**JA4** fixed that by sorting the fields before hashing. It restored stability. It did not make the fingerprint hard to fake, and that difference is the whole story of this layer.

{{< hl amber >}}Where you can compute it, and what it costs{{< /hl >}}

- **Only where TLS is terminated**, usually your edge proxy. Behind that point the backend sees plain HTTP.
- **It travels as a header the proxy adds.** The backend must drop any copy of that header the client sent itself, or anyone can hand you a Chrome fingerprint.
- **A third-party CDN in front of your edge** terminates TLS itself, so you end up fingerprinting the CDN, not the client.
- **Header order has the same problem:** a reverse proxy reorders and rewrites headers on the way through, so that fingerprint has to be taken at the proxy too.

The cost is smaller than people expect. The fingerprint is computed once per TLS connection, not per request, and a client typically fetches hundreds of objects over one kept-alive connection.

{{< hl amber >}}Two neighbouring layers{{< /hl >}}

- **The TCP handshake** (JA4T) leaks initial TTL, MSS, window size and the order of TCP options. Coarse - it gives you an operating system family, not a device. But it is written by the kernel, not by the abuser's code, which makes it harder to change.
- **HTTP/2** adds another layer: the SETTINGS values and their order, the first flow-control update, PRIORITY frames, and pseudo-header ordering. The technique comes from an Akamai white paper, which reported that browser families could be separated with 99.7% accuracy using the HTTP/2 fingerprint alone. In practice, it can be more discriminating than TLS.

{{< hl amber >}}How well it works{{< /hl >}}

Recent academic work trained gradient-boosted classifiers on JA4 features over roughly 200,000 labelled records from JA4DB, reporting near-perfect separation on its own test set: AUC around 0.998, F1 around 0.973.

Read the setup before believing the number. A record was labelled bad-bot when the client's application field contained "bot". So the model learned to recognise software that announces itself, which is a much easier problem than recognising software that lies.

The authors say where it fails, in plain terms:

- against **Puppeteer, Playwright and Selenium**, because those drive a real browser binary and inherit a real browser's TLS stack
- against **libraries written to mimic a target fingerprint** on purpose

Their own conclusion is that JA4 "is not a standalone authentication or attribution mechanism".

So this layer separates cheap tooling from real browsers very well, and a motivated abuser from a real browser not at all. `curl-impersonate`, `curl_cffi` and `uTLS` reproduce a target browser's cipher list, extension order and HTTP/2 settings in a single call.

Here is what that looks like against a plain nginx computing JA4, in a small lab:

| Client | JA4 |
|---|---|
| curl | `t13d3112h2_e8f1e7e78f70_0c76ac0b1ceb` |
| curl with a Chrome User-Agent | `t13d3112h2_e8f1e7e78f70_0c76ac0b1ceb` |
| ffmpeg | `t13d291300_723694b0fccc_4039a0f2863c` |
| curl-impersonate as Chrome 116 | `t13d1516h2_8daaf6152771_0adf69b4533f` |

Changing the User-Agent changes nothing underneath. Changing the TLS library changes everything. And a library built to imitate Chrome gets a Chrome-shaped answer.

{{< hl amber >}}The asymmetry that survives{{< /hl >}}

It is the most useful thing in this section.

**A spoofer normally fakes one layer at a time.** A bot on a Linux host can present a flawless Chrome-on-Windows TLS fingerprint and still emit Linux TCP values, because the kernel wrote those.

So do not hunt for one good fingerprint. Look for contradictions between layers. JA4T captures the TCP half, which is why the pair is worth more than either piece.

One caveat: the contradiction only exists while the abuser imitates a platform he is not running on. Once he runs the real browser on the real OS, it disappears.

### The layers that need the client

Some signals can only be collected if you can run code on the client itself. That opens a wider surface: canvas and WebGL output, audio behaviour, fonts, screen metrics, timezone, memory, supported codecs, and similar details.

The problem is that these signals are much less unique and stable than they appear. On an ordinary commercial audience, only a third of desktop fingerprints and under a fifth of mobile ones were unique, and fingerprints change over time.

A fingerprint is an identifier that decays.

That makes it useful for **grouping related activity**, but weak as a standalone identity or accusation. Where available, platform attestation is stronger: instead of inferring who the client is from its characteristics, it provides a platform-signed statement about the client itself. It is useful at credential issuance, but not as the primary signal on the delivery path.

### The layer that actually pays

The most useful signals are already in the access logs:

- network diversity under one credential
- request rate and access patterns
- concurrency and activity over time
- delivered versus entitled volume
- client identity changes within a session or across credential history

These are cheap to collect and require no changes to the request path. More importantly, they become much stronger when observed over time.

Measure behaviour, not individual sessions. A shared credential does not need two active sessions at the same time; its history can still look nothing like a normal consumer.

### Where the request comes from

Network information is useful context: home, mobile, hosting, VPN, residential proxy.

But an IP address is not an identity. Addresses are shared, change over time, and can be deliberately proxied.

Use network information as one feature in the broader behavioural profile, not as a hard binding.

### The turn: group, do not accuse

A fingerprint is weak evidence for saying *"this is a pirate"*, but a strong key for asking *"does this look like the same actor we have seen before?"*

Once one session is identified through behaviour, an abuse report, or a watermark hit, fingerprinting can connect it to other sessions. The same idea applies to infrastructure: domains, IPs, hosting, DNS, and portal patterns can reveal related services.

One confirmed incident can therefore become a population of related activity.

---

## 2. Marking the copy

*Attribution side*

This is what is left once **mirroring** or **republication** has already happened.

Marking writes a per-recipient identifier into the artifact, so a copy found anywhere traces back to whoever it was issued to. Below, a *chunk* is whatever unit your artifact is already split into: a video segment, a page, a shard.

There are four places to put the mark:

| Where the mark goes in | Cost | Trust needed in client |
|---|---|---|
| Per-recipient generation | grows with N; fine for hundreds of recipients | none |
| Variant composition (A/B) | storage doubles once, delivery flat | none |
| Recipient-side embedding | almost none | high - the abuser controls it and can turn it off |
| Delivery-time embedding | CPU per request, breaks caching | none |

Variant composition is the practical default, and the only one with an interoperable standard: DASH-IF's Forensic A/B Watermarking, published by ETSI as **TS 104 002** in 2023. Every chunk exists in an A and a B variant; the edge reads one bit of the recipient's identifier per chunk from the request token and serves the matching variant.

![How A/B variant marking produces many recipient identities from two stored variants](/images/antipiracy-ab-marking.png)

**Two marked variants plus a per-recipient selection sequence give you N identities from 2 stored copies** - for video segments, document pages and dataset shards alike.

### The failure mode that will not show up on a dashboard

**The token carrying the identifier must be integrity-protected and bound to the session.** If a client can edit it, it can request the all-A sequence and become unattributable, and nothing will alert on it. The edge must fail closed on a bad or missing token, and both variants must be encrypted under the same key.

Mark at every handoff, too, not just at the end user. A per-partner mark plus a per-session mark tells you whether a leak happened inside a distributor or on your own delivery path.

### The arithmetic to run before any procurement call

```text
  bits available   =  f(artifact surface, robustness margin)
  bits needed      =  log2(recipients) + collusion margin + ECC
  material needed  =  bits needed / bits per chunk
                      ->  the time or size it takes to attribute
```

For A/B that is about one bit per chunk: 15 bits per minute at four-second chunks. Ten million recipients need 24 bits; with error correction and a collusion margin you are past forty - about three minutes of *clean* material, more in practice.

The window live enforcement works to is **30 minutes**: Italy's Piracy Shield deadline, and the ceiling an EU study proposed for live takedown. Attribution spends three of them before you know whose account it was. That makes **chunk size an anti-piracy parameter**: at six-second chunks the same identifier needs four minutes.

And **fragments cannot be attributed.** A thirty-second clip or a two-hundred-row extract has too little surface. If your loss is fragments, marking is the wrong purchase.

### Collusion and robustness

Recipients can compare and splice their copies; in A/B, two spliced sequences can decode to an innocent third party. Anti-collusion codes (Tardos) fix that, but code length grows with the **square** of the number of colluders, and that is proven unavoidable. Design to that scaling law, not to a vendor datapoint.

Recovery is always probabilistic: the mark has to survive re-encoding, cropping, screen capture, format conversion, row sampling or recompilation, depending on the medium, while staying invisible. **Marking prevents nothing. It changes the odds of being identified, and so the economics of leaking.**

It also depends on the registry mapping identifiers to recipients - the most sensitive database you own. Its retention caps how far back you can attribute, and accusing the wrong customer from a corrupted registry is worse than a leak you never attributed.

---

## 3. Finding the leak: content fingerprinting

*Attribution side*

Marking tells you whose copy it is only once something tells you a copy exists. That is content fingerprinting: a small, change-tolerant descriptor of your artifact - perceptual hashes, audio peak patterns, text shingles - matched against an index of your own catalogue.

- **It is a search problem, not a hashing problem.** The index over a large catalogue at crawl volume is where the money goes, so this layer is usually bought.
- **Its ceiling is geometric.** Flips, heavy crops, overlays and compositing into a bigger frame - exactly what a pirate's branding does - break weak hashes.
- **A match is a location, not a verdict.** Partners and pirates both match; separating them is a rights-metadata problem.

Used well, it produces a queue of locations ranked by audience, each a candidate for mark extraction.

---

## Putting it together: designs that hold up

Back to the two halves from part one, this time with their internals. Interruption and attribution are pipelines of different length, and only one of them runs while you can still change the outcome.

![The interruption loop and the attribution loop, with their different latencies and owners](/images/antipiracy-two-loops.png)

Before the failure list, the mapping that decides what you build. Symptoms here are ambiguous, and the same one points at different controls depending on which reading is true.

| What you see | Likely reading | What helps | What will not help |
|---|---|---|---|
| One credential, many networks, never at the same time | **sharing**, staggered in time | device and location history over a window; binding the credential to named devices | concurrency limits |
| One credential, volume far above entitlement | **leeching** - an audience being served off your infrastructure | per-object validation, session binding, throttling | access control; marking works but is the slow path |
| Your artifact on third-party hosts, your egress flat | **mirroring** or **republication** after one legitimate fetch | marking, plus content fingerprinting to find it | anything at request time |
| A perfect client fingerprint, implausible access pattern | an emulated client - an entry route, not one of the four shapes | attestation at issuance, token integrity, cross-layer consistency | any single fingerprint, marking |
| Cheap tooling in your logs | opportunistic scraping, below all four shapes | protocol-layer classification, graduated response | attestation, marking |
| Fragments only, nothing longer than a minute | clipping, outside what marking can reach | monitoring, then accept it | marking - not enough surface |

The right-hand column is the useful one. Most wasted spend here is a correct control bought for the wrong reading of a symptom.

Now the failures, which are predictable enough to list.

**Allow or deny at the edge, keyed on a classifier.** As brittle as the classifier's false-positive rate, which you do not know. Graduated response survives its own mistakes instead: throttling or capping quality changes timing rather than correctness, and looks like ordinary congestion to a legitimate user you caught by accident.

**Enforcement keyed on a fingerprint or an address.** Neither lasts. One decays, the other is shared by a whole CGNAT population. **The only durable unit of enforcement is the credential:** fingerprints and addresses feed the decision, but are never what it is applied to.

**A high-cardinality classifier that reaches the cache key.** You have destroyed your own cache with your own defence. Decide after the lookup, substitute on the way out, and mark per-recipient responses uncacheable.

**Detection with nothing to execute it.** If you can spot abuse mid-event but cannot interrupt it, you have built a dashboard. Interruption needs a recurring point where a decision can be applied, and with long-lived credentials that are never revalidated, that point does not exist. Better detection will not create one. It is common: in a 2024 live-sports study, **81% of illegal streams stayed up for the whole event.** Detection was rarely the missing piece. Execution was.

**Depth of enforcement instead of breadth.** The UK site-blocking studies are the best natural experiment: blocking one major site only moved users to other sites and VPNs, while blocking 19, and later 52, raised paid legal streaming by roughly 10-11%. Enforcement has a coverage threshold: below it you displace the abuse. Above it you convert users. That argues for spending on grouping and coverage, not on perfecting one detector.

**Enforcing before measuring.** There are no credible published false-positive baselines for any control here. Anyone quoting a precise percentage cannot support it for your traffic. Run every classifier in observe-only mode against your own logs first, long enough to see a weekend and a holiday.

---

## Cost, honestly

Marking is four line items that get collapsed into one and therefore estimated wrongly: preparation, storage and egress for the variants, per-delivery decisioning, and the detection service plus licensing.

A/B is the interesting case. Storage doubles while egress does not, because the whole population shares the same two variants. Caching still works, only the object count grows.

Per-request validation has a cost profile people get backwards. The cryptography is never the bottleneck; an HMAC check is microseconds. Invocation overhead at the edge dominates.

That overhead decides whether you can afford a decision per object, or only per manifest, per index, per catalogue call - which is also the boundary of what you can interrupt mid-session.

## If I were designing this today

I would start with measurement, not a product.

The five features from the access logs - network diversity, request patterns, activity over time, delivered versus entitled volume, and client-identity consistency - are already in your access logs. No request-path changes. Within days, you know which problem you actually have.

Make the threat model explicit, including a column for **what we choose not to address**.

The analog hole goes there. If a legitimate user can render the artifact, they can capture it. A determined abuser usually can too. That boundary keeps the rest of the budget honest.

Keep **interruption** and **attribution** as separate systems, with separate owners. Interruption needs short-lived credentials and renewal. Attribution needs a discovery-to-takedown loop. They fail independently and should be built independently.

Build in this order:

1. **Measure.** Existing logs, observe-only. *(interruption)*
2. **Shorten the credential.** Create the decision point. *(interruption)*
3. **Grade the response.** Throttle and step up before denying. *(interruption)*
4. **Classify.** Protocol-level scoring for cheap tooling. *(interruption)*
5. **Mark.** Only when the capacity works for your artifacts. *(attribution)*
6. **Discover.** Only when someone owns the path to takedown. *(attribution)*

The first four are cheap. The last two cost real money.

Every classifier stays a score feeding a graduated decision, never a gate.

## References

- Jarad, Bicakci, *When Handshakes Tell the Truth*, arXiv:2602.09606, 2026
- Gomez-Boix et al., *Hiding in the Crowd*, WWW 2018
- ETSI TS 104 002, forensic A/B watermarking (DASH-IF), 2023
- Danaher, Smith, Telang, *The Effect of Piracy Website Blocking on Consumer Behavior*, 2018

---
title: "Designing the system that starts after authorization"
date: 2026-08-18T20:00:00+02:00
tags: ["security", "fingerprinting", "watermarking", "anti-piracy", "system-design", "architecture"]
categories: ["engineering"]
description: "The engineering half: requester fingerprinting ranked by what a forgery costs, the watermark capacity arithmetic that decides whether marking can work at all, content fingerprinting as a search problem, and the two loops that get confused for one."
draft: false
---

This is the second half of a pair. [Part one](/blog/content-piracy-by-authorized-users/) covered the problem: why the abuser usually holds valid access, the four shapes that abuse actually takes, and the three unrelated technologies that all get called fingerprinting.

Four things from it carry over, and they are all you need to read on:

- An **artifact** is whatever you deliver: a stream, a document, a dataset, a build, an image catalogue, a set of weights.
- Abuse takes four shapes. **Sharing** and **leeching** are still moving through your infrastructure, so they can be **interrupted**. **Mirroring** and **republication** are already over when you find out, so all that is left is **attribution**.
- Those are two separate systems with different latency budgets, and merging them is the most common architectural mistake here.
- **Requester fingerprinting** serves the interruption side. **Recipient marking** and **content fingerprinting** serve the attribution side, as a pair.

What follows is the engineering. Each technology gets taken apart, then wired back together into something you could actually build.

## Fingerprinting the requester

Start on the interruption side, with the only technology that serves it.

A fingerprint is just a set of details about the caller that you did not ask them to send. Their software leaks it by existing.

The useful way to think about the layers is not accuracy. It is **what a forgery costs the abuser**.

![The signal stack ranked by cost to fake, from TLS up to platform attestation](/images/antipiracy-signal-stack.png)

Note the inversion in that picture. The two layers vendors talk about most are the two cheapest to defeat.

### The layers you can read without any help from the client

When a client opens a TLS connection, its first message lists the version, the ciphers it supports, the extensions and the curves. Different software produces a different list.

**JA3** hashed that list into one short string, so you could recognise the same software again later.

It worked until January 2023. Chromium began permuting the order of TLS extensions on every connection, and within days nearly every Chrome connection was producing a different JA3 value.

**JA4** fixed that by sorting the fields before hashing. It restored stability. It did not make the fingerprint hard to fake, and that difference is the whole story of this layer.

There are two neighbouring layers worth collecting:

- **The TCP handshake** leaks initial TTL, MSS, window size and the order of TCP options. Coarse - it gives you an operating system family, not a device. But it is written by the kernel, not by the abuser's code, which makes it harder to change.
- **HTTP/2** adds the SETTINGS values and their order, the first flow-control update, the PRIORITY frames, and the order of pseudo-headers. The scheme comes from an Akamai white paper, which reported browser families separable at 99.7% on the HTTP/2 fingerprint alone. In practice it often discriminates better than TLS does.

How well does this work? Recent academic work trained gradient-boosted classifiers on JA4 features over roughly 200,000 labelled records from JA4DB, reporting near-perfect separation on its own test set: AUC around 0.998, F1 around 0.973.

Read the setup before believing the number. A record was labelled bad-bot when the client's application field contained "bot". So the model learned to recognise software that announces itself, which is a much easier problem than recognising software that lies.

The authors say where it fails, in plain terms. It fails against Puppeteer, Playwright and Selenium, because those drive a real browser binary and inherit a real browser's TLS stack. It fails against libraries written to mimic a target fingerprint on purpose. Their own conclusion is that JA4 "is not a standalone authentication or attribution mechanism".

So this layer separates cheap tooling from real browsers very well, and a motivated abuser from a real browser not at all. `curl-impersonate`, `curl_cffi` and `uTLS` reproduce a target browser's cipher list, extension order and HTTP/2 settings in a single call.

One asymmetry survives, and it is the most useful thing here.

**A spoofer normally fakes one layer at a time.** A bot on a Linux host can present a flawless Chrome-on-Windows TLS fingerprint and still emit Linux TCP values, because the kernel wrote those.

So do not hunt for one good fingerprint. Look for contradictions between layers. JA4T captures the TCP half, which is why the pair is worth more than either piece.

One caveat: the contradiction only exists while the abuser imitates a platform he is not running on. Once he runs the real browser on the real OS, it disappears.

### The layers that need the client's cooperation

Where you can run code, the surface widens: canvas and WebGL output, audio behaviour, font lists, screen metrics, timezone, memory, the list of supported codecs.

This layer is oversold. Three studies show why.

- **2010, Panopticlick:** 83.6% of 470,161 fingerprints were unique.
- **2016, AmIUnique:** 89.4% of 118,934 were unique, and 81% of the mobile ones.
- **2018, *Hiding in the Crowd*:** 2,067,942 fingerprints from a top-15 French commercial site, and only **33.6% were unique. On mobile, 18.5%.**

The gap is sampling, not noise. The early datasets came from sites that attract privacy-minded visitors running unusual software. The last one came from an ordinary commercial audience, which is exactly the population you serve.

So plan against the last row. Two thirds of desktop fingerprints and more than four fifths of mobile ones are shared with somebody else. Mobile is the weakest case, and mobile is where consumer abuse mostly lives.

Stability is the second problem. Longitudinal work saw at least one change within a single day for 45.5% of devices. Linkage held about 52 days on average, and past 100 days for roughly a quarter of them.

**A fingerprint is an identifier that decays.**

The third problem is not technical at all. In the EU, fingerprinting falls under Article 5(3) of the ePrivacy Directive, the same provision that governs cookies. The EDPB said so explicitly in its Guidelines 2/2023 on the technical scope of that article, and the point is that storing nothing on the device does not exempt you.

Anti-abuse is a defensible legal basis, but only for a specific, documented purpose. Put retention and purpose limits into the feature store on day one.

Platform attestation belongs in a different box entirely. Play Integrity and App Attest do not ask whether you look like the real client. They ask you to **prove** you are, and the platform signs that proof over your signed binary.

That is the one question a copied client cannot answer, which makes it the answer to the emulated-client entry route rather than to anything on this list. It is also narrow: strong on mobile, absent on the web and most embedded targets. Use it when issuing credentials, not on the delivery path.

### The layer that actually pays

Here is the part that gets underbuilt, and it is the cheapest thing in this post.

Almost every useful signal about an account is already sitting in your access logs:

- distinct network prefixes and networks under one credential in a rolling window
- concurrency counted per **consumer**, not per session object, since one session object can have any number of people behind it
- request rate and access order against plausible behaviour, because a sequential sweep of a whole catalogue is a scraper by construction
- coverage of the clock, because an account active 24/7 across four timezones is not a person
- delivered volume against entitled volume
- how many distinct device fingerprints show up under one credential over time

One published critique is worth internalising. Concurrent-session limits only fire when sessions overlap. The dominant sharing pattern is **staggered in time**.

Two people sharing one subscription who never watch at the same moment will never trip a concurrency check. Accumulating device and location history over a window, fourteen days in one published approach, builds a case instead of judging a single session.

Why does this layer win? Cost again.

Defeating a TLS fingerprint costs one library call. Defeating a behavioural profile means genuinely behaving like N ordinary users: renting N plausible network paths and slowing your own operation down to human speed.

That bill recurs. It is the only lever here that raises the abuser's ongoing cost rather than his setup cost.

### Where the request comes from

The class of network - home, mobile, hosting, VPN, relay - is a strong signal for both leeching and mirroring, because bandwidth economics push resale into datacenters. The IPTV research is evidence for its own countermeasure, since those operations were renting mainstream hosting.

Residential proxies blunt it completely, for a per-gigabyte fee a paying pirate can absorb.

One rule follows, and it is worth stating flatly. **Never bind a session to an exact IP address.**

Carrier-grade NAT puts hundreds of real subscribers behind one address. Dual-stack clients switch address families mid-session. Relays rotate exit points.

Bind to the prefix instead, a /24 or a /56. Allow a few changes per session. Prefer a re-authentication prompt over cutting somebody off.

### The turn: group, do not accuse

This is the part that changed how I think about the whole category.

A fingerprint is weak as an accusation and strong as a way to **group sessions together**. It answers "is this the same actor as before?" much better than "is this actor a pirate?"

And a faked fingerprint is faked the same way every time. So the fake itself becomes a grouping key.

Two consequences follow, and both are cheap.

**First: the pirate is also your client.** Whatever pulls your content on their behalf has a fingerprint on the lower layers. You will not recognise it as pirate software up front.

But once you isolate it by any means - a behavioural flag, an abuse report, a watermark hit - that fingerprint retroactively identifies every other session it ever opened. One incident becomes a population.

**Second: their infrastructure fingerprints too.** Threat-intelligence work on one IPTV network started from a single domain and reached more than 10,000 IP addresses and 1,100 domains.

The links were mundane: shared hosting patterns, shared DNS records exposing co-hosted services, a repeated portal URL shape like `/get.php?username=...&password=...&type=m3u`, and registration history.

Grouping hundreds of resellers back to one upstream is worth far more than blocking any one of them. The enforcement numbers later explain why.

## Marking the copy

Now the attribution half, which is what you are left with once **mirroring** or **republication** has already happened.

Marking writes a per-recipient identifier into the artifact. A copy found anywhere then traces back to the recipient it was issued to. It also attributes a leech, since your bytes reach their audience carrying their session mark - but slowly, which is why the interruption half is the better answer there.

Where the text says *chunk* below, read it as whatever unit your artifact is already split into: a video segment, a page, a shard.

There are four places to put the mark. They differ in cost and in how much you must trust the client, not in what they achieve.

| Where the mark goes in | How it works | Cost | Trust needed in client |
|---|---|---|---|
| Per-recipient generation | a unique artifact rendered per recipient | grows with N | none |
| Variant composition (A/B) | two marked variants per chunk, assembled into a per-recipient sequence | storage doubles once, delivery flat | none |
| Recipient-side embedding | trusted code on the device applies the mark | almost none | high |
| Delivery-time embedding | injected per request at the serving tier | CPU per request, breaks caching | none |

Per-recipient generation stops scaling in the hundreds, which is still fine for review copies, licensed datasets and per-customer builds. Delivery-time embedding is flexible and expensive, because a per-recipient response cannot be cached.

Recipient-side embedding is the one to watch. It is the only option where the abuser controls the thing doing the marking. Unless it runs somewhere he cannot reach, such as a hardware-backed execution environment, he turns it off - and you find out when an unmarked copy appears.

That leaves variant composition, the only option with an interoperable standard.

![How A/B variant marking produces many recipient identities from two stored variants](/images/antipiracy-ab-marking.png)

DASH-IF's Forensic A/B Watermarking, published by ETSI as **TS 104 002** in August 2023, defines the roles and the interfaces between them.

A preprocessor emits an A and a B variant of every chunk. The packager carries the metadata through the pipeline. The edge does the sequencing: it derives a bit position from the chunk identifier, reads that bit out of the identifier in the request token, and serves the matching variant.

Strip the domain vocabulary and a general technique remains. **If an artifact can be chunked, two marked variants plus a per-recipient selection sequence give you N identities from 2 stored copies.**

Per-page document variants and per-shard dataset variants work exactly the same way.

### The failure mode that will not show up on a dashboard

The security of the whole scheme rests on one thing that is easy to get wrong.

**The token carrying the identifier must be integrity-protected and bound to the session.**

If a client can edit that token, it can request the all-A sequence and make itself unattributable. That is a quieter failure than an outage, and nothing will alert on it.

So the edge must fail closed on a bad or missing token. And both variants must be encrypted under the same key, so switching between them stays invisible to the player.

### Mark at every handoff, not just at the end user

One decision is worth making early and is usually made late.

A per-partner mark applied when you hand an artifact to a distributor, plus a per-session mark on your own delivery path, gives you a two-level search.

A leak carrying partner X's mark but no session mark means the loss happened inside X. Different conversation, different contract clause, and usually the more damaging case.

### The arithmetic to run before any procurement call

Three lines, for each class of artifact you ship.

```text
  bits available   =  f(artifact surface, robustness margin)
  bits needed      =  log2(recipients) + collusion margin + ECC
  material needed  =  bits needed / bits per chunk
                      ->  the time or size it takes to attribute
```

For A/B composition the middle term is about one bit per chunk. So two-second chunks give 30 bits per minute, four-second chunks 15, six-second chunks 10.

Work it through for a real population:

- ten million recipients is 24 bits, before anything else
- add error correction so the identifier survives partial recovery, and you are in the thirties
- add any collusion margin, and you are past forty
- at four-second chunks, forty-odd bits is about three minutes of *clean* recovered material, and more wall clock than that in practice

Now compare that to how long the content is worth stealing. Vendors advertise attribution in around three minutes for live material. The window everyone in live enforcement works to is **30 minutes**: it is the deadline Italy's Piracy Shield imposes on ISPs, and the ceiling an EU study proposed for notice and takedown on live streams.

So the budget is 30 minutes end to end, and three of them are gone before you even know whose account it was. The rest has to cover capture, extraction, the registry lookup, a decision, and somebody acting on it.

That is why **chunk size is an anti-piracy parameter**, not just a latency and caching one. At four-second chunks a forty-bit identifier needs about 2.7 minutes of clean material; at six-second chunks the same identifier needs 4. You spend that difference out of the same 30.

The same arithmetic gives the hard limit of the technique. **Fragments cannot be attributed.** A thirty-second clip, a two-hundred-row extract, one lifted function - not enough surface to carry an identifier that survives anything.

If your real loss is fragments, marking is the wrong purchase, and no vendor engineering changes that.

### Collusion, and why it scales badly

Several recipients can compare their copies, then average or splice them.

In an A/B scheme this is cheap to attempt and easy to reason about: two subscribers splicing their sequences produce a third sequence that decodes to an innocent third party.

The countermeasure is anti-collusion coding, and Tardos codes are the reference family. Required code length grows on the order of `c^2 * ln(n/e)`, for `c` colluders in a population of `n` recipients at false-accusation probability `e`.

The quadratic term is the part to design around. Tardos proved it is unavoidable, not an artefact of his construction. Only the constant has moved: his original 100 is down to roughly 4.93, with 2 as the asymptotic floor.

Design to that scaling law, not to a vendor datapoint.

One related detail. Extraction happens under loss, and loss is the normal case. Spread the identifier's weight evenly across its bits. Schemes with a few structurally important bits fail badly when exactly those go missing.

### Robustness, and the registry behind it

| Medium | The transformations that matter |
|---|---|
| Video, audio, images | re-encode, rescale, crop and letterbox, screen capture, camcording, overlay, clipping |
| Documents | reflow, format conversion, OCR round-trip, retyping, paraphrase |
| Datasets | row sampling, shuffling, dropping columns, joining against another source |
| Software, model weights | recompilation, symbol stripping, obfuscation, quantisation, fine-tuning |

The mark has to be invisible, and being invisible is exactly what makes recovery probabilistic. That is the shape of the technology, not a flaw to engineer away.

**Marking prevents nothing. It changes the odds of being identified, and so the economics of leaking.**

It also depends entirely on the mapping from recipient to identifier, and that registry is the part teams underbuild.

It is the most sensitive database you own, since its whole purpose is turning an identifier into a person. Its retention window caps how far back you can attribute anything, and accusing the wrong customer from a corrupted registry is far worse than a leak you never attributed.

## Finding the leak: content fingerprinting

The attribution half has one more prerequisite. Marking answers "whose copy is this" only if something first tells you that a copy exists at all.

That is content fingerprinting, working in the opposite direction.

It derives a small, change-tolerant descriptor from the artifact and matches it against an index of your own catalogue: perceptual hashes for images and frames, spectral peak patterns for audio, shingling for text, similarity metrics for compiled code.

It works because a small change to the artifact produces a small change in the descriptor, so re-encoding and resizing do not break the match.

Three realities decide whether it earns its cost:

- **It is a search problem, not a hashing problem.** The descriptor is easy. The index is the engineering. Nearest-neighbour search over a large catalogue at crawl volumes is where the money goes, which is why this layer is usually bought rather than built.
- **Its ceiling is geometric, not cryptographic.** Weak perceptual hashes fall over on a horizontal flip, heavy cropping, large overlays, or your content composited into a bigger frame. That last one is exactly what a leech or a mirror operator does when they wrap your feed in their own branding.
- **It cannot tell infringement from licensed use.** A match is a location, not a verdict. Your affiliate, your syndication partner and a pirate all produce matches. Separating them is a metadata problem in your rights system.

Used well, this layer produces a queue of locations ranked by audience, each a candidate for capture and mark extraction. Used badly, a report nobody reads.

## Putting it together: designs that hold up

Back to the two halves from part one, this time with their internals. Interruption and attribution are pipelines of different length, and only one of them runs while you can still change the outcome.

![The interruption loop and the attribution loop, with their different latencies and owners](/images/antipiracy-two-loops.png)

Before the failure list, the mapping that decides what you build. Symptoms here are ambiguous, and the same one points at different controls depending on which reading is true.

| What you see | Likely reading | What helps | What will not help |
|---|---|---|---|
| One credential, many networks, never at the same time | **sharing**, staggered in time | device and location history over a window; per-seat binding | concurrency limits |
| One credential, volume far above entitlement | **leeching** - an audience being served off your infrastructure | per-object validation, session binding, throttling | access control; marking works but is the slow path |
| Your artifact on third-party hosts, your egress flat | **mirroring** or **republication** after one legitimate fetch | marking, plus content fingerprinting to find it | anything at request time |
| A perfect client fingerprint, implausible access pattern | an emulated client - an entry route, not one of the four shapes | attestation at issuance, token integrity, cross-layer consistency | any single fingerprint, marking |
| Cheap tooling in your logs | opportunistic scraping, below all four shapes | protocol-layer classification, graduated response | attestation, marking |
| Fragments only, nothing longer than a minute | clipping, outside what marking can reach | monitoring, then accept it | marking - not enough surface |

The right-hand column is the useful one. Most wasted spend here is a correct control bought for the wrong reading of a symptom.

Now the failures, which are predictable enough to list.

**Allow or deny at the edge, keyed on a classifier.** As brittle as the classifier's false-positive rate, which you do not know. Graduated response survives its own mistakes instead: throttling or capping quality changes timing rather than correctness, and looks like ordinary congestion to a legitimate user you caught by accident.

**Enforcement keyed on a fingerprint or an address.** Neither lasts. One decays within days, the other is shared by a whole CGNAT population.

**The only durable unit of enforcement is the credential.** Fingerprints and addresses feed the decision. They are never what it is applied to.

**A high-cardinality classifier that reaches the cache key.** You have destroyed your own cache with your own defence. Decide after the lookup, substitute on the way out, and mark per-recipient responses uncacheable.

**Detection with nothing to execute it.** If you can spot abuse mid-event but cannot interrupt it, you have built a dashboard. Interruption needs a recurring point where a decision can be applied, and with long-lived credentials that are never revalidated, that point does not exist. Better detection will not create one.

The live-sports numbers show how common this failure is. A 2024 study by the Live Content Coalition and Grant Thornton found that **81% of illegal streams stayed up for the whole event, and only 2.7% were taken down inside the 30-minute window.** Detection was rarely the missing piece. Execution was.

**Depth of enforcement instead of breadth.** The best natural experiment available is the UK site-blocking sequence, and the numbers are worth knowing:

- blocking one major site: a small drop in piracy, and **no** increase in legal use, because people moved to other sites and to VPNs
- blocking 19 sites at once: a real drop, plus an 11% average rise in paid legal streaming among affected users
- blocking 52 sites later: roughly 10% more subscription use and 11.5% more ad-supported use

**Enforcement has a coverage threshold.** Below it you displace the abuse. Above it you convert users. That argues for spending on grouping and coverage, not on perfecting one detector.

**Enforcing before measuring.** There are no credible published false-positive baselines for any control here. Anyone quoting a precise percentage cannot support it for your traffic.

Run every classifier in observe-only mode against your own logs first, long enough to see a weekend and a holiday.

## Cost, honestly

Marking is four line items that get collapsed into one and therefore estimated wrongly: preparation, storage and egress for the variants, per-delivery decisioning, and the detection service plus licensing.

A/B is the interesting case. Storage doubles while egress does not, because the whole population shares the same two variants. Caching still works, only the object count grows.

Per-request validation has a cost profile people get backwards. The cryptography is never the bottleneck; an HMAC check is microseconds. Invocation overhead at the edge dominates.

That overhead decides whether you can afford a decision per object, or only per manifest, per index, per catalogue call - which is also the boundary of what you can interrupt mid-session.

## Lessons learned

- **The abuser usually has valid access.** Card sharing servers exist because the encryption works. Any strategy built mainly on access control addresses the smaller half of the problem.
- **Sort the abuse by whether a copy has already left.** Sharing and leeching can be interrupted. Mirroring and republication can only be attributed. A control bought for the wrong half is wasted money.
- **Keep the entry route on its own axis.** A valid credential behaving badly and an emulated client are different problems with different answers, and calling both of them redistribution is how the wrong control gets funded.
- **Rank signals by what a forgery costs, not by lab accuracy,** and look for contradictions between layers, since spoofers fake one at a time.
- **A fingerprint groups sessions; it does not identify a person,** and it decays. Uniqueness figures from self-selected datasets do not transfer: 33.6% on desktop and 18.5% on mobile is what a real audience looks like.
- **Marking is attribution with a probability attached, and its unit is the chunk.** Fragments are permanently out of scope, and the registry resolving an identifier to a person is both the real system and the real liability.
- **Detection with no executor is a dashboard,** enforcement has a coverage threshold, and anything sold as making an attack impossible is sold to the wrong buyer. Measure in observe-only first; the baselines you need are published nowhere.

## If I were designing this today

I would build the measurement pipeline before evaluating a single product.

Four features per credential - distinct network prefixes, request pattern against plausible behaviour, delivered versus entitled volume, and consistency of client identity within a session - come straight out of existing access logs. They need no change to the request path, and within days they tell you which problem you actually have.

I would also write the threat model as a table with an explicit column headed "we are choosing not to address this".

The analog hole belongs in that column. If a legitimate party can render the artifact, they can capture it. So, for most services, does the fully determined abuser. Naming those cases out of scope is what makes the rest of the budget defensible.

I would split interruption and attribution into two subsystems with two owners, because they fail independently and get merged in every vendor conversation. Interruption needs a short credential lifetime with renewal, which is cheap and retrofittable. Attribution needs a discovery and extraction loop with an agreed turnaround, which is an operational commitment rather than a purchase.

And I would build in this order, because each step tells you whether the next one is worth funding:

1. **Measure.** Behavioural features over existing logs, observe-only. *(interruption)*
2. **Shorten the credential.** Create the checkpoint where any decision can later be applied. *(interruption)*
3. **Grade the responses.** Throttle and step up before you ever deny. *(interruption)*
4. **Classify at the protocol layer,** as a score, for the commodity tier only. *(interruption)*
5. **Mark**, but only after the capacity arithmetic says it can work for your artifacts. *(attribution)*
6. **Discover**, and only once somebody owns the takedown path end to end. *(attribution)*

The first four are cheap and stop the two shapes you can still catch in the act. The last two cost real money and only pay off once somebody owns the path from a match to a takedown.

Every classifier stays a score feeding a graduated decision, never a gate. The credential stays the only key enforcement is applied to.

## References

- Danaher, Smith, Telang, *The Effect of Piracy Website Blocking on Consumer Behavior*, CMU IDEA, 2018
- *Iniquitous Cord-Cutting: An Analysis of Infringing IPTV Services*, Damon McCoy et al.
- Gomez-Boix et al., *Hiding in the Crowd*, WWW 2018, and Laperdrix et al., *Browser Fingerprinting: A Survey*, 2019
- Vastel et al., *FP-Stalker: Tracking Browser Fingerprint Evolutions*, IEEE S&P 2018
- Jarad and Bicakci, *When Handshakes Tell the Truth: Detecting Web Bad Bots via TLS Fingerprints*, arXiv:2602.09606, 2026
- Shuster, *Passive Fingerprinting of HTTP/2 Clients*, Akamai white paper, Black Hat EU 2017
- FoxIO, JA4+ network fingerprinting specification
- DASH-IF Forensic A/B Watermarking, published as ETSI TS 104 002 V1.1.1 (2023-08)
- Tardos, *Optimal Probabilistic Fingerprint Codes*, and the later literature reducing its leading constant
- EDPB Guidelines 2/2023 on the technical scope of Article 5(3) of the ePrivacy Directive
- Live Content Coalition and Grant Thornton, live sports piracy takedown study, 2024

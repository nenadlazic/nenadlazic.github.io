---
title: "Content piracy by authorized users: a threat model that survives contact with reality"
date: 2026-08-14T09:00:00+02:00
tags: ["security", "anti-piracy", "threat-modeling", "system-design", "architecture"]
categories: ["engineering"]
description: "Piracy at scale is a distribution business built on legitimate access, not a broken cipher. The four shapes abuse actually takes, the one question that splits your architecture in two, and the three unrelated technologies people keep calling fingerprinting."
draft: false
---

Imagine you sell access to something you make. A live sports feed, a market research report, a licensed dataset, a per-customer software build, a set of model weights - it does not matter which. People pay you every month, and that revenue is the whole business.

You have done the security work, too. Nothing leaves your servers unencrypted. Every request has to prove who it belongs to. Links expire in seconds rather than days. What each customer can reach is checked against what they actually paid for.

Somebody reviewed all of it and signed it off.

![A security review scoped entirely to the door, while the copy walks out through it](/images/antipiracy-the-lock-works.png)

Now picture one particular customer.

They log in from one home, on one device, at ordinary hours. They never share a password, never trip a rate limit, never appear in two countries at once. On every dashboard you own, this account is a model citizen.

They are also reselling what you send them to four hundred other people.

No password was stolen. No cipher was broken. Nothing in that review was wrong. The account is exactly what it claims to be, and that is the whole problem.

This post is about the part of the system that begins after the login succeeds.

## The shape every content business ends up with

One careful decision at the door, then thousands of deliveries that never question it again.

A subscription is checked once, and three thousand segments follow. A licence box is ticked, and forty gigabytes of model weights follow. A contract is signed, and a dataset lands on a laptop where it will quietly live forever.

The decision at the door is the part everybody reviews. The thousands of deliveries behind it are the part nobody owns.

I will call the thing you deliver an **artifact**: a stream, a document, a dataset, a build, an image catalogue, a set of weights. Everything below applies to all of them.

### Four ways that gap gets used

These are worth separating, because they cost you different things and they need different controls.

{{< hl amber >}}Sharing.{{< /hl >}} One credential, several people, usually at different times of day. Your authorization is working correctly. There are simply too many people standing behind one of them.

{{< hl amber >}}Leeching.{{< /hl >}} One valid credential pulls, and the puller forks that stream out to an audience of its own in real time. Your infrastructure does the delivering. Nothing is ever stored anywhere. You lose the sale *and* you pay the egress bill for viewers who are not your customers.

{{< hl amber >}}Mirroring.{{< /hl >}} They fetch once through a valid account, keep a copy, and serve their own audience from their own infrastructure. You lose the sale, but not the bandwidth.

{{< hl amber >}}Republication.{{< /hl >}} The artifact simply leaves and turns up somewhere else, whole. A file on a locker, a dataset in a public repo, a build on a forum.

The last three all get called "redistribution" in industry conversations, which is exactly why that word is no use as a label. It hides the only two distinctions that matter: whose infrastructure pays, and whether a copy still exists by the time you find out.

Two questions tell you which one you are looking at. The first of them decides your whole architecture.

![Decision tree splitting the four abuse shapes by whether the artifact is still moving through your infrastructure](/images/antipiracy-decision-tree.png)

> **The dividing line:** sharing and leeching are still happening on your infrastructure while you are looking at them, so they can be **interrupted**. Mirroring and republication are already over by the time you find out, so the only thing left is **attribution**.

Two different systems, then. Different latency budgets, different owners, independent failure modes.

Most bad design in this field comes from treating them as one, and most wasted spend comes from buying a control that belongs to the other half.

### How they got in is a separate axis

The four shapes describe what happens to the delivery once somebody is inside. They say nothing about how that somebody got inside, and those are independent questions.

Entry comes in roughly four flavours: a credential they paid for, a credential somebody shared with them, a **client they emulated**, or a token they forged or replayed.

That third one is worth calling out, because it is the case people most often file under redistribution when it does not belong there. If an emulated client is pulling your content, access control was not answered correctly - it was **defeated**. The distribution that follows is a consequence, not the problem.

It also has entirely different countermeasures. Behavioural scoring and per-object validation are the answer to a valid credential behaving badly. An emulated client is answered by platform attestation, by tokens whose integrity you can actually verify, and by keeping no signing secret in the client at all.

Both axes matter, and they multiply: any entry route can feed any of the four shapes. Both posts keep them apart.

The rest of this post stays at that level: what the business on the other side actually looks like, and the three technologies people confuse when they try to answer it. The engineering detail - signal layers, watermark capacity arithmetic, what to build in which order - is in [part two](/blog/anti-piracy-designing-after-authorization/).

## The business on the other side

Start with the thing that surprises people: piracy at scale is not a hacking story. It is a distribution business.

The best measurements come from video, because that is where researchers bought subscriptions and took notes. An academic study of paid pirate IPTV services mapped the whole operation.

It looks like a normal company:

- an ingest headend built from off-the-shelf TV tuner cards
- a middleware vendor handling subscriber management and billing
- sellers, who run the storefront
- resellers, who buy credits and never touch the infrastructure at all
- customers, paying by card or crypto

They rent hosting like anyone else. In the measured sample, some rented commercial CDN capacity from mainstream providers. One of the larger services reportedly had around 180,000 subscribers.

Now the detail that should reshape your threat model.

Next to the tuner cards sits a **card sharing server**. Its only job is to distribute valid decryption keys to clients that are not entitled to them.

Nobody broke the cipher. Somebody with legitimate access shared the key, and a business grew on top of that.

### This is not a video problem

Change the medium and the story survives intact.

A consultancy forwards your paid research to three clients: **sharing**. One API key quietly fronts a competitor's free service: **leeching**. A licensee mirrors your dataset onto their own infrastructure: **mirroring**. A per-customer build turns up on a forum: **republication**.

Same four shapes, no video anywhere. In every one of those cases access control worked exactly as designed. It was asked whether this party may open the artifact. It answered correctly, and the answer was yes.

### So what is left to ask?

Three questions, and the door answers none of them:

- **Who is this, really?** Everything on the interruption side depends on this one.
- **Whose copy is this?** Where attribution begins.
- **Is this artifact even ours?** Without an answer here, attribution never gets the chance to run.

None has a clean answer. All three have a useful one, as long as you know what you are buying.

One last thing before the technologies. Fix the goal. You are not going to eliminate this behaviour, you are managing how much of it happens. Your two levers are the abuser's cost per unit of abuse, and your time to respond.

## Three technologies, one word

Almost every confused conversation in this field comes from the word "fingerprinting" carrying three unrelated meanings.

![Requester fingerprinting, recipient marking and content fingerprinting compared](/images/antipiracy-three-technologies.png)

In plain terms:

**Requester fingerprinting** looks at the connection and the account. It tries to tell whether this caller is the same one as last time.

**Recipient marking**, usually called watermarking, hides a serial number inside the artifact itself. Every recipient gets a slightly different copy.

**Content fingerprinting** takes a copy found somewhere in the wild and asks whether it belongs to your catalogue at all.

The distinction that costs real money is between the last two. Marking tells you whose copy leaked, but not where it went. Content fingerprinting tells you where a copy is, but not who put it there.

You need both to close a loop. Buying one while believing you bought the other is the most expensive mistake here.

Mapped onto the two halves from earlier: requester fingerprinting is the whole interruption side, while marking and content fingerprinting are the attribution side, and they only work as a pair.

## Where this goes next

That is the map. What it deliberately does not contain is any of the engineering.

[**Part two: designing the system that starts after authorization**](/blog/anti-piracy-designing-after-authorization/) takes each of the three technologies apart:

- **Requester fingerprinting** layer by layer, ranked by what a forgery costs the abuser rather than by lab accuracy - and the published uniqueness numbers that show where it hits a ceiling.
- **Marking**, including the four places you can insert it, the capacity arithmetic that decides whether it can work for your artifacts at all, and the token failure that makes a recipient unattributable without alerting anything.
- **Content fingerprinting** as the discovery layer, and why it is a search problem rather than a hashing one.
- **The synthesis**: a table mapping the symptom you see to the control that helps, the failure modes worth knowing before a procurement call, honest costs, and the order I would build in today.

## Reference

- *Iniquitous Cord-Cutting: An Analysis of Infringing IPTV Services*, Damon McCoy et al.

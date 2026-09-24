---
title: "High availability: what actually happens when things fail"
date: 2026-09-24
tags: ["high-availability", "reliability", "distributed-systems", "kubernetes", "architecture"]
categories: ["engineering"]
description: "HA is not a replica count. It is the path traffic and state take to the surviving side: the two levels of HA, why DNS and service addressing decide failover, why state is the real problem, and how to audit it honestly."
cover: "/images/og/high-availability-what-happens-when-things-fail.png"
draft: false
---

Every architecture document I have reviewed says "HA" somewhere. Very few say what happens, step by step, when the thing it protects actually dies.

Here is a failure that is more common than it should be. A platform runs on two Kubernetes clusters in two data centres, primary and backup. Every service is marked HA. Then the primary site loses its uplink.

Nothing moves. The public DNS record still points at the dead cluster, because switching it is a manual change nobody has rehearsed. The backup cluster has most services running, but the message broker they depend on lives only on the primary site. And redeploying anything on the backup side needs the secret store and the image registry, both of which run on the primary.

Every component was "HA". The system was not.

This post is about the difference. My working definition: **high availability is not a replica count. It is the path that traffic and state take to the surviving side, and whether that path has been walked before it is needed.**

## Two levels of HA, and what neither of them covers

"HA" in a design document usually means one of two different things, and mixing them up causes most of the wrong assumptions.

![Two levels of HA: replicas inside a cluster, deployments across clusters, and the shared dependencies underneath both](/images/ha-two-levels.png)

| Level | What it is | Protects against | Does not protect against |
|---|---|---|---|
| 1 | more than one replica inside one cluster | a pod or a node dying | the cluster, the site, a shared database or broker |
| 2 | the service deployed on two clusters or sites | a whole cluster or site going down | anything both sides depend on |

Level 1 is cheap and mostly automatic: the orchestrator restarts pods and the load balancer drops dead endpoints. Level 2 is where the real work is, because traffic, service discovery and state all have to move together.

A service with one replica deployed on both clusters has level 2 but not level 1. It survives a site failure, eventually, after someone switches it, but a routine pod restart is an outage. A service with five replicas on one cluster has level 1 but not level 2. Both get called HA.

Neither level says anything about dependencies. **A service is exactly as available as the least available thing it cannot work without.**

### A vocabulary that makes the audit honest

"Is it HA?" gets a yes or a no, and the yes hides everything. Two columns per component give a real answer.

**Topology** - where it runs:

- **active/active** - both sides serve traffic
- **active/passive, hot** - both sides run, one gets the traffic
- **active/passive, cold** - the backup has the objects, scaled to zero
- **not deployed** - nothing on the backup side
- **single site** - there is no backup side

**Failover class** - what it takes to move:

- **automatic** - health checks and routing move traffic on their own
- **scale + DNS** - someone scales up the backup and switches a record
- **deploy + DNS** - someone first has to deploy it
- **data promotion** - a replica has to be promoted, or data is restored or lost
- **not possible**

Filling that table for every component of a real platform is humbling. Most rows land in "scale + DNS" or worse, and the few "automatic" ones tend to be the ones somebody was once burned by.

## How traffic finds the surviving side

Most active/passive setups move external traffic with DNS: one hostname, one record, pointing at the active cluster. Failover means changing the record. Three details decide whether that works.

**A plain record does not fail over.** If the service dies but the cluster is up, requests still arrive, the ingress finds no ready endpoints and answers 503. It does not forward to the other cluster; it does not know there is one.

**A health-checked record checks a URL, not your system.** DNS-level failover probes one endpoint from outside and moves traffic when that URL fails, which may or may not be when your users are failing.

**TTL is a floor, not a guarantee.** After the switch, resolvers and clients keep the old answer for at least the TTL, and some keep it much longer. A 60-second TTL does not mean a 60-second failover.

Inside the cluster, the same decision is made by the **readiness** probe, not liveness. Readiness removes a pod from the endpoints; liveness only restarts it. A liveness probe that fails when a dependency is down turns one broken database into a restart storm.

## How services find each other

External traffic is the visible half. The half that usually breaks is service-to-service calls.

![A call chain A to B to C where C fails on the primary, and what each addressing mode does](/images/ha-service-chain.png)

Take a chain: a client calls A, A calls B, B calls C. Everything is deployed on both clusters, traffic is on the primary. Now C dies on the primary only. Whether the chain keeps working depends entirely on the address B uses for C:

| B calls C via | What happens |
|---|---|
| a cluster-local service name | resolves only inside the primary; B keeps calling the dead C and fails |
| an external hostname | you can switch only C's record: partial failover, cross-site latency on every call, and C on the backup needs healthy dependencies of its own |
| a multi-cluster (global) service in a mesh | endpoints in both clusters; when no local pod is ready, calls go to the remote one immediately, with no DNS and no TTL |

The first row is the default almost everywhere, and its consequence is worth stating plainly: **in active/passive with cluster-local addressing, the unit of failover is the cluster, not the service.** One service without level 1 takes down the functionality of the whole primary, and the only way out is to move the entire stack.

The mesh option has a trap of its own. Many ingress controllers balance directly across pod IPs from the local endpoint list instead of going through the service IP, so external traffic never sees the remote endpoints and still gets a 503. The mesh covers pod-to-pod calls; check separately that the ingress path uses it.

## State is the real problem

Stateless services are the easy part. Every hard failover conversation ends at state.

**The database.** A common shape is one database cluster stretched across both sites: a primary with streaming replicas on the other side, and services reaching it through an alias. That is a good design, because failover is promoting a replica and repointing the alias, with no redeploys. Two questions decide how good it really is. Is replication synchronous? The default usually is not, so the recovery point is whatever lag existed at the moment of failure. And is promotion automated, or a procedure that lives in one person's head?

**The message broker** is the hidden single point of failure. Two independent broker clusters, one per site, look redundant. But if every client has one site's brokers in its configuration and nothing replicates between them, losing that site means lost in-flight events and a redeploy of every producer and consumer.

Cross-cluster replication fixes most of that, at a price:

- it is asynchronous, so the recovery point is the replication lag
- it delivers duplicates, so consumers must be idempotent
- consumer offsets differ between the clusters and must be translated
- if messages carry only a schema ID, the registry on the other side must know the same IDs, or consumers cannot deserialize a single message

**Per-cluster state** - caches, analytical stores, object stores, local volumes - is lost on failover unless it is replicated. For a cache that is fine. For anything else it should be a conscious row in the table, not a surprise.

**The control plane of recovery.** The secret store, the image registry and the CI system are rarely in anyone's HA scope, yet every recovery step goes through them. If they live only on the primary, the backup can run what it already has, but it cannot deploy, pick up new secrets or pull a new image. That is the failure from the opening, and it is the one I would check first.

## Singletons, and electing a leader across two clusters

Some services cannot run twice. The causes are mundane: scheduled jobs that would execute on every replica, volumes that allow a single writer, state kept only in memory, a deployment strategy that stops the old pod before starting the new one.

Most of these are fixable, and the fix is almost always the same: **move the coordination into something both sides already share.**

- **Request handling** needs no leader at all if the state is in the database. Any instance on either cluster can serve.
- **Scheduled work** needs exactly one executor, and the right place for that lock is the shared database: a lock table, an advisory lock, or row claiming with `SKIP LOCKED`. When the primary dies, the lock expires and the backup takes over, without anyone having to know who the leader was.
- **Not a Kubernetes lease.** A lease lives in one cluster's API server, so each cluster elects its own leader, and you are back to two.

If a leader must also receive requests because of in-memory state, you can make non-leaders report not-ready so only the leader has endpoints. It works, at a cost: failover takes the lock TTL plus a probe period, rollouts stall, and the backup always looks unhealthy. Moving the state into the database is nearly always cheaper.

## Failure modes worth expecting

- **The cold standby drifts.** A backup scaled to zero is updated by nobody who watches it. Months later it runs versions behind, with configuration that points at systems which no longer exist.
- **Split primaries.** After one incident, some services move to the backup site and never move back. Each site is now primary for half the stack, and every call between the halves crosses sites.
- **Secrets that fail to sync on the backup side** stay invisible until the day a redeploy there is actually needed.
- **Failover that was never run.** An untested failover is a hypothesis. The procedures that work are the ones with a documented order - what to scale down first, what to bring up last - and a date on which someone last ran them.

## What it costs

Level 1 is cheap: more replicas, and the work of making the service safe to run twice. Level 2 roughly doubles the stateless footprint if the backup is hot, and costs almost nothing if it is cold. That is exactly why cold backups are so common, and why they drift.

The real cost is not compute. It is **cross-site state**. Synchronous replication adds a round trip between sites to every write; asynchronous replication buys that latency back with a recovery point greater than zero; and every replicated broker or store is one more system to operate and monitor. That trade-off belongs to whoever owns each data set, decided per data set, not by default.

## If I were designing this today

I would start by writing down what "HA" means for the platform, as a checklist instead of an adjective. A service is HA only if all of this holds:

1. it can run as more than one instance at the same time - no unguarded scheduled jobs, no single-writer volumes, no state only in memory
2. everything it depends on is available on the backup side
3. there is a defined way for traffic to move - a health-checked route, or a documented and tested switch
4. it runs at least two replicas per cluster

**The replica count is a consequence, not the goal.**

Then I would fill in the topology and failover-class table for every component, including the ones nobody thinks of as components: DNS, secrets, the registry, CI. The rows marked "not possible" are where the real architecture discussion starts.

And I would put a failover exercise in the calendar. Not because it will go well the first time, but because it will not.

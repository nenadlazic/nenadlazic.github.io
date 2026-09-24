---
title: "NUMA: the performance bug that never throws an error"
date: 2026-07-31T09:00:00+02:00
tags: ["numa", "performance", "linux", "systems-programming", "memory", "video-encoding"]
categories: ["engineering"]
description: "NUMA is the failure mode where everything keeps working, nothing reports a fault, and you quietly pay a third of your hardware budget for nothing. How it happens, and how to catch it."
cover: "/images/og/numa-the-performance-bug-that-never-throws.png"
draft: false
---

Two identical servers. Same binary, same config, same input. One delivers roughly 30% less throughput than the other, yet both sit at 100% CPU utilization. No errors, no warnings, nothing in the logs. The difference is where the memory lives.

This is a post about NUMA, written for engineers who have never had to care about it, and for those who have and got bitten anyway. I will start from the hardware, but the part worth your time is the failure modes near the end. NUMA is one of the very few problems where everything keeps working, nothing reports a fault, and you quietly pay a third of your hardware budget for nothing.

## Memory used to be simple

For a long time, the mental model was simple: the CPUs sit on one side, RAM on the other, and every core has roughly the same cost when accessing memory. That is **UMA** - Uniform Memory Access. As more CPU cores and sockets were added, however, they all had to share the same path to memory, turning memory bandwidth into a bottleneck.

The solution was to give each CPU socket (a physical processor package on the board, not a network socket) its own local memory. This increased both total capacity and available bandwidth, but introduced an important trade-off: memory is no longer equally close to every CPU. Accessing memory attached to your own socket is faster, while accessing memory attached to another socket takes longer. That is **NUMA** - Non-Uniform Memory Access.

![UMA versus NUMA memory topology](/images/numa-uma-vs-numa.png)

Everything below is a consequence of that trade-off.

## What the distance matrix actually tells you

The machine will tell you its own topology:

```text
$ numactl --hardware
available: 2 nodes (0-1)
node 0 cpus: 0-31,64-95
node 0 size: 257838 MB
node 1 cpus: 32-63,96-127
node 1 size: 257997 MB
node distances:
node   0   1
  0:  10  32
  1:  32  10
```

Two things worth knowing about that matrix, because it is routinely misread.

**Those numbers are firmware's opinion, not a measurement.** They come from the ACPI SLIT table (System Locality Information Table, a relative-distance matrix the BIOS hands to the OS): `10` conventionally means local memory, while `32` tells the OS that remote memory is roughly three times as costly. But this is only a hint from the BIOS, not a benchmark. In practice, remote latency on a two-socket system is often closer to 1.5-2x local latency.

**Bandwidth is the bigger problem.** A modern socket can get hundreds of GB/s from its local DDR5 memory, while the inter-socket link provides only a fraction of that. Latency can often be hidden with prefetching and multiple in-flight requests; a saturated interconnect cannot. Under load, remote memory access can therefore hurt performance far more than the raw latency difference suggests.

{{< accent >}}A simple way to picture it: local memory is a drawer in your own desk; remote memory is asking a colleague across the office to fetch from theirs. The reaching is not the expensive part - the walk, and the wait when they are busy, are.{{< /accent >}}

## Why compute-heavy workloads feel this so badly

Most software barely notices NUMA because its hot working set fits in cache. Memory-bound workloads are different, and video encoding is a good example.

A single 1080p 8-bit 4:2:0 frame is about 3.1 MB (`1920 x 1080 x 1.5`). But an encoder does not hold one frame - it keeps a lookahead window and multiple reference frames in memory. With 25-40 frames in flight, plus motion vectors, partition trees, cost maps, and other metadata, a single encode instance easily reaches a substantial hot working set:

```text
~30 frames x 3.1 MB   ≈   95 MB of frame buffers
+ internal structures ≈   ~2x that in practice
                      ─────────────────────────
1080p encode instance ≈   150-250 MB of hot working set
```

For UHD the numbers get larger still: one frame is about 12.4 MB, so a single instance can push well beyond **1 GB**. That is far larger than the cache available to any individual core.

Worse, video encoding has relatively poor memory locality: motion estimation repeatedly reads scattered regions from large reference frames, so much of that data has to come from DRAM rather than cache. Now add NUMA. If those reference frames live on the other socket, every one of those reads pays the higher remote latency and competes for the limited inter-socket bandwidth. With many encoders running at once, this stops being a small optimization and becomes a major throughput bottleneck - roughly a third less work from the same hardware.

The same principle applies well beyond video: large working sets that overflow cache and have poor locality are highly sensitive to NUMA placement - graph traversal, in-memory analytics, simulations, and the like.

## The silent failure: the thread moves, the memory does not

Linux manages memory in fixed-size **pages** (4 KB by default, or 2 MB where transparent huge pages apply - which makes every placement decision, and every later migration, that much coarser), and places each one with a **first-touch** policy: the physical RAM backing a page is allocated on the NUMA node of the thread that first *writes* to it - not at `malloc`, but at the first real access. So a process that starts on socket 0 allocates and touches its buffers there, and they land in RAM 0: local and fast. Then the scheduler moves the thread to another socket - socket 0 got busy, or for a reason you do not control. The memory does **not** follow.

![First-touch allocation and the silent migration that strands the memory](/images/numa-first-touch-migration.png)

The root cause is that two things are decided independently: **first-touch** fixes where the memory lives, and the **scheduler** decides where the thread runs - and nothing keeps the two aligned. The thread never chose remote memory; it simply walked away from its own. This matters most for exactly the workload from the last section - a large working set that lives in DRAM, spread across many threads the scheduler is free to shuffle between sockets.

Everything still works. Output is identical, and every core still shows 100% busy in `htop` - a core stalled on a remote fetch is not an idle core. You just get lower throughput per box than you should - fewer jobs on the same hardware - and write it off as "what this hardware does."

**That is the whole problem in one sentence: it gets slower, and nothing reports an error.**

CPU utilization is useless here - a stalled core and a busy core look the same from up there. For the real signal, watch `numa_miss` and `other_node` climb in plain `numastat` (system-wide counters, per node), check where one process's pages actually sit with `numastat -p <pid>`, or measure remote traffic with `perf` uncore counters.

## The fix: take the choice away from the scheduler

The fix is to re-couple the two decisions the OS made separately: pin the process and its threads to one node's cores, and bind their memory to that same node, so compute and data never drift apart. (A NUMA node here is a set of cores plus its local memory - you bind to the node, not necessarily to a single core.)

![Pinning threads and memory to the same node](/images/numa-pinned-fix.png)

You need both knobs. **CPU affinity** alone keeps the thread put but lets its memory land anywhere; **memory policy** alone places the memory but lets the thread wander off. Do only one and you have mostly wasted the effort. `libnuma` does both, and `numactl` is its command-line front end. (This assumes the workload fits inside one node - see *The traps* below for when it does not.)

The kernel does have automatic NUMA balancing that migrates pages toward a thread (or a thread toward its pages) to reduce remote access. It helps, but for heavy, many-threaded workloads it is best-effort and reacts after the fact - explicit pinning is what you actually rely on.

For a quick sanity check you do not need to touch the application at all:

```bash
numactl --cpunodebind=0 --membind=0  ./my_workload ...
```

That reads as: run `my_workload` only on the cores of NUMA node 0 (`--cpunodebind=0`), and allocate all of its memory on node 0 (`--membind=0`) - compute and data forced onto the same node.

If that alone shifts throughput by 20-30%, you have your answer, and the rest is about doing it properly instead of by hand. If it changes nothing, NUMA is not your bottleneck - stop here.

## Wiring it into a process

There are two ways that pinning actually reaches a process, and it is worth being clear on which you are using.

**Externally, with `numactl`.** It wraps a process at launch and pins the whole thing to a node - no code changes. This is enough when an entire process belongs on one node, which is exactly how you run several instances side by side, one per node:

```bash
numactl --cpunodebind=0 --membind=0  ./worker   # instance on node 0
numactl --cpunodebind=1 --membind=1  ./worker   # instance on node 1
```

**In-process, with `libnuma`.** When a single process needs finer control - different threads on different nodes, or specific buffers placed deliberately - the application links `libnuma` and calls its API itself: pin a thread with `numa_run_on_node()` (or `pthread_setaffinity_np`), and place its memory with `numa_set_membind()` or `numa_alloc_onnode()`. `libnuma` is a thin wrapper over the kernel syscalls that do the real work (`sched_setaffinity`, `mbind`, `set_mempolicy`); a container's `cpuset` cgroup is a third layer that limits which nodes the process may touch at all.

However you wire it, you are always configuring the same two things: **where threads run** and **where memory is allocated**.

## The traps

Everything above is textbook. This is the part that actually costs you, because each trap produces the same symptom: slower, no error.

### One socket does not mean no NUMA

Firmware can split one physical socket into several NUMA nodes - AMD calls it **NPS** (NUMA Per Socket), Intel calls it Sub-NUMA Clustering. So a single-socket machine can be a NUMA machine, and a two-socket machine can present eight nodes.

![One physical socket presenting multiple NUMA nodes via NPS / Sub-NUMA Clustering](/images/numa-nps-subnuma.png)

The practical rule: read `NUMA node(s)`, never `Socket(s)`.

```bash
lscpu | grep -E "^Model name|^Socket|^NUMA node"
```

### Strict binding can OOM a half-empty machine

Pinning assumes one thing that nobody states out loud: that the workload *fits* inside a single node. One node on the machine above holds ~256 GB, so an instance with a 400 GB working set has no node to be pinned to, and the question stops being *which* node and becomes *how to spread*.

This is also the one loud failure in a post full of quiet ones. `--membind` is strict: when the bound node runs out, the allocation fails and the process is killed - even with hundreds of gigabytes free on the other node. A half-empty machine OOM-killing a workload is confusing exactly until you remember the policy is doing what you asked.

Two softer policies exist for the cases where strict binding does not fit:

```bash
numactl --cpunodebind=0 --preferred=0   ./worker   # prefer node 0, fall back instead of dying
numactl --interleave=all                ./worker   # spread pages round-robin across all nodes
```

`--preferred` keeps the locality benefit but degrades to remote memory rather than failing. `--interleave` gives up locality on purpose: every node's memory gets used and both memory controllers carry traffic, so you trade the best case for a predictable average. That is the right trade for a working set too large to localize, or for a many-threaded process you cannot cleanly partition - and it is a real answer, not a consolation prize. The failure mode it removes is the one that actually hurts: all the hot data stranded on one node while every socket reads from it.

### Verify that it was applied, not that it was configured

"Configuration was sent" and "pinning happened" are different claims. A run where pinning silently did nothing looks identical to a healthy one in CPU% and output, so do not trust the config - inspect the running process directly, on both halves.

**Are the threads on the node?** `ps` reports the CPU each thread last ran on (the `psr` column); check those against the node's CPU list:

```bash
ps -L -o tid,psr,comm -p <pid>            # psr = current CPU, per thread
numactl --hardware | grep 'node 0 cpus'   # which CPUs belong to node 0
```

Every thread's `psr` should fall inside that node's CPU list. (`taskset -acp <pid>` shows the same as an affinity mask.)

The CPU list itself is worth a look, because hyperthreading usually splits a node into two ranges:

```text
$ numactl --hardware | grep 'node 0 cpus'
node 0 cpus: 0 1 2 3 ... 30 31 64 65 66 ... 94 95
```

So node 0 owns `0-31` and `64-95` (node 1 gets `32-63` and `96-127`). Now hold a real, scattered process against that:

```text
$ ps -L -o tid,psr,comm -p 40127
    TID PSR COMMAND
  40127  14 worker        # cpu 14  -> node 0
  40163  73 worker        # cpu 73  -> node 0
  40188 104 worker        # cpu 104 -> node 1   <-- other node
```

Two threads on node 0, one on node 1: this process is not pinned. Its threads span both sockets, so whichever node holds its memory, the ones on the far side are reading remotely - the silent tax, live.

**Is the memory on the node?** `numastat` has two faces, and they answer different questions. With `-p` it breaks one process's pages down per node:

```bash
numastat -p <pid>          # this process: how many MB on each node
numastat                   # whole machine: numa_hit / numa_miss / other_node
```

A correctly pinned process shows nearly all its memory on one node in the `-p` view; if the pages are split across nodes, the memory is remote no matter what you configured. `/proc/<pid>/numa_maps` gives the same per-mapping (`N0=... N1=...`). The miss counters live in the bare `numastat` output, not the `-p` one - so run it before and after a load test and watch whether `numa_miss` and `other_node` are still climbing while the workload runs.

These two checks - threads inside the node's CPUs, pages on that node - are the only place the difference between "configured" and "applied" actually shows.

## When NUMA stops being your problem

It is just as important to know when NUMA tuning is unnecessary. A modern single-socket server can expose everything as one node:

```text
1 socket · 96 cores · 192 threads · NUMA node(s): 1
```

With a single node, all memory sits in the same NUMA domain: no remote memory, no inter-socket link to cross, and usually nothing worth pinning. The right amount of NUMA tuning here is zero. And this is increasingly common - a single package now packs dozens of cores and a large pool of memory, so a good share of the fleet has no NUMA topology to tune at all.

The rule stays the same either way: **check the topology before you tune placement, and verify it afterwards.** Everything above lives between those two checks.

## Takeaways

1. **NUMA is a property of the machine, not a feature of your software.** `lscpu` first, opinions second - and read `NUMA node(s)`, not `Socket(s)`.
2. **The failure is always silent.** It gets slower; nothing errors. No alert will find it, and CPU utilization will actively lie, because a core stalled on remote memory looks perfectly busy.
3. **Pin threads and memory.** Doing only one is close to doing neither.
4. **Responsibility is smeared across layers** - orchestration decides placement, the application applies it, the kernel enforces it - and each layer can drop it independently of the others. The symptom is identical every time.
5. **If you did not verify it at runtime, it did not happen.** A version in a config file, a green build, and "we passed the parameter" prove nothing. The machine is the only witness that counts.

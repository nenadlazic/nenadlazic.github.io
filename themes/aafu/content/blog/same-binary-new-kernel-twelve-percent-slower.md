---
title: "The OS upgrade that quietly ate 12% of the CPU"
date: 2026-11-04
tags: ["linux", "kernel", "scheduler", "performance", "numa", "multithreading"]
categories: ["engineering"]
description: "An OS upgrade made a heavily multithreaded, CPU-bound workload burn 12% more CPU for identical work. Same instructions, lower efficiency, and every usual suspect ruled out one at a time until only the kernel was left."
cover: "/images/og/same-binary-new-kernel-twelve-percent-slower.png"
draft: false
---

Two identical servers run the same binary on the same live input. One needs about 12% more CPU to do it. Nothing errors, the output is identical, every dashboard is green. The only difference is the operating system: Ubuntu 20.04 with kernel 5.15 on one, Ubuntu 24.04 with kernel 6.8 on the other.

Twelve percent sounds small until you size a fleet with it: roughly one extra machine in eight, just to stand still. Nobody budgets for an OS upgrade making the same work more expensive.

The short version: it is the kernel, the most likely mechanism is how newer schedulers place threads on a CPU with many small caches, and the usual quick fixes did not help. The fix is still in progress and will land in the last section of this post.

## The setup

The workload is a demanding multithreaded process doing intensive computation over a continuous data feed. Several independent instances run side by side on each machine, each with 100-150 threads and 6-7 cores of load. It is CPU-bound, memory-heavy, and works on far more data than fits in any CPU cache, so where that data sits in memory matters.

The hardware is a server with two first-generation AMD EPYC processors (Zen 1): 64 cores and 128 hardware threads in total. What matters for this story is how those cores are grouped, because the groups decide how far a core is from the data it needs.

![Two sockets, eight NUMA nodes with their own RAM, sixteen CCXs with their own L3 cache](/images/zen1-topology.png)

Read it from the bottom up:

- A **CCX** (core complex) is a group of 4 cores sharing one L3 cache, the last and largest cache on the chip. Data in it is close and fast. A core in another CCX cannot use it.
- A **NUMA node** is a group of cores with its own memory attached. Its cores reach that memory directly; memory attached to another node is reachable too, but slower. ([More on NUMA here.](/blog/numa-the-performance-bug-that-never-throws/))
- A **socket** is one physical processor. Going from one socket to the other is the longest trip of all.

So this machine has not one big cache but sixteen small ones, and not one pool of memory but eight. As long as a thread stays on the same cores, its data stays close. When the operating system moves the thread to a core in another CCX, it starts with an empty cache. When it moves the thread to another NUMA node, it also leaves its memory behind and reads it from a distance from then on.

## Measuring 12% without fooling yourself

Comparing CPU graphs over a day does not work here, because **the input drives the cost**. Some data is simply more expensive to process, and CPU per process swings by 20-30% from one minute to the next.

So the input has to cancel out. Both machines process the same four feeds at the same time with the same binary, CPU per process is read from `/proc/<pid>/stat` over the same 60-second window on both, and only the **ratio** counts. Absolute numbers drift; the ratio was stable to within a few points.

```bash
# CPU cores used by each worker process over 60 s (utime + stime)
for p in $(pgrep -f worker); do echo "$p $(awk '{print $14+$15}' /proc/$p/stat)"; done > /tmp/a
sleep 60
for p in $(pgrep -f worker); do echo "$p $(awk '{print $14+$15}' /proc/$p/stat)"; done > /tmp/b
join /tmp/a /tmp/b | awk '{printf "%s %.2f cores\n", $1, ($3-$2)/100/60}'
```

Baseline: **+11.8%** on the newer OS, with every instance showing about the same gap.

### Same work, done slower

CPU time says *that* something is slower, not *why*. The CPU's hardware counters can answer that, and `perf stat` reads them from a running process without touching it. Four of them matter:

- **instructions** - how much work the program did
- **cycles** - how many clock ticks that work took
- **IPC** (instructions per cycle) - how efficiently the CPU got through the work; it drops when the CPU sits waiting, mostly for data from memory
- **cache misses** - how often data was not in the fast on-chip cache and had to come from slower memory

Measured on both machines over the same 60 seconds, counting only the application's own code (not time spent in the kernel):

| | Old OS (5.15) | New OS (6.8) | |
|---|---|---|---|
| instructions | baseline | -0.2% | same work |
| cycles | baseline | +11% | took longer |
| IPC | 1.45 | 1.30 | 10% less efficient |
| cache misses | baseline | +5-6% | small increase |

The new system does not run more code - no extra security path, no library doing more work. It runs the same instructions about 10% slower, and almost all extra cycles are in the application, not the kernel. The kernel is not burning the CPU; something it does makes everyone else slower.

Keep one number in mind for later: cache misses rose only 5-6%, which on its own does not explain a 10% efficiency drop.

## Ruling things out, one at a time

An OS upgrade changes hundreds of things at once. The only reliable way through is one change per test, both machines measured at the same moment.

| Suspect | Test | Gap after |
|---|---|---|
| CPU security mitigation (SRSO) | turned off with `spec_rstack_overflow=off` | +12.3% |
| CPU microcode | booted with the older microcode | +12.3% |
| glibc and toolchain | binary rebuilt on the new OS | still there |
| NUMA placement | each process pinned to 2 NUMA nodes | +8.7% |
| hyperthreading (SMT) | both machines pinned to physical cores only | +13.6% |
| that particular kernel | kernel 6.14 instead of 6.8 | +10.5% |

The security mitigation was the first suspect, since the older kernel does not have it at all. Turning it off changed nothing; neither did the microcode. Rebuilding the binary on the new OS did not close the gap either (that build was also a newer version of the code, so not a perfect test, but enough to rule out "built on the old system").

One test nearly fooled me. Pinning the processes to physical cores on the new machine alone dropped the gap to +3.4%, which looked like a fix. It was not: that pinning makes this workload cheaper on *any* machine, and with the same pinning on both, the gap was back at +13.6%. **An optimisation applied to only one side of a comparison is not a result.**

## The kernel swap

Two explanations were left: the kernel, or this particular machine - BIOS settings, memory layout, firmware. The test that separates them: keep the new OS, change only the kernel.

| Kernel on the new-OS machine | CPU vs the old-OS machine |
|---|---|
| 6.8 (release default) | +12% |
| 6.14 (newer hardware-enablement kernel) | +10.5% |
| **5.15 (from the previous long-term release)** | **~0%, every instance within ±2%** |

Same machine, same userspace, same binary, same microcode. With 5.15 the difference is gone. The machine is fine; the gap follows the kernel. (The 5.15 result comes from four clean 60-second windows rather than fifteen, for a reason described below. All four agreed.)

## What the scheduler does differently

The scheduler keeps per-thread statistics that can be read without any tracing: time spent waiting for a CPU (`/proc/<pid>/task/*/schedstat`) and the number of moves between cores (`/proc/<pid>/task/*/sched`). Sampling which core each thread ran on once per second also shows how often it changed NUMA node.

| Per process | 5.15 | 6.8 | 6.14 |
|---|---|---|---|
| time waiting for a CPU | ~8 ms/s | ~32 ms/s | ~8 ms/s |
| moves between cores | ~390/s | ~500-550/s | ~450/s |
| on a different NUMA node than 1 s earlier | ~49% * | ~68% | ~52-62% |

*The 6.8 column was measured with a newer build of the same application; 6.14 and 5.15 with the binary used everywhere else in this post. \* The 5.15 figure in the last row is from the old-OS machine; the swapped machine on 5.15 was not sampled cleanly for it.*

**Wait time was a red herring.** On 6.8 threads waited four times longer for a CPU, on a machine only 17% busy, and that looked like the answer. Then 6.14 brought wait time back to the 5.15 level while the CPU gap stayed at 10.5%.

**Moves are the signal that tracks the gap.** Both 6.x kernels move threads more often, and more often across NUMA nodes. On 5.15 the numbers match the old machine exactly.

The likely mechanism follows from the topology. A thread that changes CCX loses its warm cache; one that changes NUMA node now reads its memory remotely. Same instructions, data further away, lower efficiency. It fits the counters with one honest gap: cache misses rose only 5-6%, so either remote and cross-CCX accesses cost more than a miss counter shows, or something else is involved too. This is a hypothesis, not yet a proof.

The prime suspect for *why* placement changed is the scheduler itself. In kernel 6.6 Linux replaced CFS, its scheduling algorithm for sixteen years, with a new one called EEVDF, and thread placement and load balancing changed along with it. Zen 1, with sixteen small caches and eight NUMA nodes in one box, is about as sensitive to placement as x86 hardware gets.

## Traps along the way

Swapping kernels on a remote server is where most of the actual risk was. Three traps, each of which would have cost a trip to the remote console:

**The network driver was not in the kernel package.** Ubuntu splits kernel modules into a base package and an `-extra` package, and this server's network card driver lives in `-extra`. The metapackage for the newest kernel did not pull `-extra` in, so installing it as suggested would have produced a machine that boots without network. Check where your network and storage drivers live before rebooting into a new kernel:

```bash
dpkg -S $(modinfo -n <nic_driver>)    # which package ships the running driver
```

**Firmware compression.** Newer Ubuntu compresses firmware with zstd, which the original 5.15 could not read. The build used here had it backported (`CONFIG_FW_LOADER_COMPRESS_ZSTD=y`), but on an old kernel with a new userspace, check it rather than assume it.

**GRUB boots the newest kernel.** An older kernel never becomes the default on its own. A one-shot boot keeps the test reversible: if it does not come up, a power cycle returns to the known-good kernel.

```bash
sudo sed -i 's/^GRUB_DEFAULT=.*/GRUB_DEFAULT=saved/' /etc/default/grub
sudo update-grub && sudo grub-set-default 0
sudo grub-reboot "Advanced options for Ubuntu>Ubuntu, with Linux 5.15.0-203-generic"
```

And one measurement trap: halfway through the 5.15 run, an extra and much heavier job was started on only one of the two machines, and from then on the new machine looked *13% faster*. Any load that is not the same on both sides turns the ratio into noise.

## What it costs, and the options

For capacity planning the result is blunt: on this CPU generation, a heavily multithreaded CPU-bound workload loses about 10-12% of its capacity on 6.x kernels.

| Option | Gain | Cost |
|---|---|---|
| stay on 5.15 with the new userspace | back to baseline | unsupported combination, security fixes only from the older kernel line |
| accept it and re-plan capacity | none | ~10-12% more machines on this generation |
| tune the scheduler on 6.x | not known yet | runtime settings, careful measurement |
| pin each process to one NUMA node | not known yet | placement logic in orchestration or the application |

Coarse pinning to two NUMA nodes is already ruled out, because the scheduler could still move threads between four CCXs inside that set. Next up: pinning each process to a single node, scheduler settings that make the kernel more reluctant to move a thread with a warm cache, and a comparison of kernel 6.5 (the last with CFS) against 6.6.

Newer CPU generations have larger caches and fewer NUMA nodes, so the effect may be smaller there. That is not measured yet, so I would not generalise beyond Zen 1.

## Lessons learned

1. **An OS upgrade is a performance change.** Measure the same workload before and after, on the same hardware, with the same binary. Nothing in the logs will tell you.
2. **Compare ratios measured at the same moment.** When the input drives the cost, numbers from two different hours are noise.
3. **One change per test, applied to both sides.** The one time that rule was bent, it produced a fake fix.
4. **The first strong signal is not always the cause.** Wait time looked like the answer on 6.8 and vanished on 6.14 while the gap stayed.
5. **A kernel change is an infrastructure change, not a package update.** Check drivers, firmware and the boot path first, and keep a way back that does not need someone in the data centre.

## The fix

*Work in progress. This section will be updated once the fix is measured.*

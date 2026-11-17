# Exp 0429 candidate R: the console's "a lower number wins" for the guest's sleeping threads (design, not built)

Written 2026-11-17 during the maintainer's play, with no box access. Facts about rtkit and the kernel are
TODO(verify) until the read in section 4.

## 1. What it should copy
On the console a woken Hi job worker (priority 500) takes its CPU at once from any lower-priority thread there: the Lo
workers (600), Havok (550/700), Bink, the background (750). On the host a woken worker waits behind them (equal nice,
or nice steps that only change shares). In h429Z1 18 % of the job-semaphore wakes took 0.1–2 ms, and the owner's help
(priority 300, spinning on its own CPU) takes the job meanwhile. R gives the woken guest worker the CPU at once, the
way the console does, and no title row is needed.

## 2. The rule (any title, derived at run time)
- **Who gets SCHED_RR:** a guest thread **after its first sleep on a guest semaphore, event flag or condition wait**
  (a sleeper), and only while its guest priority is below the console's default thread priority, 700
  (TODO(verify): the default; the title's own threads show 700 as Havok's and Bink's start). So the title's job workers
  qualify, and its background and default-priority threads do not.
- **RR priority from the guest priority, order kept:** rr = 1 + (700 − guest_priority) × (maxrr − 1) / 700, with maxrr
  from rtkit (section 4). A lower guest number gives a higher RR priority. The owner (300) is a spinner and is excluded
  by the next rule, whatever its number.
- **Spinners never keep it:** a thread that runs under RR for longer than the bound without blocking is dropped back to
  SCHED_OTHER **for good** (a per-thread flag), and the drop is logged once. The owner's `pause` loop is such a thread.
  So is any title's busy-waiter.
- **Off by default, one switch:** `KYTY_BC5_0429_RR=1`. It is combined with `KYTY_BC5_0429_GUEST_CPUS=1` in the arms
  that test the console's whole model, and is also run alone.

## 3. The bound (the top's constraint 2: no RR thread may freeze the box)
Three layers, each enough on its own:
1. **RLIMIT_RTTIME on the process.** It is required by rtkit anyway (TODO(verify): rtkit refuses without it).
   - Soft limit: 20 ms of RR CPU time without a blocking call. The kernel then sends SIGXCPU; the host's handler
     demotes every guest thread that is over its budget (each RR thread's runtime is read from `/proc/self/task/<tid>/schedstat`
     against its last block) and marks it as a spinner.
   - Hard limit: rtkit's RTTimeUSecMax (typically 200 ms). Past it the kernel kills the process. It is the last stop,
     never the plan.
   - TODO(verify): whether this kernel sends the RLIMIT_RTTIME SIGXCPU to the thread or the process; the handler must
     work either way.
2. **A host watchdog thread at SCHED_OTHER nice −15**, every 5 ms. For each RR guest thread it reads `/proc/self/task/<tid>/stat`.
   A thread in state R whose voluntary context switches have not moved for 10 ms is demoted and marked as a spinner.
   This works even if the signal path fails.
3. **The kernel's RT throttling** (`sched_rt_runtime_us`, 950000 of 1000000 by default, TODO(verify) on the box): an RR
   thread can never take more than 95 % of a CPU per second, so the host's own threads keep running even in the worst
   case.

Every promotion and demotion goes through one function, so a demotion can never be undone by a later wake. Threads
marked as spinners stay out for the rest of the process.

## 4. Getting RR without changing the system (the top's constraint 1)
- **First choice: rtkit (RealtimeKit1 on the system bus)**, already the host's fallback for nice (SDL). It needs no
  limits.conf, rtkit config or setcap change if its defaults suffice. TODO(verify): rtkit-daemon's usual defaults are
  MaxRealtimePriority 39, MinNiceLevel −15, RTTimeUSecMax 200000, and about 25 RR threads per user with a burst
  limit on the calls.
- **The R threads:** at most the title's Hi and Lo workers. Here that is 8 + 8 with GUEST_CPUS, or 5 + 5 without, so it
  fits. The build stops promoting at rtkit's per-user thread cap and logs it.
- **The burst limit:** calls are made only at a thread's first sleep, so they are spread over the start.
- **Second choice, only with his own word: RLIMIT_RTPRIO for his user.** If `ulimit -r` is already above 0,
  sched_setscheduler works directly with no rtkit; if it is 0, raising it is a system setting (limits.conf), and the top
  asks him.
- **The read, once he has finished (read-only, under BOX-LOCK, about 1 minute):**
  - `ulimit -r`, `ulimit -e` and `ulimit -t` in his session;
  - `busctl get-property org.freedesktop.RealtimeKit1 /org/freedesktop/RealtimeKit1 org.freedesktop.RealtimeKit1
    MaxRealtimePriority MinNiceLevel RTTimeUSecMax`;
  - `systemctl cat rtkit-daemon` (its arguments, for the per-user caps);
  - `cat /proc/sys/kernel/sched_rt_runtime_us /proc/sys/kernel/sched_rt_period_us`;
  - `uname -r` (whether SCHED_RR's slice and RT throttling are as on 7.3).

## 5. What a test looks like
Build 7 is build 6 plus R; the removal is already in it. Arms, on the long route with RT on:
- **RG** `RR=1` + `GUEST_CPUS=1`, against the stressed control **M**. M has crashed 3 of 4.
- Then **R** alone, against **C**.

The catcher stays: every promotion and demotion, the sleeper and spinner lists, and the job-semaphore wake bands. These
show directly whether the 0.1–2 ms tail is gone. A form survives when RG is clean over repeated sets while M keeps
crashing; then R alone is checked for fps against C. Counts are reported as counts (R13).

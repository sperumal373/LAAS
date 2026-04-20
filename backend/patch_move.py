f = open(r'C:\caas-dashboard\backend\nutanix_move_client.py', 'r', encoding='utf-8')
c = f.read()
f.close()

# Replace _compute_schedule_epoch to handle Move v2.2 behavior
old = '''def _compute_schedule_epoch(options):
    """
    Determine ScheduleAtEpochSec from migration options.

    options dict may contain:
      cutover_mode: "auto" | "scheduled" | "manual"  (default: "auto")
      cutover_datetime: ISO string e.g. "2026-04-20T02:00:00"  (for scheduled mode)

    Returns: integer epoch in nanoseconds for Move API
      0  = immediate auto-cutover after seeding completes
      -1 = manual (user must click Cutover in Move UI)
      N  = scheduled cutover at epoch N (nanoseconds)
    """
    mode = (options.get("cutover_mode") or "auto").lower().strip()

    if mode == "manual":
        return -1

    if mode == "scheduled":
        dt_str = options.get("cutover_datetime", "")
        if dt_str:
            try:
                dt = datetime.datetime.fromisoformat(dt_str)
                epoch_sec = int(dt.timestamp())
                return epoch_sec * 1_000_000_000  # nanoseconds
            except Exception as e:
                log.warning("Invalid cutover_datetime '%s': %s. Falling back to auto.", dt_str, e)
        # If no valid datetime, fall through to auto
        log.info("Scheduled mode without valid datetime, using auto-cutover.")

    # Default: auto-cutover (ScheduleAtEpochSec = 0)
    return 0'''

new = '''def _compute_schedule_epoch(options):
    """
    Determine ScheduleAtEpochSec from migration options.

    Move v2.2.0 behavior:
      - ScheduleAtEpochSec=0 is IGNORED by Move (treated as -1/manual)
      - ScheduleAtEpochSec=-1 means manual cutover from Move UI
      - ScheduleAtEpochSec=N (future nanosecond epoch) means scheduled cutover

    For "auto" mode, we schedule cutover 5 minutes in the future so Move
    has time to complete seeding before the cutover triggers automatically.

    options dict may contain:
      cutover_mode: "auto" | "scheduled" | "manual"  (default: "auto")
      cutover_datetime: ISO string e.g. "2026-04-20T02:00:00"  (for scheduled mode)
    """
    import time as _time
    mode = (options.get("cutover_mode") or "auto").lower().strip()

    if mode == "manual":
        return -1

    if mode == "scheduled":
        dt_str = options.get("cutover_datetime", "")
        if dt_str:
            try:
                dt = datetime.datetime.fromisoformat(dt_str)
                epoch_sec = int(dt.timestamp())
                return epoch_sec * 1_000_000_000  # nanoseconds
            except Exception as e:
                log.warning("Invalid cutover_datetime '%s': %s. Falling back to auto.", dt_str, e)
        log.info("Scheduled mode without valid datetime, using auto-cutover.")

    # Auto mode: Move v2.2 ignores 0, so we schedule cutover ~5 min from now.
    # This gives seeding time to begin; Move will auto-cutover at the scheduled time.
    # If seeding takes longer, Move waits until seeding finishes then cutovers.
    auto_delay_sec = 300  # 5 minutes
    future_epoch_ns = int((_time.time() + auto_delay_sec) * 1_000_000_000)
    return future_epoch_ns'''

if old in c:
    c = c.replace(old, new, 1)
    print("Replaced _compute_schedule_epoch")
else:
    print("ERROR: old text not found")

# Also update _describe_schedule for auto
old2 = '''def _describe_schedule(epoch_ns):
    """Human-readable description of the cutover schedule."""
    if epoch_ns == 0:
        return "Auto-cutover (immediately after seeding completes)"
    elif epoch_ns == -1:'''
new2 = '''def _describe_schedule(epoch_ns):
    """Human-readable description of the cutover schedule."""
    if epoch_ns == 0:
        return "Auto-cutover (immediately after seeding completes)"
    if epoch_ns == -1:'''
c = c.replace(old2, new2, 1)

# Update the ReadyToCutover auto message
old3 = '''                    if schedule_epoch == 0:
                        # Auto-cutover: Move should proceed automatically
                        log_fn(plan_id,
                               f"{ready_count} VM(s) ReadyToCutover - auto-cutover is configured, "
                               f"Move will proceed automatically...",
                               "system")
                    elif schedule_epoch == -1:'''
new3 = '''                    if schedule_epoch > 0 and schedule_epoch != -1:
                        # Scheduled/auto cutover
                        sched_dt = datetime.datetime.fromtimestamp(schedule_epoch / 1_000_000_000)
                        log_fn(plan_id,
                               f"{ready_count} VM(s) ReadyToCutover - cutover scheduled for "
                               f"{sched_dt.strftime('%Y-%m-%d %H:%M:%S')}. Move will proceed automatically...",
                               "system")
                    elif schedule_epoch == -1:'''
if old3 in c:
    c = c.replace(old3, new3, 1)
    print("Updated ReadyToCutover auto message")
else:
    print("WARNING: ReadyToCutover auto message not found")

# Remove the duplicate scheduled block that's now unreachable
old4 = '''                    else:
                        # Scheduled: cutover will happen at the scheduled time
                        sched_dt = datetime.datetime.fromtimestamp(schedule_epoch / 1_000_000_000)
                        log_fn(plan_id,
                               f"{ready_count} VM(s) ReadyToCutover - cutover scheduled for "
                               f"{sched_dt.strftime('%Y-%m-%d %H:%M:%S')}. Waiting...",
                               "system")'''
if old4 in c:
    c = c.replace(old4, '', 1)
    print("Removed duplicate scheduled block")

f = open(r'C:\caas-dashboard\backend\nutanix_move_client.py', 'w', encoding='utf-8')
f.write(c)
f.close()
print("Done!")

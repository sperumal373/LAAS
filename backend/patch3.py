f = open(r'C:\caas-dashboard\backend\nutanix_move_client.py', 'r', encoding='utf-8')
c = f.read()
f.close()

# Fix _describe_schedule - currently auto shows for epoch_ns==0 but auto now returns a future timestamp
old = '    if epoch_ns == 0:\n        return "Auto-cutover (immediately after seeding completes)"\n    if epoch_ns == -1:'
new = '    if epoch_ns == -1:'
c = c.replace(old, new, 1)

# Also add auto detection in describe (values > current time - 10 min are "auto")
old2 = '    if epoch_ns == -1:\n        return "Manual cutover (requires user action in Move UI)"'
new2 = '    if epoch_ns == -1:\n        return "Manual cutover (requires user action in Move UI)"\n    # Check if this is near-future (auto) vs far-future (scheduled)\n    import time as _t\n    if abs(epoch_ns / 1e9 - _t.time()) < 600:\n        dt = datetime.datetime.fromtimestamp(epoch_ns / 1e9)\n        return f"Auto-cutover (scheduled at {dt.strftime(chr(37)+chr(72)+chr(58)+chr(37)+chr(77))} after seeding completes)"'
c = c.replace(old2, new2, 1)

# Fix ReadyToCutover block
old3 = '                    if schedule_epoch == 0:'
new3 = '                    if schedule_epoch > 0:'
c = c.replace(old3, new3, 1)

# Fix the auto message
old4 = '                        # Auto-cutover: Move should proceed automatically\n                        log_fn(plan_id,\n                               f"{ready_count} VM(s) ReadyToCutover - auto-cutover is configured, "\n                               f"Move will proceed automatically...",\n                               "system")'
new4 = '                        # Scheduled/auto cutover\n                        sched_dt = datetime.datetime.fromtimestamp(schedule_epoch / 1_000_000_000)\n                        log_fn(plan_id,\n                               f"{ready_count} VM(s) ReadyToCutover - cutover scheduled at "\n                               f"{sched_dt.strftime(chr(37)+chr(72)+chr(58)+chr(37)+chr(77))}. Move will proceed automatically...",\n                               "system")'
c = c.replace(old4, new4, 1)

# Remove old duplicate scheduled block if present
old5 = '                    else:\n                        # Scheduled: cutover will happen at the scheduled time'
if old5 in c:
    # Find and remove this block
    idx = c.find(old5)
    end = c.find("system\")", idx) + len("system\")")
    c = c[:idx] + c[end:]
    print("Removed duplicate scheduled block")

f = open(r'C:\caas-dashboard\backend\nutanix_move_client.py', 'w', encoding='utf-8')
f.write(c)
f.close()
print("Patched!")

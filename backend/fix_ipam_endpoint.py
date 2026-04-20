"""Fix the ON CONFLICT bug in collect_ipam_now endpoint."""
import re

with open(r'c:\caas-dashboard\backend\main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the line with ON CONFLICT inside collect_ipam_now (after line 6200)
target_line = None
for i in range(6200, min(len(lines), 6280)):
    if 'ON CONFLICT (run_date) DO UPDATE SET' in lines[i]:
        target_line = i
        break

if target_line is None:
    print("ERROR: target line not found")
    exit(1)

print(f"Found ON CONFLICT at line {target_line + 1}: {lines[target_line].rstrip()}")

# The block to replace:
# Lines from the INSERT INTO ... through the end of the ON CONFLICT block
# We need to find the start of the INSERT statement for this endpoint
insert_start = None
for i in range(target_line - 10, target_line):
    if 'INSERT INTO snap_ipam_summary' in lines[i]:
        insert_start = i
        break

# The cur.execute(""" is one line before INSERT INTO
exec_start = insert_start - 1
print(f"cur.execute starts at line {exec_start + 1}: {lines[exec_start].rstrip()}")

# Find the closing of the execute call - it ends with the params line + ))
# Find the line with 'subnets_warning))' after target_line
exec_end = None
for i in range(target_line, target_line + 20):
    if 'subnets_warning))' in lines[i] or ('subnets_warning' in lines[i] and '))' in lines[i]):
        exec_end = i
        break

print(f"execute ends at line {exec_end + 1}: {lines[exec_end].rstrip()}")

# Build the replacement lines
new_block = [
    '            cur.execute("DELETE FROM snap_ipam_summary WHERE run_date = %s", (today,))\n',
    '            cur.execute("""\n',
    '                INSERT INTO snap_ipam_summary\n',
    '                    (run_date, total_subnets, total_ips, used_ips, free_ips,\n',
    '                     reserved_ips, utilisation_pct, subnets_critical, subnets_warning,\n',
    '                     collected_at)\n',
    '                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())\n',
    '            """, (today, total_vlans, total_ips, used_ips, free_ips,\n',
    '                  reserved_ips, util_pct, subnets_critical, subnets_warning))\n',
]

# Replace lines exec_start..exec_end (inclusive) with new_block
new_lines = lines[:exec_start] + new_block + lines[exec_end + 1:]

with open(r'c:\caas-dashboard\backend\main.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print(f"SUCCESS: replaced {exec_end - exec_start + 1} lines with {len(new_block)} lines")
print(f"New file length: {len(new_lines)} lines")

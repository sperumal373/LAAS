"""Remove duplicate backup feature cards from About LaaS."""
with open(r'C:\caas-dashboard\frontend\src\App.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# The duplicate block is the second set of Backup/Rubrik/Cohesity/Veeam cards
# We need to find the pattern: after the first Veeam card, there's another Backup card
# The unique marker is "Managed server and proxy infrastructure visibility" which ends the Veeam card

marker = '"Managed server and proxy infrastructure visibility"]},'
parts = content.split(marker)
print(f"Found {len(parts)-1} occurrences of Veeam end marker")

if len(parts) >= 3:
    # Keep first two parts (up to and including second Veeam card ending)
    # But the duplicate is between the second and third occurrence
    # Actually: parts[0] has everything up to first Veeam end
    # parts[1] starts after first Veeam end, has the duplicate block up to second Veeam end
    # parts[2] starts after second Veeam end
    
    # The duplicate content in parts[1] starts immediately and is a copy of 4 cards
    # We need to check if parts[1] starts with the duplicate Backup card
    dup_start = parts[1].find('{icon:"\U0001f4be",title:"Backup & Data Protection"')
    if dup_start == -1:
        # Try with actual content
        dup_start = parts[1].find('title:"Backup & Data Protection"')
    
    print(f"Duplicate block starts at offset {dup_start} in parts[1]")
    print(f"Parts[1] starts with: {repr(parts[1][:80])}")
    
    if dup_start >= 0:
        # parts[1] = "  \n              <second_backup_card...><rubrik>...<cohesity>...<veeam_end>"
        # We want to keep parts[0] + marker + (skip the duplicate) + parts[2]
        # The content before dup_start in parts[1] is whitespace/newline
        before_dup = parts[1][:dup_start].rstrip()
        
        # Remove the duplicate: join parts[0] + first marker + parts[2] (skip parts[1])
        content = parts[0] + marker + "\n" + parts[2]
        print("Removed duplicate backup cards block")
    else:
        print("Could not locate duplicate start")
else:
    print("Not enough occurrences found")

with open(r'C:\caas-dashboard\frontend\src\App.jsx', 'w', encoding='utf-8') as f:
    f.write(content)

# Verify
count_backup = content.count('title:"Backup & Data Protection"')
count_rubrik = content.count('title:"Rubrik Security Cloud"')
count_cohesity = content.count('title:"Cohesity DataProtect"')
count_veeam = content.count('title:"Veeam Backup & Replication"')
print(f"After fix: Backup={count_backup}, Rubrik={count_rubrik}, Cohesity={count_cohesity}, Veeam={count_veeam}")

# patch_exhale.py — Run this ON THE ESP32 via mpremote repl
# to increase payloads per exhale cycle from 10 to 25
#
# Usage:
#   py -m mpremote connect COM18 run patch_exhale.py
#
# Or paste into the REPL manually.

import os

try:
    with open('exhale.py', 'r') as f:
        content = f.read()
    
    original = content
    
    # Try multiple candidate strings — handles different versions of exhale.py
    replacements = [
        # Pattern 1: explicit comment
        ('10  # payloads per cycle', '25  # v1.9: payloads per cycle (was 10)'),
        # Pattern 2: bare number in range/slice context  
        ('range(10)', 'range(25)'),
        # Pattern 3: config key with default
        ('exhale_count\', 10)', "exhale_count', 25)"),
        # Pattern 4: local variable assignment
        ('max_payloads = 10', 'max_payloads = 25'),
        ('payloads_per_cycle = 10', 'payloads_per_cycle = 25'),
        ('count = 10', 'count = 25'),
        ('n = 10', 'n = 25'),
    ]
    
    patched = False
    for old, new in replacements:
        if old in content:
            content = content.replace(old, new, 1)
            print('Patched: {} -> {}'.format(old, new))
            patched = True
            break
    
    if not patched:
        # Show lines with numbers so user can identify the right one
        print('Could not auto-patch. Lines containing numbers near exhale logic:')
        for i, line in enumerate(original.split('\n'), 1):
            if any(x in line.lower() for x in ['payload', 'broadcast', 'count', 'sample', 'pool.get']):
                print('{:3d}: {}'.format(i, line))
    else:
        with open('exhale.py', 'w') as f:
            f.write(content)
        print('exhale.py updated successfully.')
        
except OSError:
    print('exhale.py not found on this device.')
    print('Available files:', os.listdir())

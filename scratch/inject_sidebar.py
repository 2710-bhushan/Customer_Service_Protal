import os

link_to_inject = """    <a href="/admin/refunds/" class="nav-link {% if request.path == '/admin/refunds/' %}active{% endif %}">
      <i class="fas fa-money-bill-wave"></i> Refunds & Complaints
      {% if pending_refunds_count > 0 %}<span class="badge-count" style="background: var(--warning); color: black;">{{ pending_refunds_count }}</span>{% endif %}
    </a>"""

for f in os.listdir('templates/admin'):
    if not f.endswith('.html'):
        continue
    p = os.path.join('templates/admin', f)
    content = open(p, encoding='utf-8').read()
    
    if '/admin/refunds/' in content:
        print(f"Skipping {f}, link already exists.")
        continue
        
    lines = content.splitlines()
    new_lines = []
    modified = False
    for l in lines:
        new_lines.append(l)
        if 'href="/servicebooked/"' in l:
            new_lines.append(link_to_inject)
            modified = True
            
    if modified:
        open(p, 'w', encoding='utf-8').write('\n'.join(new_lines) + '\n')
        print(f"Successfully injected sidebar option in: {f}")

"""A numbered pleading (a complaint): the document's own locators are its sections, lettered subsections and
numbered paragraphs, plus the caption, the signature block and the footnotes. Lazy: the skeleton is every locator,
a region is written when something points at it, and a region carries its position (page, until) and a digest of
its words, never the prose itself: what a paragraph says is decomposed into facts beneath it by whoever reads it.

Written by Codex for one complaint (the section table below is that document's); a second pleading is a second
table, or a script that reads the table of contents."""
import hashlib
import re


eager = False

SECTIONS = [
 ('caption','Caption',0,0),
 ('contents','Table of contents',0,0),
 ('introduction','INTRODUCTION',1,9),
 ('parties','THE PARTIES',10,15),
 ('parties/a','A. Plaintiffs',10,11),
 ('parties/b','B. Steyr Arms',12,15),
 ('jurisdiction','JURISDICTION AND VENUE',16,20),
 ('sourcing','SOURCING',21,21),
 ('facts','FACTUAL ALLEGATIONS',22,121),
 ('facts/i','I. From 2003 Through 2008, Iran Was Arming Terrorists To Attack Americans In Iraq.',22,53),
 ('facts/i/a','A. Iran Was the World’s Leading Sponsor of Terrorism.',26,32),
 ('facts/i/b','B. Hizballah Established a Terrorist Network Armed by Iran to Target Americans in Iraq.',33,43),
 ('facts/i/c','C. The Terrorist Campaign Accelerated in 2004 and 2005.',44,48),
 ('facts/i/d','D. The Terrorist Campaign Culminated in the Battle of Sadr City.',49,53),
 ('facts/ii','II. As Iran And Hizballah Accelerated Their Terrorist Campaign In Iraq, Steyr Equipped Them With Hundreds Of High-Caliber Sniper Rifles.',54,78),
 ('facts/ii/a','A. Steyr’s HS .50 Sniper Rifle Was a Deadly and Precise “Weapon of War.”',54,59),
 ('facts/ii/b','B. Steyr Sold Hundreds of HS .50 Sniper Rifles to Iran While Knowing or Recklessly Disregarding that They Would Be Used to Arm Iran’s Terrorist Proxies in Iraq.',60,65),
 ('facts/ii/c','C. When Confronted by U.S. Authorities, Steyr Refused to Mitigate the Harm It Had Done, Lied to Protect its Iranian Partners, and Enabled Further Iranian Support for Terrorists.',66,78),
 ('facts/iii','III. Iran’s Terrorist Proxies Used Steyr’s Sniper Rifles To Attack Americans In Iraq.',79,88),
 ('facts/iv','IV. Plaintiffs Were Injured By Terrorists Targeting Them With HS .50 Sniper Rifles During the Battle of Sadr City.',89,121),
 ('facts/iv/a','A. Hizballah and JAM Used HS .50 Sniper Rifles to Terrorize and Impede U.S. Forces.',89,97),
 ('facts/iv/b','B. Plaintiffs Were Injured As a Result.',98,121),
 ('facts/iv/b/1','1. U.S. Army Sergeant Benjamin A. Zibutis',101,102),
 ('facts/iv/b/2','2. U.S. Army Sergeant Mark E. Thomsen',103,104),
 ('facts/iv/b/3','3. U.S. Army Staff Sergeant Brandon T. Josey',105,109),
 ('facts/iv/b/4','4. U.S. Army Staff Sergeant Anthony Farina',110,110),
 ('facts/iv/b/5','5. U.S. Army National Guard Sergeant Adam J. Magers',111,113),
 ('facts/iv/b/6','6. U.S. Army Sergeant John Kyle Daggett',114,115),
 ('facts/iv/b/7','7. U.S. Army Sergeant Andres Vazquez',116,118),
 ('facts/iv/b/8','8. U.S. Army Sergeant Michael J. Briggs',119,121),
 ('claim','CLAIM FOR RELIEF',122,132),
 ('jury','JURY DEMAND',133,133),
 ('relief','PRAYER FOR RELIEF',134,134),
 ('signature','Signature',0,0),
 ('footnotes','Footnotes',0,0),
]



def extract(pdf_path):
    import pdfplumber                                   # only when a region is read
    paragraphs,notes,pages={}, {}, {}
    current=None; note_current=None; expected=1
    headings=re.compile(r'^(?:INTRODUCTION|THE PARTIES|JURISDICTION AND VENUE|SOURCING|FACTUAL ALLEGATIONS|CLAIM FOR RELIEF|JURY DEMAND|PRAYER FOR RELIEF)$|^(?:[IVX]+|[A-D])\.\s|^[1-8]\.\s+U\.S\. Army')
    with pdfplumber.open(pdf_path) as pdf:
        for page,p in enumerate(pdf.pages,1):
            rules=[r for r in p.rects if abs(r['width']-144)<2 and r['height']<1]
            cut=min([r['top'] for r in rules],default=740)
            body=p.crop((0,45,p.width,min(cut,740))).extract_text(x_tolerance=2) or ''
            pages[page]=body
            if 4<=page<=55:
                for line in body.splitlines():
                    line=line.strip()
                    m=re.match(r'^'+str(expected)+r'\.\s+(.+)',line)
                    if m:
                        current=expected;expected+=1
                        paragraphs[current]={'lines':[line],'positions':[page],'page':page,'until':page}
                    elif headings.match(line):current=None
                    elif current and line:
                        paragraphs[current]['lines'].append(line)
                        paragraphs[current]['positions'].append(page)
                        paragraphs[current]['until']=page
            if rules:
                note_text=p.crop((0,cut,p.width,740)).extract_text(x_tolerance=2) or ''
                for line in note_text.splitlines():
                    next_note=len(notes)+1
                    m=re.match(r'^'+str(next_note)+r'\s*(?=[^\d])(.+)',line)
                    if m:
                        note_current=next_note
                        notes[note_current]={'lines':[m[1]],'page':page,'until':page}
                    elif note_current and line.strip():
                        notes[note_current]['lines'].append(line)
                        notes[note_current]['until']=page
    if set(paragraphs)!=set(range(1,135)) or set(notes)!=set(range(1,140)):
        raise ValueError('Numbering differs from this artifact; inspect before binding a new version')
    return paragraphs,notes,pages

def locators():
    result={}
    for n in range(1,135):
        candidates=[s for s in SECTIONS if s[2]>0 and s[2]<=n<=s[3]]
        section=min(candidates,key=lambda s:(s[3]-s[2],-s[0].count('/')))
        result[n]=section[0]+'/p'+str(n)
    return result



def marker(source):
    return 'sha256 ' + hashlib.sha256(open(source['where'], 'rb').read()).hexdigest()


def contents(source):
    return [p for p, name, a, z in SECTIONS]


def skeleton(source):
    paths = locators()
    out = [p for p, name, a, z in SECTIONS]
    out += list(paths.values())
    for n, letters in [(59, 'abcdefg'), (125, 'abc'), (134, 'abcde')]:
        out += [paths[n] + '/' + letter for letter in letters]
    out += ['footnotes/f' + str(n) for n in range(1, 140)]
    return out


def region_of(region, paragraphs, notes, pages, paths):
    match = [n for n, p in paths.items() if p == region]
    if match:
        return paragraphs[match[0]]
    if re.fullmatch(r'.+/p\d+/[a-g]', region):
        parent, letter = region.rsplit('/', 1)
        n = next(n for n, p in paths.items() if p == parent)
        original = paragraphs[n]
        start = next(i for i, line in enumerate(original['lines']) if re.match(r'^' + letter + r'\.\s', line))
        end = next((i for i in range(start + 1, len(original['lines'])) if re.match(r'^[a-g]\.\s', original['lines'][i])), len(original['lines']))
        return {'lines': original['lines'][start:end], 'page': original['positions'][start], 'until': original['positions'][end - 1]}
    if re.fullmatch(r'footnotes/f\d+', region):
        return notes[int(region.split('f')[-1])]
    if region in ('caption', 'signature'):
        n = 1 if region == 'caption' else 56
        return {'lines': pages[n].splitlines(), 'page': n, 'until': n}
    return None


def regions(source, paths_wanted):
    paragraphs, notes, pages = extract(source['where'])
    paths = locators()
    names = {p: name for p, name, a, z in SECTIONS}
    out = {}
    for region in paths_wanted:
        if region in names:
            out[region] = {'name': names[region]}
            continue
        data = region_of(region, paragraphs, notes, pages, paths)
        if data is None:
            out[region] = None
            continue
        text = '\n'.join(data['lines'])
        slots = {'page': data['page'], 'words': len(text.split()), 'body': hashlib.sha256(text.encode()).hexdigest()[:16]}
        if data['until'] != data['page']:
            slots['until'] = data['until']
        out[region] = slots
    return out

// The folio is a read-only lens. All writes go through the notebook's Goo controls.
(() => {
  const phrase = document.querySelector('.gemara button');
  const question = document.getElementById('question');
  const leaves = document.getElementById('leaves');
  function select() {
    phrase.setAttribute('aria-pressed', 'true');
    question.hidden = false;
  }
  phrase.addEventListener('click', select);
  if (location.hash === '#' + phrase.id) select();
  function node(tag, value) {
    const n = document.createElement(tag);
    n.textContent = value;
    n.dir = 'auto';
    return n;
  }
  function citation(id, evidence) {
    if (id !== evidence.id) return node('span', 'Evidence: ' + id);
    const a = node('a', 'Evidence: ' + evidence.reference);
    a.href = '#' + id;
    a.addEventListener('click', select);
    return a;
  }
  function distinction(d, evidence) {
    const card = node('article', '');
    card.id = 'leaf-' + d.id;
    card.append(node('small', 'CHILUK   /   ' + d.id), node('h3', d.name),
      node('b', 'Practical difference'), node('p', d.consequence),
      node('b', 'Boundary case'), node('p', d.limit), citation(d.lemma, evidence));
    return card;
  }
  function edition(e, draft, evidence) {
    const card = node('article', '');
    const d = node('a', 'Distinction ' + e.distinction);
    d.href = '#leaf-' + e.distinction;
    const cite = node(e.sourceUrl ? 'a' : 'span', e.reference);
    if (e.sourceUrl) cite.href = e.sourceUrl;
    card.append(node('small', (draft ? 'DRAFT' : 'PUBLISHED') + '   /   ' + e.id),
      node('h3', 'From ' + e.parentName),
      node('p', e.thesis || 'Open this fork at the study table to write its alternative.'),
      node('b', 'Inherited assumption'), node('p', e.premise), cite, node('br', ''), d, node('br', ''), citation(e.lemma, evidence));
    return card;
  }
  let generation = 0;
  async function refresh() {
    const current = ++generation;
    try {
      const r = await fetch('/torah-study/leaves', {cache:'no-store'});
      if (!r.ok) throw Error('Notebook unavailable');
      const book = await r.json();
      if (generation !== current) return;
      const cards = [...book.leaves.toReversed().map(e => edition(e, false, book.evidence)),
        ...(book.draft ? [edition(book.draft, true, book.evidence)] : []),
        ...book.distinctions.toReversed().map(d => distinction(d, book.evidence))];
      leaves.replaceChildren(...(cards.length ? cards : [node('p', 'Your distinctions and published readings will appear here, beside their evidence.')]));
    } catch {
      if (generation === current) leaves.textContent = 'Could not read the margin. Reload to try again.';
    }
  }
  // One reread after Goo mounts or replaces a view (including the post-save reread).
  let timer;
  new MutationObserver(() => { clearTimeout(timer); timer = setTimeout(refresh, 120); })
    .observe(document.querySelector('.table'), {subtree:true, childList:true});
  refresh();
})();

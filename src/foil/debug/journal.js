// A journal cursor is a physical epoch key, not a JavaScript number or offset.
// Path identity stays /log; only these independently validated options may
// become query parameters. Older kernels remain usable at the default page.
const DECIMAL = /^(?:0|[1-9][0-9]*)$/;
export const DEFAULT_JOURNAL_PAGE = Object.freeze({ before: null, limit: 40 });

export function journalPage(value = DEFAULT_JOURNAL_PAGE) {
  if (!value || (value.before !== null && !DECIMAL.test(value.before)) ||
      (value.before !== null && typeof value.before !== 'string') ||
      !Number.isInteger(value.limit) || value.limit < 1 || value.limit > 40) {
    throw new Error('Invalid journal page. Use a decimal cursor and a limit from 1 to 40.');
  }
  return { before: value.before, limit: value.limit };
}

export function journalPageFromURL(url) {
  const params = url.searchParams;
  // URLSearchParams discards empty fields; the HTTP grammar rejects them.
  // Preserve that distinction instead of silently repairing malformed links.
  if (url.search.slice(1).split('&').some(field => !field) && url.search) {
    throw new Error('Empty journal query parameters are not supported.');
  }
  for (const key of params.keys()) {
    if (!['before', 'limit', 'view'].includes(key) || params.getAll(key).length !== 1 ||
        (key === 'view' && params.get(key) !== 'rendered')) {
      throw new Error('Unsupported or repeated journal query parameter.');
    }
  }
  const before = params.get('before');
  const limit = params.get('limit');
  if (limit !== null && !/^(?:[1-9]|[1-3][0-9]|40)$/.test(limit)) {
    throw new Error('Journal page size must be from 1 to 40.');
  }
  return journalPage({ before, limit: limit === null ? 40 : Number(limit) });
}

export function journalQuery(value) {
  const page = journalPage(value);
  const query = new URLSearchParams();
  if (page.before !== null) query.set('before', page.before);
  if (page.limit !== 40) query.set('limit', String(page.limit));
  return query.size ? '?' + query : '';
}

export function sameJournalPage(left, right) {
  return (left?.before ?? null) === (right?.before ?? null) &&
    (left?.limit ?? 40) === (right?.limit ?? 40);
}

export function parseJournalPagination(workspace, path, children) {
  if (!workspace.dataset.paging) return null;
  const data = workspace.dataset;
  const invalid = () => { throw new Error('The runtime returned invalid journal pagination metadata.'); };
  if (path !== '/log' || data.paging !== 'journal' ||
      !DECIMAL.test(data.childCount || '') || !DECIMAL.test(data.pageEpoch || '') ||
      !/^(?:[1-9]|[1-3][0-9]|40)$/.test(data.pageLimit || '') ||
      data.pageBefore === undefined || data.pageNextBefore === undefined) invalid();
  const before = data.pageBefore || null;
  const nextBefore = data.pageNextBefore || null;
  if ((before !== null && !DECIMAL.test(before)) || (nextBefore !== null && !DECIMAL.test(nextBefore))) invalid();
  const limit = Number(data.pageLimit);
  if (children.length > limit || BigInt(data.childCount) < BigInt(children.length)) invalid();
  let previous = before === null ? null : BigInt(before);
  for (const path of children) {
    const key = path.slice(5);
    if (!path.startsWith('/log/') || !DECIMAL.test(key)) invalid();
    const epoch = BigInt(key);
    if (epoch > BigInt(data.pageEpoch) || (previous !== null && epoch >= previous)) invalid();
    previous = epoch;
  }
  if (nextBefore !== null && (!children.length || nextBefore !== children.at(-1).slice(5))) invalid();
  return { kind: 'journal', before, nextBefore, limit, total: data.childCount, epoch: data.pageEpoch };
}

export function assertJournalPage(view, requested) {
  if (view.path !== '/log') return;
  const page = journalPage(requested);
  if (view.pagination ? !sameJournalPage(view.pagination, page) : !sameJournalPage(page, DEFAULT_JOURNAL_PAGE)) {
    throw new Error('The runtime did not return the requested journal page. The current view has been kept.');
  }
}

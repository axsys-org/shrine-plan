// A journal cursor is a physical epoch key, not a JavaScript number or offset.
// The journal belongs to its hexadecimal namespace authority. Bare /log is
// accepted only for old bookmarks and saved parser artifacts.
const DECIMAL = /^(?:0|[1-9][0-9]*)$/;
export const DEFAULT_JOURNAL_PAGE = Object.freeze({ before: null, limit: 40 });

export function isJournalRoot(path) {
  if (typeof path !== 'string') return false;
  if (path === '/log') return true;
  // Shrine hex is minimal little-endian bytes, not conventional hex digits:
  // 0x0001 is valid, while an odd nibble count or trailing zero byte is not.
  const match = /^\/0x((?:[0-9a-f]{2})+)\/log$/.exec(path);
  return Boolean(match && !match[1].endsWith('00'));
}

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

export function parseJournalPagination(data, path, children) {
  if (data === null) return null;
  const invalid = () => { throw new Error('The runtime returned invalid journal pagination metadata.'); };
  const fields = ['kind', 'before', 'nextBefore', 'limit', 'total', 'epoch'];
  if (!data || typeof data !== 'object' || Array.isArray(data) ||
      Object.keys(data).length !== fields.length || fields.some(key => !Object.hasOwn(data, key)) ||
      !isJournalRoot(path) || data.kind !== 'journal' ||
      typeof data.total !== 'string' || !DECIMAL.test(data.total) ||
      typeof data.epoch !== 'string' || !DECIMAL.test(data.epoch)) invalid();
  const {before, nextBefore, limit} = data;
  journalPage({before, limit});
  if (nextBefore !== null && (typeof nextBefore !== 'string' || !DECIMAL.test(nextBefore))) invalid();
  if (children.length > limit || BigInt(data.total) < BigInt(children.length)) invalid();
  let previous = before === null ? null : BigInt(before);
  const prefix = path + '/';
  for (const child of children) {
    const key = child.slice(prefix.length);
    if (!child.startsWith(prefix) || !DECIMAL.test(key)) invalid();
    const epoch = BigInt(key);
    if (epoch > BigInt(data.epoch) || (previous !== null && epoch >= previous)) invalid();
    previous = epoch;
  }
  if (nextBefore !== null && (!children.length || nextBefore !== children.at(-1).slice(prefix.length))) invalid();
  return { kind: 'journal', before, nextBefore, limit, total: data.total, epoch: data.epoch };
}

export function assertJournalPage(view, requested) {
  if (!isJournalRoot(view.path)) return;
  const page = journalPage(requested);
  if (view.pagination ? !sameJournalPage(view.pagination, page) : !sameJournalPage(page, DEFAULT_JOURNAL_PAGE)) {
    throw new Error('The runtime did not return the requested journal page. The current view has been kept.');
  }
}

// Split rendered, sanitized Markdown while retaining its inline markup.
export function paginateJournal(source, target) {
  source.querySelectorAll('ol').forEach((list) => {
    Array.from(list.children).forEach((item, index) => {
      item.setAttribute('value', String(index + 1));
    });
  });
  const points = [{ node: source, offset: 0, wordEnd: true }];
  const visit = (parent) => {
    Array.from(parent.childNodes).forEach((node, index) => {
      if (node.nodeType === 3) {
        let offset = 0;
        for (const char of node.textContent) {
          offset += char.length;
          points.push({ node, offset, wordEnd: /\s/u.test(char) });
        }
      } else {
        visit(node);
      }
      points.push({ node: parent, offset: index + 1, wordEnd: true });
    });
  };
  visit(source);
  const range = document.createRange();
  const fragment = (start, end) => {
    range.setStart(points[start].node, points[start].offset);
    range.setEnd(points[end].node, points[end].offset);
    return range.cloneContents();
  };
  const pages = [];
  let start = 0;
  while (start < points.length - 1) {
    let low = start + 1;
    let high = points.length - 1;
    let fit = start;
    while (low <= high) {
      const middle = Math.floor((low + high) / 2);
      target.replaceChildren(fragment(start, middle));
      if (target.scrollHeight <= target.clientHeight) {
        fit = middle;
        low = middle + 1;
      } else {
        high = middle - 1;
      }
    }
    let end = fit;
    if (fit < points.length - 1) {
      while (end > start && !points[end].wordEnd) end--;
    }
    // An unbroken word may need a split between Unicode code points.
    if (end === start) end = Math.max(start + 1, fit);
    pages.push(fragment(start, end));
    start = end;
  }
  if (!pages.length) pages.push(source.cloneNode(true));
  return pages;
}

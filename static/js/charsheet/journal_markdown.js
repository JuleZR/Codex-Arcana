// Small, deliberately HTML-free Markdown subset for personal journal entries.
const escapeHtml = (text) => String(text).replace(/[&<>"']/g, (char) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[char]));

function inline(text) {
  // Tokenize before emitting markup so user text never becomes HTML attributes.
  const pattern = /`([^`]+)`|\*\*(.+?)\*\*|__(.+?)__|\*([^*]+)\*|_([^_]+)_|\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g;
  let html = '', end = 0;
  for (const match of text.matchAll(pattern)) {
    html += escapeHtml(text.slice(end, match.index));
    if (match[1]) html += `<code>${escapeHtml(match[1])}</code>`;
    else if (match[2] || match[3]) html += `<strong>${escapeHtml(match[2] || match[3])}</strong>`;
    else if (match[4] || match[5]) html += `<em>${escapeHtml(match[4] || match[5])}</em>`;
    else html += `<a href="${escapeHtml(match[7])}" target="_blank" rel="noopener noreferrer">${escapeHtml(match[6])}</a>`;
    end = match.index + match[0].length;
  }
  return html + escapeHtml(text.slice(end));
}

function blocks(text) {
  const result = [];
  let fence = null, code = [];
  for (const line of String(text || '').replace(/\r\n?/g, '\n').split('\n')) {
    const marker = line.match(/^\s{0,3}(`{3,}|~{3,})(.*)$/);
    if (fence) {
      if (marker && marker[1][0] === fence[0] && marker[1].length >= fence.length && !marker[2].trim()) {
        result.push({ type: 'pre', text: code.join('\n') });
        fence = null; code = [];
      } else code.push(line);
    } else if (marker) {
      fence = marker[1];
    } else {
      const heading = line.match(/^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$/);
      const unordered = line.match(/^\s*[-+*]\s+(.+)$/);
      const ordered = line.match(/^\s*\d+[.)]\s+(.+)$/);
      const quote = line.match(/^\s*>\s?(.*)$/);
      if (heading) result.push({ type: `h${heading[1].length}`, text: heading[2] });
      else if (/^\s*(---+|\*\*\*+|___+)\s*$/.test(line)) result.push({ type: 'hr', text: '' });
      else if (unordered || ordered) result.push({ type: unordered ? 'ul' : 'ol', text: (unordered || ordered)[1] });
      else if (quote) result.push({ type: 'blockquote', text: quote[1] });
      else result.push({ type: line.trim() ? 'p' : 'blank', text: line });
    }
  }
  if (fence) result.push({ type: 'pre', text: code.join('\n') });
  return result;
}

export function journalTitle(text) {
  const heading = blocks(text).find((block) => block.type === 'h1');
  return heading ? heading.text.replace(/\[([^\]]+)\]\([^)]*\)/g, '$1').replace(/[`*_]/g, '').trim() : '';
}

export function renderJournalMarkdown(text) {
  const rows = blocks(text), html = [];
  for (let i = 0; i < rows.length; i++) {
    const { type, text: value } = rows[i];
    if (type === 'blank') continue;
    if (type === 'hr') { html.push('<hr>'); continue; }
    if (type === 'pre') { html.push(`<pre><code>${escapeHtml(value)}</code></pre>`); continue; }
    const parts = [inline(value)];
    if (['p', 'ul', 'ol', 'blockquote'].includes(type)) {
      while (rows[i + 1]?.type === type) parts.push(inline(rows[++i].text));
    }
    const body = type === 'ul' || type === 'ol'
      ? parts.map((part) => `<li>${part}</li>`).join('') : parts.join('<br>');
    html.push(`<${type}>${body}</${type}>`);
  }
  return html.join('');
}

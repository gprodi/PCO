// Rendu Markdown des documents générés (guide de montage, câblage) : HTML brut échappé, liens
// limités à http(s), cases à cocher affichées comme des cases à imprimer (pas de champ sans libellé).
import { Marked } from 'marked';

const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
export const escapeHtml = (s) => String(s).replace(/[&<>"']/g, (c) => ESC[c]);

const marked = new Marked({
  gfm: true,
  async: false,
  renderer: {
    html: ({ text }) => escapeHtml(text),
    checkbox: ({ checked }) => `<span class="todo" aria-hidden="true">${checked ? '☑' : '☐'}</span> `,
    link({ href, title, tokens }) {
      const text = this.parser.parseInline(tokens);
      if (!/^https?:\/\//i.test(href)) return text;
      const t = title ? ` title="${escapeHtml(title)}"` : '';
      return `<a href="${escapeHtml(href)}"${t} target="_blank" rel="noopener noreferrer">${text}</a>`;
    },
    image: ({ text }) => escapeHtml(text),
  },
});

export function renderMarkdown(text) {
  return marked.parse(text ?? '');
}

import { describe, expect, it } from 'vitest';
import { renderMarkdown } from './markdown.js';

describe('rendu Markdown du guide', () => {
  it('titres, listes, gras et code', () => {
    const html = renderMarkdown('## Étape 1\n\n1. Relier **3V3**\n2. Lire `cablage.md`\n');
    expect(html).toContain('<h2>Étape 1</h2>');
    expect(html).toContain('<strong>3V3</strong>');
    expect(html).toContain('<code>cablage.md</code>');
  });

  it('HTML brut échappé, liens non http neutralisés, image réduite à son texte', () => {
    const html = renderMarkdown('<img src=x onerror=alert(1)>\n\n[clic](javascript:alert(1)) [doc](https://wokwi.com) ![schéma](x.png)');
    expect(html).not.toContain('<img');
    expect(html).toContain('&lt;img');
    expect(html).not.toContain('javascript:');
    expect(html).toContain('<a href="https://wokwi.com" target="_blank" rel="noopener noreferrer">doc</a>');
    expect(html).toContain('schéma');
  });

  it('cases à cocher : symbole imprimable, aucun champ de formulaire', () => {
    const html = renderMarkdown('- [ ] **3V3** : board.3V3\n- [x] fait\n');
    expect(html).not.toContain('<input');
    expect(html).toContain('☐');
    expect(html).toContain('☑');
  });
});

import { marked } from 'marked';
import mermaid from 'mermaid';

// ============================================================
// MathJax 3 configuration (must be set BEFORE the es5 bundle loads)
// ============================================================
window.MathJax = {
  tex: {
    inlineMath: [['$', '$']],
    displayMath: [['$$', '$$']],
    // MathJax automatically handles: \bm, \boldsymbol, \coloneqq, \stackrel,
    // \begin{aligned}, \operatorname, \mathbb, \mathcal, \text, etc.
    // The full bundle includes: ams, boldsymbol, cancel, cases, color, colortbl,
    // configmacros, empheq, enclose, extpfeil, gensymb, html, mathtools, mhchem,
    // newcommand, noundefined, tagformat, textcomp, textmacros, unicode, upgreek, verb
  },
  startup: {
    typeset: false,  // We control when to render
  },
  options: {
    enableMenu: false,
    ignoreHtmlClass: 'mathjax-ignore',
  },
};

let _mathjaxReady = false;
async function _ensureMathJax() {
  if (_mathjaxReady) return;
  // The es5 bundle reads window.MathJax config on load
  await import('mathjax/es5/tex-chtml-full.js');
  _mathjaxReady = true;
}

marked.setOptions({
  breaks: false,
  gfm: true,
});

mermaid.initialize({ startOnLoad: false, theme: 'neutral' });

// ============================================================
// LaTeX scanner — ported from Python _scan_math_delimiters
// ============================================================

const HTML_RE = /<[^>]+>/g;

function scanMathDelimiters(text) {
  const result = [];
  let i = 0;
  const n = text.length;

  while (i < n) {
    // $$ block
    if (i + 1 < n && text.substring(i, i + 2) === '$$') {
      const closer = text.indexOf('$$', i + 2);
      if (closer !== -1) {
        const inner = text.substring(i + 2, closer).replace(HTML_RE, '');
        result.push('$$' + inner + '$$');
        i = closer + 2;
      } else {
        result.push('\\$\\$');
        i += 2;
      }
      continue;
    }

    // $ inline
    if (text[i] === '$') {
      let j = i + 1;
      let found = false;
      while (j < n) {
        if (text[j] === '$') {
          if (j + 1 < n && text.substring(j, j + 2) === '$$') {
            const closer2 = text.indexOf('$$', j + 2);
            if (closer2 !== -1) {
              j = closer2 + 2;
            } else {
              j += 2;
            }
            continue;
          }
          const inner = text.substring(i + 1, j).replace(HTML_RE, '');
          result.push('$' + inner + '$');
          i = j + 1;
          found = true;
          break;
        }
        j++;
      }

      if (!found) {
        result.push('\\$');
        i += 1;
      }
      continue;
    }

    result.push(text[i]);
    i++;
  }

  return result.join('');
}

// Pre-processing fixes for LLM-generated LaTeX that even MathJax might struggle with.
// MathJax handles \bm, \coloneqq, \stackrel, \begin{aligned}, etc. natively.
// This fixes the edge cases: \d (differential vs underdot), \intertext, etc.
function fixLatexCommands(text) {
  const MATH_RE = /\$\$([\s\S]*?)\$\$|\$([^$\n]+?)\$/g;
  return text.replace(MATH_RE, (match) => {
    let inner = match;
    // Differential d — LLM writes \d{x} for differential, but \d is underdot in LaTeX.
    // MathJax would interpret \d{x} as "dot-under x". Fix before rendering.
    inner = inner.replace(/\\d\{([^}]*)\}/g, '\\mathrm{d}$1');
    inner = inner.replace(/\\d\b/g, '\\mathrm{d}');
    // Degree symbol
    inner = inner.replace(/\\degree\b/g, '^{\\circ}');
    // MathJax handles \bm, \coloneqq, \stackrel natively — no fix needed
    // Remove \notag / \nonumber (only meaningful in LaTeX align environments)
    inner = inner.replace(/\\notag\b/g, '');
    inner = inner.replace(/\\nonumber\b/g, '');
    // \intertext{...} → \text{...} (intertext only works in align)
    inner = inner.replace(/\\intertext\{/g, '\\text{');
    return inner;
  });
}

export function fixLatex(content) {
  return fixLatexCommands(content);
}

export function normalizeLatex(content) {
  let s = content;
  // Normalize \(...\) → $...$
  s = s.replace(/\\\(\s*/g, '$');
  s = s.replace(/\s*\\\)/g, '$');
  // Normalize \[...\] → $$...$$
  s = s.replace(/\\\[\s*/g, '$$');
  s = s.replace(/\s*\\\]/g, '$$');
  // Add space between CJK chars and $
  s = s.replace(/([一-鿿　-〿＀-￯])\$/g, '$1 $');
  s = s.replace(/\$([一-鿿　-〿＀-￯])/g, '$ $1');
  s = scanMathDelimiters(s);
  s = fixLatexCommands(s);
  return s;
}

// ============================================================
// Image URL rewriting
// ============================================================

export function rewriteImageUrls(markdown, courseId, docName) {
  return markdown.replace(
    /!\[([^\]]*)\]\((?!https?:\/\/)([^)]+)\)/g,
    `![$1](/api/courses/${encodeURIComponent(courseId)}/images/${encodeURIComponent(docName)}/$2)`
  );
}

// ============================================================
// Rendering
// ============================================================

export function renderContentLight(md) {
  try {
    return marked.parse(md);
  } catch (e) {
    return '<pre>' + escapeHtmlLight(md) + '</pre>';
  }
}

export function renderContent(md) {
  const normalized = normalizeLatex(md);
  let html;
  try {
    html = marked.parse(normalized);
  } catch (e) {
    html = '<pre>' + escapeHtmlLight(normalized) + '</pre>';
  }
  return html;
}

// Lightweight render for streaming/chat — does NOT invoke MathJax (too slow for streaming)
export function renderInline(md) {
  try {
    return marked.parse(fixLatexCommands(md));
  } catch (e) {
    return '<pre>' + escapeHtmlLight(md) + '</pre>';
  }
}

function escapeHtmlLight(s) {
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

// ============================================================
// Math rendering — uses MathJax 3 (handles \bm, \coloneqq,
// \stackrel, \begin{aligned}, and almost all LLM-generated LaTeX)
// ============================================================

export async function renderMath(container) {
  try {
    await _ensureMathJax();
    if (window.MathJax && window.MathJax.typesetPromise) {
      await window.MathJax.typesetPromise([container]);
    }
  } catch (e) {
    console.warn('MathJax render error:', e);
  }
}

export async function renderMermaid(container) {
  const blocks = container.querySelectorAll('pre code.language-mermaid');
  for (let i = 0; i < blocks.length; i++) {
    try {
      const id = 'mermaid-' + Date.now() + '-' + i;
      const { svg } = await mermaid.render(id, blocks[i].textContent);
      const wrapper = document.createElement('div');
      wrapper.innerHTML = svg;
      wrapper.style.textAlign = 'center';
      wrapper.style.margin = '1em 0';
      blocks[i].parentElement.replaceWith(wrapper);
    } catch (e) {
      console.warn('Mermaid render error:', e);
    }
  }
}

export async function renderMathAndMermaid(container) {
  await renderMath(container);
  await renderMermaid(container);
}

export function renderMarkdown(md, container, courseId, docName) {
  let processed = courseId && docName ? rewriteImageUrls(md, courseId, docName) : md;
  container.innerHTML = renderContent(processed);
  setTimeout(() => renderMathAndMermaid(container), 0);
}

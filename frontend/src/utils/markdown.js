import { marked } from 'marked';
import mermaid from 'mermaid';

// KaTeX auto-render — separate entry point
let renderMathInElement = null;
import('katex/dist/contrib/auto-render.js').then(m => {
  renderMathInElement = m.default || m.renderMathInElement;
});

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
          // Check if it's a $$ block opener
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

function fixLatexCommands(text) {
  // Replace known-problematic LaTeX commands only inside math regions
  const MATH_RE = /\$\$([\s\S]*?)\$\$|\$([^$\n]+?)\$/g;
  return text.replace(MATH_RE, (match) => {
    let inner = match;
    // Dotless i/j — text-mode only, invalid in KaTeX math mode
    inner = inner.replace(/\\i\b/g, 'i');
    inner = inner.replace(/\\j\b/g, 'j');
    // Differential d — LLM often writes \d{x} or \d
    inner = inner.replace(/\\d\{([^}]*)\}/g, '\\mathrm{d}$1');
    inner = inner.replace(/\\d\b/g, '\\mathrm{d}');
    // Degree symbol
    inner = inner.replace(/\\degree\b/g, '^{\\circ}');
    // Old-style font commands → modern equivalents
    inner = inner.replace(/\\rm\{([^}]*)\}/g, '\\mathrm{$1}');
    inner = inner.replace(/\\bf\{([^}]*)\}/g, '\\mathbf{$1}');
    inner = inner.replace(/\\it\{([^}]*)\}/g, '\\textit{$1}');
    // Unsupported packages
    inner = inner.replace(/\\mathds\{([^}]*)\}/g, '\\mathbb{$1}');
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

// Lightweight render for streaming/chat — only fixes LaTeX commands, no delimiter scanning
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

export async function renderMath(container) {
  if (!renderMathInElement) {
    // Wait for KaTeX auto-render to load
    try {
      const m = await import('katex/dist/contrib/auto-render.js');
      renderMathInElement = m.default || m.renderMathInElement;
    } catch (e) {
      console.warn('KaTeX auto-render not available:', e);
      return;
    }
  }
  try {
    renderMathInElement(container, {
      delimiters: [
        { left: '$$', right: '$$', display: true },
        { left: '$', right: '$', display: false },
      ],
      throwOnError: false,
    });
  } catch (e) {
    console.warn('KaTeX render error:', e);
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

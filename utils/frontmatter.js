/**
 * frontmatter.js — read a field out of a wiki page's YAML-ish frontmatter.
 *
 * ## Why this exists
 *
 * Eight files in `utils/` carried their own copy of the same two-line regex (measured
 * 2026-10-17): `component-scan`, `consumption-report`, `daily-pipeline`, `family-assign`,
 * `family-match`, `family-queue`, `integrate-eligible`, `integrate-queue`, `wiki-epoch-repair`,
 * `wiki-type-build`. Four trimmed the captured value and six did not, so some call sites
 * compensated with a `.trim()` of their own and others relied on there being no trailing space —
 * `component-scan.js:228` and `wiki-type-build.js:118` are the same line, one remembering and the
 * next file along forgetting.
 *
 * ⚠ **This was not yet a live bug** and the note should not pretend otherwise: the wiki carries
 * **zero** values with trailing whitespace today, and every uncompensated call site feeds the
 * result to `parseFloat`, `parseInt` or `.match()`, all of which tolerate it. The hazard is that
 * `family:` and `universe:` ARE compared by equality across these files, so one hand-edited page
 * with a trailing space would make a family vanish from one reader and not another — silently,
 * and in the direction of the biggest families.
 *
 * So: one implementation, which always trims. CLAUDE.md records the same shape of problem for the
 * harness constants ("duplicated across seven files and had already drifted"); this is the
 * cheapest possible version of that lesson.
 *
 * Usage:
 *   const { field } = require('./frontmatter');
 *   field(text, 'family')      // '' when absent — never undefined, so `.trim()`/`.match()` are safe
 */

/**
 * The first `^<key>: <value>$` line anywhere in `text`, trimmed.
 *
 * ⚠ Scans the WHOLE document, not just the `---` block, which is what every copy did and what
 * callers depend on: `kb-stub.js` stamps a `normalized:` block further down the page and several
 * readers reach fields that are not strictly frontmatter.
 *
 * ⚠ Returns `''` for a missing field, never `undefined` or `null`. Callers chain `.match()` and
 * `.replace()` onto the result without guarding, so a nullish return would throw.
 *
 * @param {string} text  the page contents
 * @param {string} key   the field name (used verbatim in a RegExp — pass a literal, not input)
 * @returns {string}
 */
function field(text, key) {
  if (!text) return '';
  // ⚠ `[^\\S\\n]*`, NOT `\\s*`: \\s matches the NEWLINE, so an EMPTY field captured the NEXT
  // line as its value. Measured 2026-10-30: `realizability:` with nothing after it returned
  // "status: active", and `edge:` returns "- name: …" on all 14 family pages. The edge case is
  // benign (nothing calls field() on a block key), but `realizability:` empty is the documented
  // way to mark it UNSET, and unknown must BLOCK — returning a non-empty string defeats that.
  const m = String(text).match(new RegExp(`^${key}:[^\\S\\n]*(.*)$`, 'm'));
  return m ? m[1].trim() : '';
}

/** `field()` with the `[[wiki link]]` brackets stripped — the form family/parent fields take. */
function link(text, key) {
  return field(text, key).replace(/[[\]]/g, '').trim();
}

// ⚠ Deliberately NOT here: `wiki-family-build.js`'s `frontmatter(src)`, which parses the whole
// `---` block into an object, and its `setFmKey(block, k, v)`, which WRITES a value. Those are
// different operations on a different surface (one page's own block, which that builder also
// rewrites), and folding them in would make this module the wiki's editor rather than its reader.
// It already trims, which is the thing that had diverged.

module.exports = { field, link };

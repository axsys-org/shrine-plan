// Goo's page presets in the browser. Goo lays a view out on the server and cannot stream, so a page
// that builds in front of its owner draws itself here, from the one list of presets Goo owns
// (presets.json): what the list does not name is not drawn, so this renderer and Goo cannot drift.
// Text in, a document out (`html`), and back (`markdown`); the host page supplies how a link, a live
// value, a blank and a live block look (`hooks`), since only it can read the world.
(function (global) {
  "use strict";
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const IMPLEMENTED = ["heading", "paragraph", "list", "numbered", "table", "quote", "embed", "divider", "link", "live", "value", "hole", "missing", "source", "strong", "em", "code"];

  function make(manifest, hooks) {
    const listed = [...(manifest.blocks || []), ...(manifest.inline || [])].map((p) => p.name);
    const on = new Set(listed.filter((n) => IMPLEMENTED.includes(n)));
    listed.filter((n) => !IMPLEMENTED.includes(n)).forEach((n) => console.error(`Goo preset ${n} is listed but this renderer cannot draw it`));
    const h = Object.assign({
      link: (p) => `<a href="#${esc(p)}" data-path="${esc(p)}">${esc(p.split("/").filter(Boolean).pop() || p)}</a>`,
      live: (p, s) => `<span class="chip" contenteditable="false" data-live="${esc(p)}" data-slot="${esc(s)}">${esc(s)}</span>`,
      hole: (hint, bind) => `<span class="hole" contenteditable="false" data-hole="${esc(hint)}" data-bind="${esc(bind)}">${esc(hint || "blank")}</span>`,
      embed: (p) => `<div class="embed" contenteditable="false" data-embed="${esc(p)}"></div>`,
    }, hooks || {});

    // ---- inline: the stated pieces first (their text is literal), then the words around them
    function inline(s) {
      const keep = []; const put = (html) => `\u0000${keep.push(html) - 1}\u0000`;
      let t = String(s);
      t = t.replace(/\{\{([?!]?)\s*([^{}]*?)\s*\}\}/g, (m, mark, body) => {
        if (mark === "?" && on.has("hole")) { const b = body.match(/^(.*?)\s*(\/[^\s#]+#[A-Za-z0-9_]+)?$/); return put(h.hole((b[1] || "").trim(), b[2] || "")); }
        if (mark === "!" && on.has("missing")) return put(`<span class="missing" contenteditable="false" data-missing="${esc(body)}">${esc(body)}</span>`);
        if (!mark && on.has("value")) return put(`<span class="v" contenteditable="false" data-v="${esc(body)}">${esc(body)}</span>`);
        return m;
      });
      if (on.has("hole")) t = t.replace(/_{3,}/g, () => put(h.hole("", "")));
      if (on.has("source")) t = t.replace(/\^\[([^\]]+)\]/g, (m, b) => put(`<span class="src" contenteditable="false" data-src="${esc(b)}">${esc(b)}</span>`));
      if (on.has("code")) t = t.replace(/`([^`]+)`/g, (m, c) => put(`<code>${esc(c)}</code>`));
      t = esc(t);
      if (on.has("strong")) t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
      if (on.has("em")) t = t.replace(/(^|[^*\w])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>");
      t = t.replace(/(^|[\s(])(\/(?:h\/[xyz]\/\d+\/\d+\/)?[A-Za-z0-9_][^\s,;)<\u0000]*)/g, (m, sp, p) => {
        const clean = p.replace(/[.:!?]+$/, ""); const tail = p.slice(clean.length); const [name, slot] = clean.split("#");
        if (slot && on.has("live")) return sp + h.live(name, slot) + tail;
        if (!slot && on.has("link")) return sp + h.link(name) + tail;
        return m;
      });
      return t.replace(/\u0000(\d+)\u0000/g, (m, i) => keep[+i]);
    }

    // ---- blocks
    const LIST = /^(\s*)([-*]|\d+[.)])\s+(.*)$/;
    const STARTS = /^(#{1,3}\s|\s*([-*]|\d+[.)])\s|\s*>|\s*\||\s*\[\[|\s*---\s*$)/;
    function html(md) {
      const lines = String(md || "").replace(/\r\n/g, "\n").split("\n"); let out = ""; let i = 0;
      const list = () => {
        let s = ""; const stack = [];
        while (i < lines.length) {
          const m = lines[i].match(LIST); if (!m) break;
          const depth = Math.floor(m[1].replace(/\t/g, "  ").length / 2); const tag = /\d/.test(m[2]) ? "ol" : "ul";
          if (!on.has(tag === "ol" ? "numbered" : "list")) break;
          if (stack.length > depth) { while (stack.length > depth + 1) s += `</li></${stack.pop()}>`; s += "</li>"; }
          while (stack.length < depth + 1) { s += `<${tag}>`; stack.push(tag); }
          s += `<li>${inline(m[3])}`; i++;
        }
        while (stack.length) s += `</li></${stack.pop()}>`;
        return s;
      };
      while (i < lines.length) {
        const l = lines[i]; let m;
        if (!l.trim()) { i++; continue; }
        if (on.has("embed") && (m = l.match(/^\s*\[\[(\/[^\]]+)\]\]\s*$/))) { out += h.embed(m[1]); i++; continue; }
        if (on.has("divider") && /^\s*---\s*$/.test(l)) { out += "<hr>"; i++; continue; }
        if (on.has("heading") && (m = l.match(/^(#{1,3})\s+(.*)$/))) { out += `<h${m[1].length}>${inline(m[2])}</h${m[1].length}>`; i++; continue; }
        if (LIST.test(l) && on.has(/^\s*\d/.test(l) ? "numbered" : "list")) { out += list(); continue; }
        if (on.has("quote") && /^\s*>\s?/.test(l)) {
          const q = []; while (i < lines.length && /^\s*>\s?/.test(lines[i])) q.push(lines[i++].replace(/^\s*>\s?/, ""));
          const by = q.length > 1 && /^(—|--)\s*/.test(q[q.length - 1]) ? q.pop().replace(/^(—|--)\s*/, "") : null;
          out += `<blockquote>${q.map(inline).join("<br>")}${by !== null ? `<br><span class="qby" data-by="1">${inline(by)}</span>` : ""}</blockquote>`;
          continue;
        }
        if (on.has("table") && /^\s*\|.*\|\s*$/.test(l)) {
          const rows = []; while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) rows.push(lines[i++]);
          const cells = (r) => r.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
          const rule = (r) => /^\s*\|[\s:|-]+\|\s*$/.test(r); const head = rows.length > 1 && rule(rows[1]);
          const body = rows.filter((r) => !rule(r));
          out += `<div class="tablewrap"><table>${body.map((r, n) => `<tr>${cells(r).map((c) => (n === 0 && head ? `<th>${inline(c)}</th>` : `<td>${inline(c)}</td>`)).join("")}</tr>`).join("")}</table></div>`;
          continue;
        }
        const para = []; while (i < lines.length && lines[i].trim() && !STARTS.test(lines[i])) para.push(inline(lines[i++]));
        if (!para.length) { para.push(inline(lines[i++])); }
        out += `<p>${para.join("<br>")}</p>`;
      }
      return out;
    }

    // ---- back to text: what was drawn from a preset goes back to that preset's spelling
    function markdown(root) {
      const inl = (node) => {
        let s = "";
        node.childNodes.forEach((n) => {
          if (n.nodeType === 3) { s += n.textContent.replace(/ /g, " "); return; }
          if (n.nodeType !== 1) return;
          const t = n.tagName, d = n.dataset || {};
          if (d.live) s += `${d.live}#${d.slot}`;
          else if (d.hole !== undefined) s += `{{? ${[d.hole, d.bind].filter(Boolean).join(" ")}}}`;
          else if (d.v !== undefined) s += `{{${d.v}}}`;
          else if (d.missing !== undefined) s += `{{! ${d.missing}}}`;
          else if (d.src !== undefined) s += `^[${d.src}]`;
          else if (d.by) s += `— ${inl(n)}`;
          else if (t === "A" && d.path) s += d.path;
          else if (t === "STRONG" || t === "B") s += `**${inl(n)}**`;
          else if (t === "EM" || t === "I") s += `*${inl(n)}*`;
          else if (t === "CODE") s += "`" + n.textContent + "`";
          else if (t === "BR") s += "\n";
          else if (t === "DIV" || t === "P") s += (s && !s.endsWith("\n") ? "\n" : "") + inl(n);
          else s += inl(n);
        });
        return s;
      };
      const lists = (el, depth) => {
        let s = "";
        [...el.children].forEach((li, k) => {
          if (li.tagName !== "LI") return;
          const nested = [...li.children].filter((c) => c.tagName === "UL" || c.tagName === "OL");
          const clone = li.cloneNode(true); clone.querySelectorAll("ul,ol").forEach((x) => x.remove());
          s += `${"  ".repeat(depth)}${el.tagName === "OL" ? `${k + 1}.` : "-"} ${inl(clone).replace(/\n/g, " ").trim()}\n`;
          nested.forEach((nl) => (s += lists(nl, depth + 1)));
        });
        return s;
      };
      const blocks = [];
      root.childNodes.forEach((n) => {
        if (n.nodeType === 3) { if (n.textContent.trim()) blocks.push(n.textContent.trim()); return; }
        if (n.nodeType !== 1) return;
        const t = n.tagName;
        if (n.dataset && n.dataset.embed) blocks.push(`[[${n.dataset.embed}]]`);
        else if (t === "HR") blocks.push("---");
        else if (/^H[1-6]$/.test(t)) blocks.push(`${"#".repeat(Math.min(3, +t[1]))} ${inl(n).trim()}`);
        else if (t === "UL" || t === "OL") blocks.push(lists(n, 0).trimEnd());
        else if (t === "BLOCKQUOTE") blocks.push(inl(n).split("\n").map((l) => `> ${l}`).join("\n"));
        else if (t === "TABLE" || (n.querySelector && n.querySelector("table"))) {
          const rows = [...n.querySelectorAll("tr")].map((tr) => "| " + [...tr.children].map((c) => inl(c).replace(/\|/g, "/").replace(/\n/g, " ").trim()).join(" | ") + " |");
          if (rows.length) { const head = n.querySelector("th") ? [rows[0], "|" + " --- |".repeat(rows[0].split("|").length - 2)] : [rows[0]]; blocks.push([...head, ...rows.slice(1)].join("\n")); }
        } else { const s = inl(n).trim(); if (s) blocks.push(s); }
      });
      return blocks.join("\n\n").replace(/\n{3,}/g, "\n\n").trim();
    }

    // the text as it streams: the blocks finished so far, and the one still arriving
    function split(md) { const parts = String(md).split(/\n[ \t]*\n/); return { done: parts.slice(0, -1), open: parts[parts.length - 1] }; }

    return { html, inline, markdown, split, has: (n) => on.has(n), manifest };
  }

  async function load(url, hooks) {
    const r = await fetch(url || "/goo/presets.json", { credentials: "same-origin" });
    if (!r.ok) throw new Error(`Goo presets: ${r.status}`);
    return make(await r.json(), hooks);
  }

  global.GooPresets = { load, make, esc };
})(typeof window !== "undefined" ? window : globalThis);

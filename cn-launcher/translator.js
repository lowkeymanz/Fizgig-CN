// Fizgig 中文界面桥接 —— 前端翻译脚本（DOM 层）。
// 只翻译词典中明确列出的完整短语，绝不做"所有英文 -> 中文"的兜底替换。
// 不碰：用户输入、路径、模型名、触发词、键值、URL、代码、script/style、contenteditable。
(function () {
  "use strict";

  var exact = Object.create(null);
  var regexes = [];
  var ready = false;

  function compile(phrases) {
    exact = Object.create(null);
    regexes = [];
    (phrases || []).forEach(function (p) {
      if (!p) return;
      if (p.re) {
        // 不以 ^ 开头的正则用于长句里的片段替换（锚定整句的规则不参与）
        var partial = !/^\^/.test(p.re);
        try { regexes.push([new RegExp(p.re), p.zh, partial]); } catch (e) {}
      } else if (p.en) {
        exact[p.en] = p.zh;
      }
    });
  }

  // 翻译一个字符串；命中返回中文，未命中返回 null
  function apply(text) {
    var s = String(text);
    if (exact[s] !== undefined) return exact[s];

    var trimmed = s.trim();
    if (!trimmed) return null;
    if (trimmed !== s && exact[trimmed] !== undefined) return s.replace(trimmed, exact[trimmed]);

    // 折叠换行 / 连续空白：HTML 里的多行段落渲染后仍带换行与缩进
    var t = trimmed.replace(/\s+/g, " ");
    if (exact[t] !== undefined) return s.replace(trimmed, exact[t]);

    // 尾随冒号（schema label 渲染时带 ":"）
    var noColon = t.replace(/[:：]\s*$/, "");
    if (noColon !== t && exact[noColon] !== undefined) {
      return s.replace(trimmed, exact[noColon] + t.slice(noColon.length));
    }

    // 正则 / 占位符（只用于整句匹配：锚定的规则）
    for (var i = 0; i < regexes.length; i++) {
      if (regexes[i][2]) continue;
      var m = regexes[i][0].exec(t);
      if (m) {
        var out = regexes[i][1].replace(/\$(\d+)/g, function (_, g) {
          return m[Number(g)] || "";
        });
        return s.replace(trimmed, out);
      }
    }

    // 片段级替换：整句由多段拼成时，把命中的片段逐个换成中文
    var res = s, hit = false;
    for (var k = 0; k < regexes.length; k++) {
      if (!regexes[k][2]) continue;
      var prx = regexes[k][0], pzh = regexes[k][1];
      if (!prx.test(res)) continue;
      res = res.replace(prx, function () {
        var a = arguments;
        return pzh.replace(/\$(\d+)/g, function (_, g) { return a[Number(g)] || ""; });
      });
      hit = true;
    }
    return hit && res !== s ? res : null;
  }

  var SKIP_TAGS = {
    SCRIPT: 1, STYLE: 1, NOSCRIPT: 1, TEXTAREA: 1, CODE: 1, PRE: 1, IFRAME: 1
  };

  function skipElement(node) {
    if (SKIP_TAGS[node.tagName]) return true;
    var ce = node.getAttribute && node.getAttribute("contenteditable");
    return ce === "true" || ce === "";
  }

  function translateTextNode(node) {
    var p = node.parentNode;
    if (!p || p.nodeType !== 1 || skipElement(p)) return;
    var t = apply(node.nodeValue);
    if (t !== null && t !== node.nodeValue) node.nodeValue = t;
  }

  var ATTRS = ["title", "placeholder", "aria-label"];
  function translateAttrs(el) {
    for (var i = 0; i < ATTRS.length; i++) {
      var a = ATTRS[i];
      if (!el.hasAttribute || !el.hasAttribute(a)) continue;
      var v = el.getAttribute(a);
      if (!v) continue;
      var t = apply(v);
      if (t !== null && t !== v) el.setAttribute(a, t);
    }
  }

  function walk(root) {
    if (!root) return;
    if (root.nodeType === 3) { translateTextNode(root); return; }
    if (root.nodeType !== 1) return;
    if (skipElement(root)) return;
    translateAttrs(root);
    var child = root.firstChild;
    while (child) {
      var next = child.nextSibling;
      walk(child);
      child = next;
    }
  }

  function startObserver() {
    var mo = new MutationObserver(function (muts) {
      if (!ready) return;
      for (var i = 0; i < muts.length; i++) {
        var m = muts[i];
        if (m.type === "childList") {
          for (var j = 0; j < m.addedNodes.length; j++) walk(m.addedNodes[j]);
        } else if (m.type === "characterData") {
          walk(m.target);
        } else if (m.type === "attributes" && m.attributeName &&
                   ATTRS.indexOf(m.attributeName) !== -1) {
          translateAttrs(m.target);
        }
      }
    });
    mo.observe(document.documentElement, {
      childList: true, subtree: true, characterData: true,
      attributes: true, attributeFilter: ATTRS
    });
  }

  function boot() {
    startObserver();
    fetch("/__cn__/dict.json", { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        compile(d && d.phrases || []);
        ready = true;
        walk(document.body || document.documentElement);
      })
      .catch(function () {
        // 词典加载失败：不翻译，保持英文（降级安全）
        ready = true;
      });
  }

  if (document.body) boot();
  else document.addEventListener("DOMContentLoaded", boot);
})();

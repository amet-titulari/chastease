(() => {
  function mdToHtml(md) {
    return md
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/^#{3}\s+(.+)$/gm, "<h4>$1</h4>")
      .replace(/^#{2}\s+(.+)$/gm, "<h3>$1</h3>")
      .replace(/^#{1}\s+(.+)$/gm, "<h2>$1</h2>")
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.+?)\*/g, "<em>$1</em>")
      .replace(/^[-–]\s+(.+)$/gm, "<li>$1</li>")
      .replace(/(<li>.*<\/li>\n?)+/g, (match) => `<ul>${match}</ul>`)
      .replace(/^\|(.+)\|$/gm, (_, row) => {
        if (row.split("|").every((cell) => /^[:\- ]+$/.test(cell.trim()))) return "";
        const cells = row.split("|").map((cell) => `<td>${cell.trim()}</td>`).join("");
        return `<tr>${cells}</tr>`;
      })
      .replace(/(<tr>.*<\/tr>\n?)+/g, (match) => {
        let first = true;
        return "<table>" + match.replace(/<tr>(.*?)<\/tr>/g, (_, cells) => {
          if (first) {
            first = false;
            return "<thead><tr>" + cells.replace(/<td>/g, "<th>").replace(/<\/td>/g, "</th>") + "</tr></thead><tbody>";
          }
          return `<tr>${cells}</tr>`;
        }) + "</tbody></table>";
      })
      .replace(/^-{3,}$/gm, "<hr>")
      .replace(/\n{2,}/g, "</p><p>")
      .replace(/^(.+)$/gm, (line) => (line.startsWith("<") ? line : line));
  }

  const el = document.getElementById("contract-body");
  if (!el) return;
  const raw = el.dataset.raw || el.textContent || "";
  el.innerHTML = `<div class="md-body">${mdToHtml(raw)}</div>`;
})();

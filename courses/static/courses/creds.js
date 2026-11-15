// Build the one-time credentials CSV in the browser; nothing is fetched again.
(function () {
  var btn = document.getElementById('dl-creds');
  if (!btn) return;
  function cell(s) {
    s = String(s);
    if (/^[=+\-@\t\r]/.test(s)) s = "'" + s;            // no formula injection in Excel
    return '"' + s.replace(/"/g, '""') + '"';
  }
  btn.addEventListener('click', function () {
    var rows = [];
    document.querySelectorAll('#creds tr').forEach(function (tr) {
      rows.push(Array.prototype.map.call(tr.children, function (td) { return cell(td.textContent.trim()); }).join(','));
    });
    var blob = new Blob(['﻿' + rows.join('\r\n')], { type: 'text/csv;charset=utf-8' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'mat_khau_tam.csv';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
  });
})();

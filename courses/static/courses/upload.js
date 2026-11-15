// File picker for the submission form: drag-and-drop, show the chosen name,
// and keep the submit button disabled until a file is chosen.
(function () {
  var drop = document.getElementById('drop');
  if (!drop) return;
  var input = drop.querySelector('input[type=file]');
  var name = document.getElementById('fname');
  var btn = document.getElementById('submit-btn');
  var hint = document.getElementById('submit-hint');
  function update() {
    var f = input.files[0];
    name.textContent = f ? '📄 ' + f.name : '';
    if (btn) btn.disabled = !f;
    if (hint) hint.style.display = f ? 'none' : '';
  }
  input.addEventListener('change', update);
  ['dragenter', 'dragover'].forEach(function (e) {
    drop.addEventListener(e, function (ev) { ev.preventDefault(); drop.classList.add('over'); });
  });
  ['dragleave', 'drop'].forEach(function (e) {
    drop.addEventListener(e, function (ev) { ev.preventDefault(); drop.classList.remove('over'); });
  });
  drop.addEventListener('drop', function (ev) {
    input.files = ev.dataTransfer.files;
    update();
  });
  update();
})();

// Drag-and-drop file picker for the submission form.
(function () {
  var drop = document.getElementById('drop');
  if (!drop) return;
  var input = drop.querySelector('input[type=file]');
  var name = document.getElementById('fname');
  input.addEventListener('change', function () {
    name.textContent = input.files[0] ? input.files[0].name : '';
  });
  ['dragenter', 'dragover'].forEach(function (e) {
    drop.addEventListener(e, function (ev) { ev.preventDefault(); drop.classList.add('over'); });
  });
  ['dragleave', 'drop'].forEach(function (e) {
    drop.addEventListener(e, function (ev) { ev.preventDefault(); drop.classList.remove('over'); });
  });
  drop.addEventListener('drop', function (ev) {
    input.files = ev.dataTransfer.files;
    input.dispatchEvent(new Event('change'));
  });
})();

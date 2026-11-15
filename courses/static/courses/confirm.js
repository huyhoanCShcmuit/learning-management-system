// Ask before removing someone from a course.
document.querySelectorAll('form.confirm-remove').forEach(function (f) {
  f.addEventListener('submit', function (ev) {
    if (!confirm('Xoá ' + f.dataset.name + ' khỏi khoá? Bài nộp cũ vẫn được giữ.')) ev.preventDefault();
  });
});

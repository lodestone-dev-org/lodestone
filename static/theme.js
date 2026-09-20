(function () {
    var saved = localStorage.getItem('lodestone-theme');
    if (saved) {
        document.documentElement.setAttribute('data-bs-theme', saved);
    }
})();

document.addEventListener('DOMContentLoaded', function () {
    var toggle = document.getElementById('theme-toggle');
    if (!toggle) {
        return;
    }

    toggle.checked = document.documentElement.getAttribute('data-bs-theme') === 'light';

    toggle.addEventListener('change', function () {
        var theme = toggle.checked ? 'light' : 'dark';
        document.documentElement.setAttribute('data-bs-theme', theme);
        localStorage.setItem('lodestone-theme', theme);
    });
});

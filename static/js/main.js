/* CivicFix shared frontend behaviour */

(function () {
    'use strict';

    function ready(fn) {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', fn);
        } else {
            fn();
        }
    }

    function csrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

    function showToast(message, type) {
        var stack = document.getElementById('flash-stack');
        if (!stack) return;
        var item = document.createElement('div');
        item.className = 'toast-item toast-' + (type || 'info');
        item.setAttribute('role', 'status');
        var icon = document.createElement('i');
        icon.className = 'bi ' + (type === 'success' ? 'bi-check-circle-fill' : type === 'danger' ? 'bi-exclamation-octagon-fill' : 'bi-info-circle-fill');
        var text = document.createElement('span');
        text.textContent = message;
        var close = document.createElement('button');
        close.type = 'button';
        close.className = 'toast-close';
        close.innerHTML = '<i class="bi bi-x"></i>';
        close.addEventListener('click', function () { item.remove(); });
        item.appendChild(icon);
        item.appendChild(text);
        item.appendChild(close);
        stack.appendChild(item);
        setTimeout(function () { item.remove(); }, 5500);
    }

    function dismissToast(element) {
        element.style.opacity = '0';
        setTimeout(function () { element.remove(); }, 180);
    }

    function postJSON(url, data) {
        return fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken() },
            credentials: 'same-origin',
            body: JSON.stringify(data || {})
        }).then(function (response) {
            return response.json().catch(function () { return {}; }).then(function (body) {
                if (!response.ok) {
                    var error = new Error(body.error || body.message || 'Request failed');
                    error.status = response.status;
                    error.body = body;
                    throw error;
                }
                return body;
            });
        });
    }

    ready(function () {
        var navToggle = document.getElementById('navToggle');
        var navLinks = document.getElementById('navLinks');
        if (navToggle && navLinks) {
            navToggle.addEventListener('click', function () {
                var open = navLinks.classList.toggle('is-open');
                navToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
            });
        }

        var sidebar = document.getElementById('dashSidebar');
        var sidebarToggle = document.getElementById('sidebarToggle');
        var sidebarClose = document.getElementById('sidebarClose');
        if (sidebarToggle) {
            sidebarToggle.setAttribute('aria-expanded', window.innerWidth <= 1024 ? 'false' : 'true');
        }
        if (sidebarToggle && sidebar) {
            sidebarToggle.addEventListener('click', function () {
                if (window.innerWidth <= 1024) {
                    var open = sidebar.classList.toggle('is-open');
                    sidebarToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
                } else {
                    var collapsed = document.body.classList.toggle('sidebar-collapsed');
                    sidebarToggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
                }
            });
        }
        if (sidebarClose && sidebar) {
            sidebarClose.addEventListener('click', function () {
                if (window.innerWidth <= 1024) {
                    sidebar.classList.remove('is-open');
                    if (sidebarToggle) sidebarToggle.setAttribute('aria-expanded', 'false');
                } else {
                    document.body.classList.add('sidebar-collapsed');
                    if (sidebarToggle) sidebarToggle.setAttribute('aria-expanded', 'false');
                }
            });
        }
        if (sidebar) {
            document.addEventListener('click', function (event) {
                if (window.innerWidth <= 1024 && sidebar.classList.contains('is-open') &&
                    !sidebar.contains(event.target) && !(sidebarToggle && sidebarToggle.contains(event.target))) {
                    sidebar.classList.remove('is-open');
                    if (sidebarToggle) sidebarToggle.setAttribute('aria-expanded', 'false');
                }
            });
        }
        window.addEventListener('resize', function () {
            if (window.innerWidth > 1024 && sidebar) sidebar.classList.remove('is-open');
            if (window.innerWidth <= 1024) document.body.classList.remove('sidebar-collapsed');
            if (sidebarToggle) {
                var expanded = window.innerWidth <= 1024
                    ? Boolean(sidebar && sidebar.classList.contains('is-open'))
                    : !document.body.classList.contains('sidebar-collapsed');
                sidebarToggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
            }
        });

        document.querySelectorAll('[data-dismiss-toast]').forEach(function (button) {
            button.addEventListener('click', function () { dismissToast(button.closest('[data-toast]')); });
        });
        document.querySelectorAll('[data-toast]').forEach(function (item) {
            setTimeout(function () { if (item.isConnected) dismissToast(item); }, 5500);
        });

        document.querySelectorAll('[data-password-toggle]').forEach(function (button) {
            button.addEventListener('click', function () {
                var input = document.getElementById(button.getAttribute('data-password-toggle'));
                if (!input) return;
                var reveal = input.type === 'password';
                input.type = reveal ? 'text' : 'password';
                button.innerHTML = '<i class="bi bi-' + (reveal ? 'eye-slash' : 'eye') + '"></i>';
            });
        });

        document.querySelectorAll('form[data-loading]').forEach(function (form) {
            form.addEventListener('submit', function () {
                var buttons = form.querySelectorAll('button[type="submit"]');
                buttons.forEach(function (button) {
                    button.disabled = true;
                    if (!button.dataset.original) button.dataset.original = button.innerHTML;
                    button.innerHTML = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span> Working...';
                });
            });
        });

        var notifDot = document.getElementById('notifDot');
        if (notifDot) {
            fetch('/api/notifications/unread-count', { credentials: 'same-origin' })
                .then(function (response) { return response.ok ? response.json() : {}; })
                .then(function (data) {
                    if (data.count > 0) notifDot.classList.add('has-unread');
                })
                .catch(function () {});
        }
    });

    window.civicfix = { csrfToken: csrfToken, postJSON: postJSON, showToast: showToast };
})();

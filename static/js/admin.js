/* Administrator interface helpers */

(function () {
    'use strict';

    function openModal(id) {
        var modal = document.getElementById(id);
        if (modal) {
            modal.classList.add('is-open');
            document.body.style.overflow = 'hidden';
        }
    }

    function closeModal(id) {
        var modal = document.getElementById(id);
        if (modal) {
            modal.classList.remove('is-open');
            if (!document.querySelector('.modal-backdrop.is-open')) {
                document.body.style.overflow = '';
            }
        }
    }

    function filterStaff() {
        var department = document.getElementById('assignDepartment');
        var staffSelect = document.querySelector('select[name="staff_id"]');
        if (!department || !staffSelect) return;
        function apply() {
            var selected = department.value;
            Array.prototype.forEach.call(staffSelect.options, function (option) {
                if (!option.value) return;
                var dept = option.getAttribute('data-department') || '';
                option.hidden = Boolean(selected) && Boolean(dept) && dept !== selected;
            });
        }
        department.addEventListener('change', apply);
        apply();
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('.modal-backdrop').forEach(function (backdrop) {
            backdrop.addEventListener('click', function (event) {
                if (event.target === backdrop) closeModal(backdrop.id);
            });
        });
        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') {
                document.querySelectorAll('.modal-backdrop.is-open').forEach(function (modal) {
                    closeModal(modal.id);
                });
            }
        });
        filterStaff();
    });

    function renderCharts() {
        if (typeof Chart === 'undefined' || !window.civicfixCharts) return;
        var data = window.civicfixCharts;
        var colors = ['#1D4ED8', '#06B6D4', '#16a34a', '#f59e0b', '#7c3aed', '#dc2626', '#64748b', '#0ea5e9'];

        var category = document.getElementById('adminCategoryChart');
        if (category) {
            new Chart(category, {
                type: 'bar',
                data: { labels: data.categoryLabels, datasets: [{ data: data.categoryValues, backgroundColor: '#1D4ED8', borderRadius: 6, maxBarThickness: 34 }] },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: '#eef2f6' } }, x: { grid: { display: false }, ticks: { font: { size: 10 } } } } }
            });
        }
        var status = document.getElementById('adminStatusChart');
        if (status) {
            new Chart(status, {
                type: 'doughnut',
                data: { labels: data.statusLabels, datasets: [{ data: data.statusValues, backgroundColor: colors, borderWidth: 0, hoverOffset: 6 }] },
                options: { responsive: true, maintainAspectRatio: false, cutout: '68%', plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, usePointStyle: true, font: { size: 11 } } } } }
            });
        }
        var trend = document.getElementById('adminTrendChart');
        if (trend) {
            new Chart(trend, {
                type: 'line',
                data: { labels: data.monthLabels, datasets: [{ data: data.monthValues, borderColor: '#1D4ED8', backgroundColor: 'rgba(29,78,216,.12)', fill: true, tension: .35, pointRadius: 3 }] },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: '#eef2f6' } }, x: { grid: { display: false } } } }
            });
        }
        var dept = document.getElementById('adminDeptChart');
        if (dept) {
            new Chart(dept, {
                type: 'bar',
                data: { labels: data.deptLabels, datasets: [{ data: data.deptValues, backgroundColor: '#16a34a', borderRadius: 6, maxBarThickness: 34 }] },
                options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: '#eef2f6' } }, y: { grid: { display: false } } } }
            });
        }
    }

    document.addEventListener('DOMContentLoaded', renderCharts);

    window.civicfixAdmin = { openModal: openModal, closeModal: closeModal };
})();

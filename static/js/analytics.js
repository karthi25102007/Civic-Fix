(function () {
    'use strict';
    window.addEventListener('DOMContentLoaded', function () {
        if (typeof Chart === 'undefined' || !window.civicfixAnalytics) return;
        var data = window.civicfixAnalytics;
        var colors = ['#1D4ED8', '#06B6D4', '#16a34a', '#f59e0b', '#7c3aed', '#dc2626', '#64748b', '#0ea5e9'];

        var category = document.getElementById('analyticsCategory');
        if (category) {
            new Chart(category, {
                type: 'bar',
                data: { labels: data.categoryLabels, datasets: [{ data: data.categoryValues, backgroundColor: '#1D4ED8', borderRadius: 6, maxBarThickness: 34 }] },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: '#eef2f6' } }, x: { grid: { display: false }, ticks: { font: { size: 10 } } } } }
            });
        }

        var status = document.getElementById('analyticsStatus');
        if (status) {
            new Chart(status, {
                type: 'doughnut',
                data: { labels: data.statusLabels, datasets: [{ data: data.statusValues, backgroundColor: colors, borderWidth: 0, hoverOffset: 6 }] },
                options: { responsive: true, maintainAspectRatio: false, cutout: '68%', plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, usePointStyle: true, font: { size: 11 } } } } }
            });
        }

        var trend = document.getElementById('analyticsTrend');
        if (trend) {
            new Chart(trend, {
                type: 'line',
                data: { labels: data.monthLabels, datasets: [{ data: data.monthValues, borderColor: '#06B6D4', backgroundColor: 'rgba(6,182,212,.14)', fill: true, tension: .35, pointRadius: 3 }] },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: '#eef2f6' } }, x: { grid: { display: false } } } }
            });
        }

        var priority = document.getElementById('analyticsPriority');
        if (priority) {
            new Chart(priority, {
                type: 'doughnut',
                data: { labels: data.priorityLabels, datasets: [{ data: data.priorityValues, backgroundColor: ['#dc2626', '#f97316', '#1D4ED8', '#64748b'], borderWidth: 0, hoverOffset: 6 }] },
                options: { responsive: true, maintainAspectRatio: false, cutout: '68%', plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, usePointStyle: true, font: { size: 11 } } } } }
            });
        }

        var departments = document.getElementById('analyticsDepartments');
        if (departments) {
            new Chart(departments, {
                type: 'bar',
                data: { labels: data.deptLabels, datasets: [{ data: data.deptValues, backgroundColor: '#7c3aed', borderRadius: 6, maxBarThickness: 34 }] },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: '#eef2f6' } }, x: { grid: { display: false }, ticks: { font: { size: 10 } } } } }
            });
        }
    });
})();

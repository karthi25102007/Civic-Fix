/* Citizen dashboard charts */

(function () {
    'use strict';
    window.addEventListener('DOMContentLoaded', function () {
        if (typeof Chart === 'undefined' || !window.civicfixCharts) return;
        var data = window.civicfixCharts;
        var colors = ['#1D4ED8', '#06B6D4', '#16a34a', '#f59e0b', '#7c3aed', '#dc2626', '#64748b', '#0ea5e9'];

        var statusCanvas = document.getElementById('citizenStatusChart');
        if (statusCanvas) {
            new Chart(statusCanvas, {
                type: 'doughnut',
                data: {
                    labels: data.statusLabels,
                    datasets: [{ data: data.statusValues, backgroundColor: colors, borderWidth: 0, hoverOffset: 6 }]
                },
                options: {
                    responsive: true, maintainAspectRatio: false, cutout: '68%',
                    plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, usePointStyle: true, font: { size: 11 } } } }
                }
            });
        }

        var categoryCanvas = document.getElementById('citizenCategoryChart');
        if (categoryCanvas) {
            new Chart(categoryCanvas, {
                type: 'bar',
                data: {
                    labels: data.categoryLabels,
                    datasets: [{ data: data.categoryValues, backgroundColor: '#1D4ED8', borderRadius: 6, maxBarThickness: 34 }]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: { y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: '#eef2f6' } }, x: { grid: { display: false }, ticks: { font: { size: 10 } } } }
                }
            });
        }
    });
})();

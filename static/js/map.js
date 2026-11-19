/* Leaflet map helpers: report location picker, detail marker and city issue map */

(function () {
    'use strict';

    var DEFAULT_CENTER = [13.0827, 80.2707];
    var TILE_URL = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
    var TILE_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
    var COLOR_BY_STATUS = {
        'Submitted': '#6366f1', 'Under Review': '#f59e0b', 'Verified': '#06b6d4',
        'Assigned': '#7c3aed', 'In Progress': '#1d4ed8', 'Resolved': '#16a34a',
        'Reopened': '#ea580c', 'Rejected': '#dc2626'
    };
    var COLOR_BY_PRIORITY = { 'Low': '#64748b', 'Medium': '#1d4ed8', 'High': '#f97316', 'Urgent': '#dc2626' };

    function markerIcon(color) {
        return L.divIcon({
            className: '',
            html: '<span style="display:block;width:16px;height:16px;border-radius:50%;background:' + color +
                  ';border:3px solid #fff;box-shadow:0 2px 6px rgba(15,23,42,.35)"></span>',
            iconSize: [22, 22], iconAnchor: [11, 11]
        });
    }

    function tiles() {
        return L.tileLayer(TILE_URL, { attribution: TILE_ATTRIBUTION, maxZoom: 19 });
    }

    function initPicker() {
        var element = document.getElementById('reportMap');
        if (!element) return;
        var latInput = document.getElementById('latitude');
        var lngInput = document.getElementById('longitude');
        var map = L.map(element).setView(DEFAULT_CENTER, 13);
        tiles().addTo(map);
        var marker = null;

        function place(lat, lng) {
            if (marker) map.removeLayer(marker);
            marker = L.marker([lat, lng], { draggable: true }).addTo(map);
            marker.bindPopup('Issue location').openPopup();
            marker.on('dragend', function () {
                var position = marker.getLatLng();
                latInput.value = position.lat.toFixed(7);
                lngInput.value = position.lng.toFixed(7);
                if (typeof checkDuplicates === 'function') checkDuplicates();
            });
            latInput.value = lat.toFixed(7);
            lngInput.value = lng.toFixed(7);
        }

        map.on('click', function (event) { place(event.latlng.lat, event.latlng.lng); });

        var useLocation = document.getElementById('useLocation');
        if (useLocation) {
            useLocation.addEventListener('click', function () {
                if (!navigator.geolocation) {
                    window.civicfix.showToast('Geolocation is not supported by this browser.', 'danger');
                    return;
                }
                useLocation.disabled = true;
                navigator.geolocation.getCurrentPosition(function (position) {
                    var lat = position.coords.latitude;
                    var lng = position.coords.longitude;
                    map.setView([lat, lng], 15);
                    place(lat, lng);
                    useLocation.disabled = false;
                }, function () {
                    window.civicfix.showToast('Location permission denied. Click the map or enter coordinates instead.', 'warning');
                    useLocation.disabled = false;
                }, { timeout: 10000 });
            });
        }

        if (latInput.value && lngInput.value) {
            place(parseFloat(latInput.value), parseFloat(lngInput.value));
        }
        window.civicfixPicker = { map: map, place: place };
    }

    function initDetailMap() {
        var element = document.getElementById('detailMap');
        if (!element) return;
        var lat = parseFloat(element.dataset.lat);
        var lng = parseFloat(element.dataset.lng);
        if (isNaN(lat) || isNaN(lng)) return;
        var map = L.map(element).setView([lat, lng], 15);
        tiles().addTo(map);
        L.marker([lat, lng]).addTo(map).bindPopup('Reported location').openPopup();
    }

    window.initCityMap = function (complaints) {
        var element = document.getElementById('cityMap');
        if (!element || typeof L === 'undefined') return;
        var map = L.map(element).setView(DEFAULT_CENTER, 12);
        tiles().addTo(map);
        var markers = [];
        var byId = {};

        complaints.forEach(function (item) {
            if (item.latitude == null || item.longitude == null) return;
            var colorBy = document.getElementById('mapColorBy');
            var mode = colorBy ? colorBy.value : 'status';
            var color = mode === 'priority' ? COLOR_BY_PRIORITY[item.priority] : COLOR_BY_STATUS[item.status];
            var icon = markerIcon(color);
            var popup = '<div class="popup-title">' + escapeHtml(item.title) + '</div>' +
                '<div class="popup-meta">' + escapeHtml(item.tracking_number) + ' · ' + escapeHtml(item.status) + '</div>' +
                '<div class="popup-meta">' + escapeHtml(item.location_address) + '</div>' +
                '<a class="btn btn-sm btn-primary" href="/complaints/' + item.id + '">View details</a>';
            var marker = L.marker([item.latitude, item.longitude], { icon: icon }).addTo(map).bindPopup(popup);
            marker._civicfix = item;
            markers.push(marker);
            byId[item.id] = item;
        });

        window.civicfixCityMap = {
            map: map,
            markers: markers,
            applyFilters: function () {
                var category = document.getElementById('mapCategory');
                var status = document.getElementById('mapStatus');
                var priority = document.getElementById('mapPriority');
                var selectedCategory = category ? category.value : '';
                var selectedStatus = status ? status.value : '';
                var selectedPriority = priority ? priority.value : '';
                markers.forEach(function (marker) {
                    var item = marker._civicfix;
                    var show = (!selectedCategory || String(item.category_id) === selectedCategory) &&
                        (!selectedStatus || item.status === selectedStatus) &&
                        (!selectedPriority || item.priority === selectedPriority);
                    if (show) {
                        if (!map.hasLayer(marker)) marker.addTo(map);
                    } else if (map.hasLayer(marker)) {
                        map.removeLayer(marker);
                    }
                });
            },
            refreshColors: function () {
                var colorBy = document.getElementById('mapColorBy');
                var mode = colorBy ? colorBy.value : 'status';
                markers.forEach(function (marker) {
                    var item = marker._civicfix;
                    var color = mode === 'priority' ? COLOR_BY_PRIORITY[item.priority] : COLOR_BY_STATUS[item.status];
                    marker.setIcon(markerIcon(color));
                });
            }
        };
    };

    function escapeHtml(value) {
        return String(value == null ? '' : value).replace(/[&<>"']/g, function (char) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char];
        });
    }

    window.addEventListener('DOMContentLoaded', function () {
        if (typeof L === 'undefined') return;
        initPicker();
        initDetailMap();
    });
})();

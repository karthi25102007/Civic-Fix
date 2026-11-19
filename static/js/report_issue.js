/* Report form: image previews, duplicate suggestions and map coordination */

(function () {
    'use strict';

    var allowedTypes = ['image/png', 'image/jpeg', 'image/webp', 'image/gif'];
    var maxBytes = 5 * 1024 * 1024;
    var selectedFiles = [];

    function csrf() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

    function renderPreview() {
        var preview = document.getElementById('imagePreview');
        if (!preview) return;
        preview.innerHTML = '';
        selectedFiles.forEach(function (file, index) {
            var holder = document.createElement('div');
            holder.className = 'preview-item';
            var image = document.createElement('img');
            image.alt = file.name;
            image.src = URL.createObjectURL(file);
            var remove = document.createElement('button');
            remove.type = 'button';
            remove.className = 'preview-remove';
            remove.innerHTML = '<i class="bi bi-x"></i>';
            remove.addEventListener('click', function () {
                selectedFiles.splice(index, 1);
                syncInput();
                renderPreview();
            });
            holder.appendChild(image);
            holder.appendChild(remove);
            preview.appendChild(holder);
        });
    }

    function syncInput() {
        var input = document.getElementById('imageInput');
        if (!input) return;
        var transfer = new DataTransfer();
        selectedFiles.forEach(function (file) { transfer.items.add(file); });
        input.files = transfer.files;
    }

    function acceptFiles(files) {
        var added = 0;
        Array.prototype.forEach.call(files, function (file) {
            if (selectedFiles.length >= 4) return;
            if (allowedTypes.indexOf(file.type) === -1) {
                window.civicfix.showToast('Only PNG, JPG, WEBP and GIF images are allowed.', 'danger');
                return;
            }
            if (file.size > maxBytes) {
                window.civicfix.showToast('An image exceeds the 5 MB limit.', 'danger');
                return;
            }
            selectedFiles.push(file);
            added += 1;
        });
        if (added) {
            syncInput();
            renderPreview();
        }
    }

    function renderMatches(matches) {
        var container = document.getElementById('duplicateMatches');
        var banner = document.getElementById('duplicateBanner');
        if (!container || !banner) return;
        container.innerHTML = '';
        if (!matches.length) {
            banner.hidden = true;
            return;
        }
        matches.forEach(function (item) {
            var row = document.createElement('div');
            row.className = 'd-flex align-center gap-2 flex-wrap mb-2';
            var link = document.createElement('a');
            link.href = '/complaints/' + item.id;
            link.className = 'text-sm fw-700';
            link.textContent = item.tracking_number + ' — ' + item.title;
            var status = document.createElement('span');
            status.className = 'badge badge-' + item.status.toLowerCase().replace(/ /g, '-');
            status.textContent = item.status;
            var supportForm = document.createElement('form');
            supportForm.method = 'post';
            supportForm.action = '/complaints/' + item.id + '/support';
            var token = document.createElement('input');
            token.type = 'hidden';
            token.name = 'csrf_token';
            token.value = csrf();
            var supportButton = document.createElement('button');
            supportButton.type = 'submit';
            supportButton.className = 'btn btn-sm btn-primary';
            supportButton.textContent = 'Support existing';
            supportForm.appendChild(token);
            supportForm.appendChild(supportButton);
            row.appendChild(link);
            row.appendChild(status);
            row.appendChild(supportForm);
            container.appendChild(row);
        });
        banner.hidden = false;
    }

    window.checkDuplicates = function () {
        var titleInput = document.getElementById('title');
        var categoryInput = document.getElementById('category_id');
        if (!titleInput || !categoryInput || titleInput.value.trim().length < 6 || !categoryInput.value) return;
        var lat = document.getElementById('latitude');
        var lng = document.getElementById('longitude');
        window.civicfix.postJSON('/api/complaints/duplicate-check', {
            title: titleInput.value,
            category_id: categoryInput.value,
            latitude: lat && lat.value ? lat.value : null,
            longitude: lng && lng.value ? lng.value : null
        }).then(function (response) {
            renderMatches(response.matches || []);
        }).catch(function () {});
    };

    window.addEventListener('DOMContentLoaded', function () {
        var input = document.getElementById('imageInput');
        var zone = document.getElementById('uploadZone');
        if (input && zone) {
            zone.addEventListener('click', function (event) {
                if (event.target !== input) input.click();
            });
            input.addEventListener('change', function () { acceptFiles(input.files); });
            ['dragenter', 'dragover'].forEach(function (name) {
                zone.addEventListener(name, function (event) { event.preventDefault(); zone.classList.add('dragover'); });
            });
            ['dragleave', 'drop'].forEach(function (name) {
                zone.addEventListener(name, function (event) { event.preventDefault(); zone.classList.remove('dragover'); });
            });
            zone.addEventListener('drop', function (event) { acceptFiles(event.dataTransfer.files); });
        }

        var titleInput = document.getElementById('title');
        if (titleInput) titleInput.addEventListener('blur', window.checkDuplicates);
        var categoryInput = document.getElementById('category_id');
        if (categoryInput) categoryInput.addEventListener('change', window.checkDuplicates);
        var dismiss = document.getElementById('dismissDuplicate');
        if (dismiss) dismiss.addEventListener('click', function () {
            var banner = document.getElementById('duplicateBanner');
            if (banner) banner.hidden = true;
        });
    });
})();

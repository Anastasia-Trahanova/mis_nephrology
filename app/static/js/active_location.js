(function () {
    function rememberLocation(locationId) {
        if (!locationId) return;
        const body = new URLSearchParams();
        body.set('location_id', String(locationId));
        fetch('/api/active-location', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'},
            body: body.toString()
        }).catch(function () {
            // Приём всё равно сохранит выбранный location_id штатным POST формы.
            // Ошибка preference-cookie не должна мешать работе врача.
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        const locationSelect = document.getElementById('locationSelect');
        if (!locationSelect) return;
        locationSelect.addEventListener('change', function () {
            rememberLocation(locationSelect.value);
        });
    });
})();

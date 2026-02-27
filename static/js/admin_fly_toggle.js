document.addEventListener('DOMContentLoaded', function() {
    const flyCheckbox = document.querySelector('#id_can_fly');
    
    // Wir suchen die IDs deiner drei Flug-Felder
    const flyFieldIds = ['#id_base_fly_speed', '#id_march_fly_speed', '#id_sprint_fly_speed'];

    function toggleFlyFields() {
        const isChecked = flyCheckbox.checked;
        
        flyFieldIds.forEach(id => {
            const field = document.querySelector(id);
            if (field) {
                // Wir suchen die übergeordnete Zeile (.form-row)
                const row = field.closest('.form-row');
                if (row) {
                    row.style.display = isChecked ? '' : 'none';
                }
            }
        });
    }

    if (flyCheckbox) {
        flyCheckbox.addEventListener('change', toggleFlyFields);
        // Einmal beim Laden ausführen
        toggleFlyFields();
    }
});
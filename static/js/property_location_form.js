(function () {
    'use strict';

    function initialize(form) {
        const fields = Object.fromEntries(Array.from(form.querySelectorAll('[data-location-field]')).map((field) => [field.dataset.locationField, field]));
        const previous = Object.fromEntries(Object.entries(fields).map(([name, field]) => [name, field.value]));
        const children = {
            region_location: ['district_location', 'locality', 'complex', 'building'],
            district_location: ['locality', 'complex', 'building'],
            locality: ['complex', 'building'], developer: ['complex', 'building'], complex: ['building'],
        };
        const status = form.querySelector('[data-property-location-status]');
        let revision = 0;

        function refresh() {
            Object.entries(fields).forEach(([name, field]) => {
                const parent = field.dataset.requiredParent;
                if (parent) field.disabled = !document.getElementById(parent).value;
                previous[name] = field.value;
                window.searchableSelect?.refresh(field);
            });
        }

        async function selectedOption(field, identifier) {
            const endpoint = new URL(field.dataset.remoteOptions, window.location.origin);
            endpoint.searchParams.set('selectedIds', identifier);
            const response = await fetch(endpoint, {credentials: 'same-origin'});
            if (!response.ok) throw new Error('Не удалось загрузить территорию корпуса.');
            const data = await response.json();
            const option = data.selected.find((row) => String(row.id) === String(identifier));
            if (!option) throw new Error('Выбранная запись недоступна.');
            return option;
        }

        Object.entries(fields).forEach(([name, field]) => field.addEventListener('change', async () => {
            if (previous[name] === field.value) return;
            const currentRevision = ++revision;
            status.textContent = '';
            (children[name] || []).forEach((child) => {
                fields[child].replaceChildren(new Option('Не выбрано', ''));
            });
            refresh();
            if (name !== 'building' || !field.value) return;
            const identifier = field.value;
            status.textContent = 'Определяем территорию корпуса…';
            try {
                const context = JSON.parse(field.selectedOptions[0].dataset.catalogContext || 'null') || await selectedOption(field, identifier);
                const assignments = {
                    region_location: context.regionLocationId, district_location: context.districtLocationId,
                    locality: context.localityId, developer: context.developerId, complex: context.realEstateComplexId,
                };
                const options = await Promise.all(Object.entries(assignments).map(async ([target, value]) => {
                    if (!value || Array.from(fields[target].options).some((option) => option.value === String(value))) return null;
                    return [target, await selectedOption(fields[target], value)];
                }));
                if (revision !== currentRevision || field.value !== identifier) return;
                options.filter(Boolean).forEach(([target, option]) => fields[target].add(new Option(option.label, option.id)));
                Object.entries(assignments).forEach(([target, value]) => { fields[target].value = value || ''; });
                refresh();
                status.textContent = 'Локация квартиры соответствует выбранному корпусу.';
                form.dispatchEvent(new CustomEvent('property-location:resolved', {detail: context}));
            } catch (error) {
                if (revision === currentRevision) status.textContent = error.message;
            }
        }));
        refresh();
    }

    document.querySelectorAll('[data-property-location-form]').forEach(initialize);
})();

(function () {
    'use strict';
    const region = document.getElementById('id_desired_region_location');
    const district = document.getElementById('id_desired_district_location');
    const locality = document.getElementById('id_desired_locality');
    if (!region || !district || !locality) return;
    const previous = new Map([[region, region.value], [district, district.value]]);
    for (const [parent, children] of [[region, [district, locality]], [district, [locality]]]) {
        parent.addEventListener('change', () => {
            if (parent.value === previous.get(parent)) return;
            previous.set(parent, parent.value);
            for (const child of children) {
                child.replaceChildren(new Option('Не указано', ''));
                if (previous.has(child)) previous.set(child, '');
                window.searchableSelect?.refresh(child);
            }
        });
    }
})();

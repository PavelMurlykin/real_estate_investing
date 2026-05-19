(function () {
    'use strict';

    function onReady(callback) {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', callback);
            return;
        }

        callback();
    }

    function sameId(left, right) {
        return String(left || '') === String(right || '');
    }

    function refreshSearchableSelect(select) {
        if (window.searchableSelect) {
            window.searchableSelect.refresh(select);
        }
    }

    function readJson(selector) {
        const element = document.querySelector(selector);
        if (!element) {
            return {};
        }

        try {
            return JSON.parse(element.textContent);
        } catch (error) {
            return {};
        }
    }

    function getFieldNameFromDatasetKey(prefix, key) {
        return key.slice(prefix.length).replace(/^./, function (letter) {
            return letter.toLowerCase();
        });
    }

    function getRelationMap(select, prefix) {
        const relations = {};

        Object.keys(select.dataset).forEach(function (key) {
            if (!key.startsWith(prefix)) {
                return;
            }

            relations[getFieldNameFromDatasetKey(prefix, key)] = select.dataset[key];
        });

        return relations;
    }

    function getParentFields(select) {
        return Object.keys(getRelationMap(select, 'cascadeParent'));
    }

    function getRequiredParents(select) {
        return (select.dataset.cascadeRequiredParents || '')
            .split(',')
            .map(function (fieldName) {
                return fieldName.trim();
            })
            .filter(Boolean);
    }

    function getSelectItem(select, itemByValue) {
        const items = itemByValue[select.dataset.cascadeField] || new Map();
        return items.get(String(select.value || '')) || null;
    }

    function buildOption(item, valueKey, labelKey) {
        const option = document.createElement('option');
        option.value = item[valueKey];
        option.textContent = item[labelKey];
        return option;
    }

    function setOptions(select, items, selectedValue) {
        const valueKey = select.dataset.cascadeValueKey || 'id';
        const labelKey = select.dataset.cascadeLabelKey || 'name';
        const emptyLabel = select.dataset.cascadeEmptyLabel || '';

        select.innerHTML = '';

        const emptyOption = document.createElement('option');
        emptyOption.value = '';
        emptyOption.textContent = emptyLabel;
        select.appendChild(emptyOption);

        items.forEach(function (item) {
            select.appendChild(buildOption(item, valueKey, labelKey));
        });

        select.value = selectedValue || '';
        if (selectedValue && !sameId(select.value, selectedValue)) {
            select.value = '';
        }

        refreshSearchableSelect(select);
    }

    function getFilteredItems(select, data, selectsByField) {
        const dataKey = select.dataset.cascadeDataKey;
        const parentMap = getRelationMap(select, 'cascadeParent');
        const requiredParents = getRequiredParents(select);

        if (!dataKey || !Array.isArray(data[dataKey])) {
            return [];
        }

        return data[dataKey].filter(function (item) {
            return Object.keys(parentMap).every(function (parentField) {
                const parentSelect = selectsByField[parentField];
                const parentValue = parentSelect ? parentSelect.value : '';

                if (!parentValue) {
                    return !requiredParents.includes(parentField);
                }

                return sameId(item[parentMap[parentField]], parentValue);
            });
        });
    }

    function refreshDataSelects(selects, data, selectsByField) {
        selects.forEach(function (select) {
            if (!select.dataset.cascadeDataKey) {
                refreshSearchableSelect(select);
                return;
            }

            setOptions(
                select,
                getFilteredItems(select, data, selectsByField),
                select.value
            );
        });
    }

    function applyAutofill(select, itemByValue, selectsByField) {
        const selectedItem = getSelectItem(select, itemByValue);
        const autofillMap = getRelationMap(select, 'cascadeAutofill');

        if (!selectedItem) {
            return;
        }

        Object.keys(autofillMap).forEach(function (fieldName) {
            const targetSelect = selectsByField[fieldName];
            if (!targetSelect) {
                return;
            }

            targetSelect.value = selectedItem[autofillMap[fieldName]] || '';
            refreshSearchableSelect(targetSelect);
        });
    }

    function clearDependentValues(changedField, selects, clearedFields) {
        selects.forEach(function (select) {
            const fieldName = select.dataset.cascadeField;
            if (
                !fieldName
                || clearedFields.has(fieldName)
                || !getParentFields(select).includes(changedField)
            ) {
                return;
            }

            select.value = '';
            clearedFields.add(fieldName);
            clearDependentValues(fieldName, selects, clearedFields);
        });
    }

    function buildItemByValue(selects, data) {
        const itemByValue = {};

        selects.forEach(function (select) {
            const fieldName = select.dataset.cascadeField;
            const dataKey = select.dataset.cascadeDataKey;
            const valueKey = select.dataset.cascadeValueKey || 'id';

            if (!fieldName || !dataKey || !Array.isArray(data[dataKey])) {
                return;
            }

            itemByValue[fieldName] = new Map(
                data[dataKey].map(function (item) {
                    return [String(item[valueKey]), item];
                })
            );
        });

        return itemByValue;
    }

    function initCascade(container) {
        const data = readJson(container.dataset.cascadeData);
        const selects = Array.from(
            container.querySelectorAll('[data-cascade-field]')
        );
        const selectsByField = {};

        selects.forEach(function (select) {
            selectsByField[select.dataset.cascadeField] = select;
        });

        const itemByValue = buildItemByValue(selects, data);

        function sync(changedSelect) {
            if (changedSelect) {
                if (!changedSelect.value) {
                    clearDependentValues(
                        changedSelect.dataset.cascadeField,
                        selects,
                        new Set()
                    );
                }
                applyAutofill(changedSelect, itemByValue, selectsByField);
            }

            refreshDataSelects(selects, data, selectsByField);
        }

        selects.forEach(function (select) {
            select.addEventListener('change', function () {
                sync(select);
            });
        });

        sync(null);
    }

    onReady(function () {
        document.querySelectorAll('[data-cascade-selects]').forEach(initCascade);
    });
})();

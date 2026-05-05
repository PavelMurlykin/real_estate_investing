(function () {
    'use strict';

    function onReady(callback) {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', callback);
            return;
        }

        callback();
    }

    function getElement(selector) {
        if (!selector) {
            return null;
        }

        return document.querySelector(selector);
    }

    function readJson(selector) {
        const element = getElement(selector);
        if (!element) {
            return null;
        }

        try {
            return JSON.parse(element.textContent);
        } catch (error) {
            return null;
        }
    }

    function initSelectSwatches() {
        document.querySelectorAll('[data-select-swatch]').forEach(function (swatch) {
            const select = getElement(swatch.dataset.selectSwatchSelect);
            const options = readJson(swatch.dataset.selectSwatchData);
            const valueKey = swatch.dataset.selectSwatchValueKey || 'id';
            const colorKey = swatch.dataset.selectSwatchColorKey || 'color';

            if (!select || !Array.isArray(options)) {
                return;
            }

            const colors = new Map(
                options.map(function (item) {
                    return [String(item[valueKey]), item[colorKey]];
                })
            );

            function syncSwatch() {
                swatch.style.backgroundColor = (
                    colors.get(String(select.value)) || 'transparent'
                );
            }

            select.addEventListener('change', syncSwatch);
            syncSwatch();
        });
    }

    function syncDependentSelect(select) {
        const source = getElement(select.dataset.dependentSource);
        const optionAttribute = select.dataset.dependentOptionAttribute;

        if (!source || !optionAttribute) {
            return;
        }

        const sourceValue = source.value;
        Array.from(select.options).forEach(function (option) {
            const optionValue = option.getAttribute(
                'data-' + optionAttribute
            ) || '';
            const isVisible = !option.value || !sourceValue || optionValue === sourceValue;

            option.hidden = !isVisible;
            option.disabled = !isVisible;
        });

        const selectedOption = select.selectedOptions[0];
        if (selectedOption && selectedOption.disabled) {
            select.value = '';
        }
        if (window.searchableSelect) {
            window.searchableSelect.refresh(select);
        }
    }

    function syncDependentSelects(form) {
        form.querySelectorAll('[data-dependent-source]').forEach(syncDependentSelect);
    }

    function replaceResults(html, targetSelector) {
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        const nextResults = doc.querySelector(targetSelector);
        const currentResults = document.querySelector(targetSelector);

        if (nextResults && currentResults) {
            currentResults.innerHTML = nextResults.innerHTML;
            currentResults.dispatchEvent(
                new CustomEvent('catalog:results-replaced', { bubbles: true })
            );
        }
    }

    function fetchFilteredResults(form) {
        syncDependentSelects(form);

        const targetSelector = form.dataset.catalogResultsTarget || '#catalog-results';
        const params = new URLSearchParams(new FormData(form));
        const url = new URL(window.location.href);
        url.search = params.toString();

        fetch(url.toString(), {
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
            },
        })
            .then(function (response) {
                return response.text();
            })
            .then(function (html) {
                replaceResults(html, targetSelector);
                window.history.replaceState({}, '', url.toString());
            });
    }

    function initCatalogFilterForms() {
        document.querySelectorAll('[data-catalog-filter-form]').forEach(function (form) {
            const controls = form.querySelectorAll('[data-catalog-filter-control]');
            let debounceTimer = null;

            controls.forEach(function (control) {
                const eventName = control.dataset.catalogFilterEvent
                    || (control.tagName === 'SELECT' ? 'change' : 'input');
                const debounceDelay = Number(
                    control.dataset.catalogFilterDebounce || 400
                );

                control.addEventListener(eventName, function () {
                    if (eventName === 'input') {
                        clearTimeout(debounceTimer);
                        debounceTimer = setTimeout(function () {
                            fetchFilteredResults(form);
                        }, debounceDelay);
                        return;
                    }

                    fetchFilteredResults(form);
                });
            });

            syncDependentSelects(form);
        });
    }

    onReady(function () {
        initSelectSwatches();
        initCatalogFilterForms();
    });
})();

(function () {
    const autoSelectSelector = [
        'select[data-searchable-select]',
        'select.form-control',
        'select.form-select',
    ].join(', ');
    const instances = new WeakMap();
    const noResultsText = '\u041d\u0438\u0447\u0435\u0433\u043e \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u043e';
    const requiredText = '\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0437\u043d\u0430\u0447\u0435\u043d\u0438\u0435.';
    let nextId = 1;
    let openState = null;

    function normalize(value) {
        return String(value || '').trim().toLowerCase();
    }

    function getOptionText(option) {
        return String(option.textContent || '').trim();
    }

    function getSelectedOption(select) {
        return select.selectedOptions && select.selectedOptions.length
            ? select.selectedOptions[0]
            : null;
    }

    function getInputValue(select) {
        const selectedOption = getSelectedOption(select);
        if (!selectedOption || !selectedOption.value) {
            return '';
        }
        return getOptionText(selectedOption);
    }

    function getPlaceholder(select) {
        if (select.dataset.searchableSelectPlaceholder) {
            return select.dataset.searchableSelectPlaceholder;
        }

        const emptyOption = Array.from(select.options).find(function (option) {
            return option.value === '';
        });

        return emptyOption ? getOptionText(emptyOption) : '';
    }

    function getOptions(select) {
        return Array.from(select.options).filter(function (option) {
            return !option.disabled;
        });
    }

    function shouldEnhanceSelect(select) {
        if (
            select.dataset.searchableSelectExclude !== undefined
            || select.dataset.themeSelector !== undefined
            || select.multiple
            || Number(select.getAttribute('size') || 1) > 1
            || select.classList.contains('searchable-select-source')
        ) {
            return false;
        }

        return select.matches(autoSelectSelector);
    }

    function getInputClassName(select) {
        const classes = ['form-control', 'searchable-select-input'];

        if (
            select.classList.contains('form-control-sm')
            || select.classList.contains('form-select-sm')
        ) {
            classes.push('form-control-sm');
        }
        if (
            select.classList.contains('form-control-lg')
            || select.classList.contains('form-select-lg')
        ) {
            classes.push('form-control-lg');
        }
        if (select.classList.contains('is-invalid')) {
            classes.push('is-invalid');
        }
        if (select.classList.contains('is-valid')) {
            classes.push('is-valid');
        }

        return classes.join(' ');
    }

    function moveLabelsToInput(select, input) {
        if (!select.id || !input.id) {
            return;
        }

        document.querySelectorAll('label[for]').forEach(function (label) {
            if (label.htmlFor === select.id) {
                label.htmlFor = input.id;
            }
        });
    }

    function positionMenu(state) {
        const rect = state.wrapper.getBoundingClientRect();
        state.menu.style.left = `${rect.left}px`;
        state.menu.style.top = `${rect.bottom + 4}px`;
        state.menu.style.width = `${rect.width}px`;
    }

    function closeMenu(state) {
        state.menu.classList.add('d-none');
        state.input.setAttribute('aria-expanded', 'false');
        state.activeIndex = -1;
        if (openState === state) {
            openState = null;
        }
    }

    function setActiveOption(state, index) {
        const options = Array.from(
            state.menu.querySelectorAll('[data-searchable-select-option]')
        );
        state.activeIndex = options.length ? index : -1;

        options.forEach(function (option, optionIndex) {
            const isActive = optionIndex === state.activeIndex;
            option.classList.toggle('is-active', isActive);
            option.setAttribute('aria-selected', isActive ? 'true' : 'false');
            if (isActive) {
                option.scrollIntoView({block: 'nearest'});
            }
        });
    }

    function chooseOption(state, option) {
        const previousValue = state.select.value;
        state.select.value = option.value;
        state.input.value = option.value ? getOptionText(option) : '';
        closeMenu(state);

        if (state.select.value !== previousValue) {
            state.select.dispatchEvent(new Event('change', {bubbles: true}));
        }
    }

    function renderOptions(state) {
        const query = normalize(state.input.value);
        const selectedValue = state.select.value;
        const options = getOptions(state.select).filter(function (option) {
            if (!query) {
                return true;
            }
            if (!option.value) {
                return false;
            }
            return normalize(getOptionText(option)).includes(query);
        });

        state.menu.innerHTML = '';
        state.matches = options;

        if (!options.length) {
            const empty = document.createElement('div');
            empty.className = 'searchable-select-empty';
            empty.textContent = state.select.dataset.searchableSelectEmptyText || noResultsText;
            state.menu.appendChild(empty);
            setActiveOption(state, -1);
            return;
        }

        options.forEach(function (option, index) {
            const item = document.createElement('div');
            item.className = 'searchable-select-option';
            item.dataset.searchableSelectOption = String(index);
            item.setAttribute('role', 'option');
            item.setAttribute('aria-selected', 'false');
            item.textContent = getOptionText(option);
            item.classList.toggle('is-selected', option.value === selectedValue);
            item.addEventListener('mousedown', function (event) {
                event.preventDefault();
                chooseOption(state, option);
            });
            state.menu.appendChild(item);
        });

        const selectedIndex = options.findIndex(function (option) {
            return option.value === selectedValue;
        });
        setActiveOption(state, selectedIndex >= 0 ? selectedIndex : 0);
    }

    function openMenu(state) {
        if (openState && openState !== state) {
            closeMenu(openState);
        }

        openState = state;
        renderOptions(state);
        positionMenu(state);
        state.menu.classList.remove('d-none');
        state.input.setAttribute('aria-expanded', 'true');
    }

    function syncInputFromSelect(state) {
        state.input.placeholder = getPlaceholder(state.select);
        state.input.value = getInputValue(state.select);
        syncValidity(state);
        if (!state.menu.classList.contains('d-none')) {
            renderOptions(state);
            positionMenu(state);
        }
    }

    function syncValidity(state) {
        if (state.isRequired && !state.select.value) {
            state.input.setCustomValidity(
                state.select.dataset.searchableSelectRequiredText
                || requiredText
            );
            return;
        }

        state.input.setCustomValidity('');
    }

    function handleInput(state) {
        const selectedText = getInputValue(state.select);
        if (
            state.select.value
            && normalize(state.input.value) !== normalize(selectedText)
        ) {
            state.select.value = '';
            state.select.dispatchEvent(new Event('change', {bubbles: true}));
        }
        openMenu(state);
    }

    function handleKeydown(state, event) {
        const options = Array.from(
            state.menu.querySelectorAll('[data-searchable-select-option]')
        );

        if (event.key === 'ArrowDown') {
            event.preventDefault();
            if (state.menu.classList.contains('d-none')) {
                openMenu(state);
                return;
            }
            setActiveOption(
                state,
                Math.min(state.activeIndex + 1, options.length - 1)
            );
            return;
        }

        if (event.key === 'ArrowUp') {
            event.preventDefault();
            if (state.menu.classList.contains('d-none')) {
                openMenu(state);
                return;
            }
            setActiveOption(state, Math.max(state.activeIndex - 1, 0));
            return;
        }

        if (event.key === 'Enter' && !state.menu.classList.contains('d-none')) {
            const option = state.matches[state.activeIndex];
            if (option) {
                event.preventDefault();
                chooseOption(state, option);
            }
            return;
        }

        if (event.key === 'Escape') {
            closeMenu(state);
            syncInputFromSelect(state);
        }
    }

    function initSearchableSelect(select) {
        if (!shouldEnhanceSelect(select)) {
            return;
        }

        if (instances.has(select)) {
            refreshSearchableSelect(select);
            return;
        }

        const wrapper = document.createElement('div');
        wrapper.className = 'searchable-select';
        if (select.style.width) {
            wrapper.style.width = select.style.width;
        }
        select.parentNode.insertBefore(wrapper, select);
        wrapper.appendChild(select);

        const input = document.createElement('input');
        input.type = 'text';
        input.className = getInputClassName(select);
        input.autocomplete = 'off';
        input.setAttribute('role', 'combobox');
        input.setAttribute('aria-autocomplete', 'list');
        input.setAttribute('aria-expanded', 'false');
        input.disabled = select.disabled;

        if (select.id) {
            input.id = `${select.id}_search`;
        }
        input.required = select.required;
        moveLabelsToInput(select, input);

        const menu = document.createElement('div');
        menu.className = 'searchable-select-menu d-none';
        menu.id = `searchable-select-menu-${nextId}`;
        menu.setAttribute('role', 'listbox');
        nextId += 1;

        input.setAttribute('aria-controls', menu.id);
        wrapper.appendChild(input);
        document.body.appendChild(menu);

        select.classList.add('searchable-select-source');
        select.tabIndex = -1;
        select.required = false;

        const state = {
            activeIndex: -1,
            input: input,
            isRequired: input.required,
            matches: [],
            menu: menu,
            observer: null,
            select: select,
            wrapper: wrapper,
        };
        instances.set(select, state);

        state.observer = new MutationObserver(function () {
            syncInputFromSelect(state);
        });
        state.observer.observe(select, {
            attributes: true,
            childList: true,
            subtree: true,
        });

        input.addEventListener('focus', function () {
            openMenu(state);
        });
        input.addEventListener('click', function () {
            openMenu(state);
        });
        input.addEventListener('input', function () {
            handleInput(state);
        });
        input.addEventListener('keydown', function (event) {
            handleKeydown(state, event);
        });
        select.addEventListener('change', function () {
            syncInputFromSelect(state);
        });

        syncInputFromSelect(state);
    }

    function refreshSearchableSelect(select) {
        const state = instances.get(select);
        if (!state) {
            initSearchableSelect(select);
            return;
        }
        state.input.disabled = select.disabled;
        state.input.className = getInputClassName(select);
        state.input.required = state.isRequired;
        syncInputFromSelect(state);
    }

    function initAll(root) {
        const scope = root || document;
        scope.querySelectorAll(autoSelectSelector).forEach(initSearchableSelect);
    }

    document.addEventListener('mousedown', function (event) {
        if (
            openState
            && !openState.wrapper.contains(event.target)
            && !openState.menu.contains(event.target)
        ) {
            const state = openState;
            closeMenu(state);
            syncInputFromSelect(state);
        }
    });

    window.addEventListener('resize', function () {
        if (openState) {
            positionMenu(openState);
        }
    });

    window.addEventListener('scroll', function () {
        if (openState) {
            positionMenu(openState);
        }
    }, true);

    document.addEventListener('DOMContentLoaded', function () {
        initAll(document);
    });

    window.searchableSelect = {
        init: initSearchableSelect,
        initAll: initAll,
        refresh: refreshSearchableSelect,
    };
})();

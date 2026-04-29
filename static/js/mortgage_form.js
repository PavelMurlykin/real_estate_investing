(function () {
    'use strict';

    const scriptElement = document.currentScript;
    const propertyCostApiTemplate = scriptElement
        ? scriptElement.dataset.propertyCostApiTemplate || ''
        : '';

    function onReady(callback) {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', callback);
            return;
        }

        callback();
    }

    function parseNumber(value) {
        if (value === null || value === undefined) {
            return 0;
        }

        const normalized = String(value).replace(/\s/g, '').replace(',', '.');
        const parsed = parseFloat(normalized);
        return Number.isFinite(parsed) ? parsed : 0;
    }

    function formatMoney(value) {
        return value.toLocaleString('ru-RU', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    function getSelectedDiscountType() {
        const checked = document.querySelector(
            'input[name="DISCOUNT_MARKUP_TYPE"]:checked'
        );
        return checked ? checked.value : 'discount';
    }

    function getDiscountMarkupSourceInput() {
        return document.getElementById('discount_markup_source');
    }

    function getDiscountMarkupSource() {
        const input = getDiscountMarkupSourceInput();
        return input && input.value === 'rubles' ? 'rubles' : 'percent';
    }

    function updateLockButtons(group, source) {
        document
            .querySelectorAll(`[data-lock-group="${group}"]`)
            .forEach(function (button) {
                const locked = button.dataset.lockSource === source;
                const label = button.dataset.lockLabel || '';

                button.classList.toggle('is-locked', locked);
                button.setAttribute('aria-pressed', locked ? 'true' : 'false');
                button.title = locked
                    ? `Значение зафиксировано в ${label}`
                    : `Зафиксировать значение в ${label}`;
            });
    }

    function setDiscountMarkupSource(source) {
        const input = getDiscountMarkupSourceInput();
        if (input) {
            input.value = source === 'rubles' ? 'rubles' : 'percent';
        }
        updateLockButtons('discount_markup', getDiscountMarkupSource());
    }

    function getInitialPaymentSourceInput() {
        return document.getElementById('initial_payment_source');
    }

    function getInitialPaymentSource() {
        const input = getInitialPaymentSourceInput();
        return input && input.value === 'rubles' ? 'rubles' : 'percent';
    }

    function setInitialPaymentSource(source) {
        const input = getInitialPaymentSourceInput();
        if (input) {
            input.value = source === 'rubles' ? 'rubles' : 'percent';
        }
        updateLockButtons('initial_payment', getInitialPaymentSource());
    }

    function getPropertyCostNumber() {
        const propertyCostInput = document.getElementById('property_cost_input');
        return parseNumber(propertyCostInput ? propertyCostInput.value : 0);
    }

    function getDiscountMarkupPercentInput() {
        return document.getElementById('discount_markup_percent');
    }

    function getDiscountMarkupRublesInput() {
        return document.getElementById('discount_markup_rubles');
    }

    function updateDiscountMarkupLabels() {
        const percentLabel = document.getElementById(
            'discount_markup_percent_label'
        );
        const rublesLabel = document.getElementById(
            'discount_markup_rubles_label'
        );
        const prefix = getSelectedDiscountType() === 'discount'
            ? 'Скидка'
            : 'Удорожание';

        if (percentLabel) {
            percentLabel.textContent = `${prefix}, %`;
        }

        if (rublesLabel) {
            rublesLabel.textContent = `${prefix}, руб.`;
        }
    }

    function syncDiscountMarkupValues() {
        const propertyCost = getPropertyCostNumber();
        const percentInput = getDiscountMarkupPercentInput();
        const rublesInput = getDiscountMarkupRublesInput();

        if (!percentInput || !rublesInput) {
            return;
        }

        if (getDiscountMarkupSource() === 'rubles') {
            const rubles = parseNumber(rublesInput.value);
            percentInput.value = propertyCost > 0
                ? (rubles / propertyCost * 100).toFixed(2)
                : '0.00';
            return;
        }

        const percent = parseNumber(percentInput.value);
        rublesInput.value = (propertyCost * percent / 100).toFixed(2);
    }

    function getDiscountMarkupRublesNumber() {
        const propertyCost = getPropertyCostNumber();
        const percentInput = getDiscountMarkupPercentInput();
        const rublesInput = getDiscountMarkupRublesInput();

        if (getDiscountMarkupSource() === 'rubles') {
            return parseNumber(rublesInput ? rublesInput.value : 0);
        }

        return (
            propertyCost
            * parseNumber(percentInput ? percentInput.value : 0)
            / 100
        );
    }

    function getFinalPropertyCostNumber() {
        const propertyCost = getPropertyCostNumber();
        const discountMarkupRubles = getDiscountMarkupRublesNumber();
        const discountType = getSelectedDiscountType();

        if (discountType === 'discount') {
            return propertyCost - discountMarkupRubles;
        }

        return propertyCost + discountMarkupRubles;
    }

    function updateInitialPaymentPercent() {
        const percentInput = document.getElementById('initial_payment_percent');
        const rublesInput = document.getElementById('initial_payment_rubles');

        if (!percentInput || !rublesInput) {
            return;
        }

        const rubles = parseNumber(rublesInput.value);
        const finalCost = getFinalPropertyCostNumber();

        if (finalCost <= 0) {
            percentInput.value = '0.00';
            return;
        }

        percentInput.value = (rubles / finalCost * 100).toFixed(2);
    }

    function updateInitialPaymentRubles() {
        const percentInput = document.getElementById('initial_payment_percent');
        const rublesInput = document.getElementById('initial_payment_rubles');

        if (!percentInput || !rublesInput) {
            return;
        }

        const percent = parseNumber(percentInput.value);
        const finalCost = getFinalPropertyCostNumber();
        rublesInput.value = (finalCost * percent / 100).toFixed(2);
    }

    function syncInitialPaymentValues() {
        if (getInitialPaymentSource() === 'rubles') {
            updateInitialPaymentPercent();
            return;
        }

        updateInitialPaymentRubles();
    }

    function updateFinalPropertyCost() {
        const finalField = document.getElementById('final_property_cost_display');
        if (!finalField) {
            return;
        }

        const finalCost = getFinalPropertyCostNumber();
        finalField.value = formatMoney(finalCost);
        syncInitialPaymentValues();
    }

    function handlePropertyCostChange() {
        syncDiscountMarkupValues();
        updateFinalPropertyCost();
    }

    function handleDiscountMarkupPercentInput() {
        setDiscountMarkupSource('percent');
        syncDiscountMarkupValues();
        updateFinalPropertyCost();
    }

    function handleDiscountMarkupRublesInput() {
        setDiscountMarkupSource('rubles');
        syncDiscountMarkupValues();
        updateFinalPropertyCost();
    }

    function setDiscountMarkupLock(source) {
        setDiscountMarkupSource(source);
        syncDiscountMarkupValues();
        updateFinalPropertyCost();
    }

    function handleDiscountMarkupTypeChange() {
        updateDiscountMarkupLabels();
        updateFinalPropertyCost();
    }

    function handleInitialPaymentPercentInput() {
        setInitialPaymentSource('percent');
        updateInitialPaymentRubles();
    }

    function handleInitialPaymentRublesInput() {
        setInitialPaymentSource('rubles');
        updateInitialPaymentPercent();
    }

    function setInitialPaymentLock(source) {
        setInitialPaymentSource(source);
        syncInitialPaymentValues();
    }

    function syncTermFromYears(yearsInputId, monthsInputId) {
        const yearsInput = document.getElementById(yearsInputId);
        const monthsInput = document.getElementById(monthsInputId);

        if (!yearsInput || !monthsInput) {
            return;
        }

        const years = Math.max(0, Math.floor(parseNumber(yearsInput.value)));
        monthsInput.value = years * 12;
    }

    function syncTermFromMonths(yearsInputId, monthsInputId) {
        const yearsInput = document.getElementById(yearsInputId);
        const monthsInput = document.getElementById(monthsInputId);

        if (!yearsInput || !monthsInput) {
            return;
        }

        const months = Math.max(0, Math.floor(parseNumber(monthsInput.value)));
        yearsInput.value = Math.floor(months / 12);
    }

    function toggleGracePeriod() {
        const container = document.getElementById('grace-period-fields');
        const checked = document.querySelector(
            'input[name="HAS_GRACE_PERIOD"]:checked'
        );

        if (!container || !checked) {
            return;
        }

        const value = (checked.value || '').toLowerCase();
        container.style.display = value === 'yes' ? 'block' : 'none';
    }

    function updatePropertyCost() {
        const selector = document.getElementById('id_PROPERTY');
        const costInput = document.getElementById('property_cost_input');

        if (!selector || !costInput) {
            return;
        }

        const propertyId = selector.value;
        if (!propertyId) {
            costInput.value = '';
            handlePropertyCostChange();
            return;
        }

        const url = propertyCostApiTemplate.replace(/0\/$/, `${propertyId}/`);
        fetch(url, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
            },
        })
            .then(function (response) {
                return response.json();
            })
            .then(function (data) {
                if (!data || data.property_cost === undefined) {
                    return;
                }

                costInput.value = data.property_cost;
                handlePropertyCostChange();
            })
            .catch(function () {
                // Values remain editable if the cost lookup is unavailable.
            });
    }

    function bindInput(id, eventName, handler) {
        const element = document.getElementById(id);
        if (element) {
            element.addEventListener(eventName, handler);
        }
    }

    function bindRadioGroup(name, eventName, handler) {
        document
            .querySelectorAll(`input[name="${name}"]`)
            .forEach(function (input) {
                input.addEventListener(eventName, handler);
            });
    }

    function bindLockButton(id, handler) {
        const button = document.getElementById(id);
        if (button) {
            button.addEventListener('click', handler);
        }
    }

    function bindEvents() {
        bindInput('id_PROPERTY', 'change', updatePropertyCost);
        bindInput('property_cost_input', 'input', handlePropertyCostChange);
        bindInput(
            'discount_markup_percent',
            'input',
            handleDiscountMarkupPercentInput
        );
        bindInput(
            'discount_markup_rubles',
            'input',
            handleDiscountMarkupRublesInput
        );
        bindInput(
            'initial_payment_percent',
            'input',
            handleInitialPaymentPercentInput
        );
        bindInput(
            'initial_payment_rubles',
            'input',
            handleInitialPaymentRublesInput
        );
        bindInput('mortgage_term_years', 'input', function () {
            syncTermFromYears('mortgage_term_years', 'mortgage_term_months');
        });
        bindInput('mortgage_term_months', 'input', function () {
            syncTermFromMonths('mortgage_term_years', 'mortgage_term_months');
        });
        bindInput('grace_period_term_years', 'input', function () {
            syncTermFromYears(
                'grace_period_term_years',
                'grace_period_term_months'
            );
        });
        bindInput('grace_period_term_months', 'input', function () {
            syncTermFromMonths(
                'grace_period_term_years',
                'grace_period_term_months'
            );
        });

        bindRadioGroup(
            'DISCOUNT_MARKUP_TYPE',
            'change',
            handleDiscountMarkupTypeChange
        );
        bindRadioGroup('HAS_GRACE_PERIOD', 'change', toggleGracePeriod);
        bindLockButton('discount_markup_percent_lock', function () {
            setDiscountMarkupLock('percent');
        });
        bindLockButton('discount_markup_rubles_lock', function () {
            setDiscountMarkupLock('rubles');
        });
        bindLockButton('initial_payment_percent_lock', function () {
            setInitialPaymentLock('percent');
        });
        bindLockButton('initial_payment_rubles_lock', function () {
            setInitialPaymentLock('rubles');
        });
    }

    onReady(function () {
        bindEvents();
        syncTermFromMonths('mortgage_term_years', 'mortgage_term_months');
        syncTermFromMonths(
            'grace_period_term_years',
            'grace_period_term_months'
        );
        updateLockButtons('discount_markup', getDiscountMarkupSource());
        updateLockButtons('initial_payment', getInitialPaymentSource());
        updateDiscountMarkupLabels();
        syncDiscountMarkupValues();
        updateFinalPropertyCost();
        toggleGracePeriod();
    });
})();

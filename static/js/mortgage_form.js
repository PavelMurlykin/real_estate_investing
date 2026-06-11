(function () {
    'use strict';

    const scriptElement = document.currentScript;
    const propertyCostApiTemplate = scriptElement
        ? scriptElement.dataset.propertyCostApiTemplate || ''
        : '';
    let propertyFormData = {
        properties: [],
    };
    let mortgageProgramFormData = {
        banks: [],
        programs: [],
        key_rate: '0',
    };
    let apartmentMenuItems = [];
    let activeApartmentMenuIndex = -1;

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

    function formatPercent(value) {
        return parseNumber(value).toLocaleString('ru-RU', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    function getDefaultMarketRate() {
        return parseNumber(mortgageProgramFormData.key_rate) + 2;
    }

    function getMortgageBankSelect() {
        return document.getElementById('mortgage-bank-select');
    }

    function getMortgageProgramSelect() {
        return document.getElementById('mortgage-program-select');
    }

    function getMortgageProgramLimitOptions() {
        return document.getElementById('mortgage-program-limit-options');
    }

    function refreshSearchableSelect(select) {
        if (window.searchableSelect) {
            window.searchableSelect.refresh(select);
        }
    }

    function getSelectedMortgageProgram() {
        const programSelect = getMortgageProgramSelect();
        if (!programSelect || !programSelect.value) {
            return null;
        }

        return mortgageProgramFormData.programs.find(function (program) {
            return String(program.id) === String(programSelect.value);
        }) || null;
    }

    function getSelectedCityRegionId() {
        const citySelect = document.getElementById('city-select');
        const cityId = citySelect ? String(citySelect.value || '') : '';
        if (!cityId || !Array.isArray(propertyFormData.cities)) {
            return '';
        }

        const city = propertyFormData.cities.find(function (item) {
            return String(item.id) === cityId;
        });
        return city ? String(city.region_id || '') : '';
    }

    function getProgramCreditLimit(program) {
        if (!program || !program.is_preferential) {
            return 0;
        }

        const regionId = getSelectedCityRegionId();
        if (regionId && Array.isArray(program.regional_credit_limits)) {
            const regionalLimit = program.regional_credit_limits.find(
                function (item) {
                    return String(item.region_id) === regionId;
                }
            );
            if (regionalLimit) {
                return parseNumber(regionalLimit.credit_limit);
            }
        }

        return parseNumber(program.credit_limit);
    }

    function getProgramInitialPaymentPercent(program) {
        const value = parseNumber(
            program ? program.minimum_initial_payment_percent : 0
        );
        return value > 0 ? value : 20;
    }

    function getProgramTermYears(program) {
        const value = Math.floor(
            parseNumber(program ? program.maximum_loan_term_years : 0)
        );
        return value > 0 ? value : 30;
    }

    function getProgramAnnualRate(program) {
        const value = parseNumber(program ? program.interest_rate : 0);
        if (value > 0) {
            return value;
        }

        return program && program.is_preferential ? 6 : getDefaultMarketRate();
    }

    function getCurrentInitialPaymentRubles() {
        const rublesInput = document.getElementById('initial_payment_rubles');
        return parseNumber(rublesInput ? rublesInput.value : 0);
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

    function getLoanAmountNumber() {
        const finalCost = getFinalPropertyCostNumber();
        const rublesInput = document.getElementById('initial_payment_rubles');
        const initialPaymentRubles = parseNumber(
            rublesInput ? rublesInput.value : 0
        );
        return Math.max(0, finalCost - initialPaymentRubles);
    }

    function updateMortgageProgramLimitOptions() {
        const container = getMortgageProgramLimitOptions();
        if (!container) {
            return;
        }

        const program = getSelectedMortgageProgram();
        const creditLimit = getProgramCreditLimit(program);
        const loanAmount = getLoanAmountNumber();

        container.classList.add('d-none');
        container.innerHTML = '';
        if (
            !program
            || !program.is_preferential
            || creditLimit <= 0
            || loanAmount <= creditLimit
        ) {
            return;
        }

        const finalCost = getFinalPropertyCostNumber();
        const requiredInitialPayment = Math.max(0, finalCost - creditLimit);
        const requiredInitialPaymentPercent = finalCost > 0
            ? requiredInitialPayment / finalCost * 100
            : 0;
        const currentInitialPayment = getCurrentInitialPaymentRubles();
        const additionalInitialPayment = Math.max(
            0,
            requiredInitialPayment - currentInitialPayment
        );
        const preferentialRate = getProgramAnnualRate(program);
        const marketRate = getDefaultMarketRate();
        const marketLoanPart = loanAmount - creditLimit;
        const combinedRate = loanAmount > 0
            ? (
                creditLimit * preferentialRate
                + marketLoanPart * marketRate
            ) / loanAmount
            : 0;

        container.innerHTML = `
            <div class="alert alert-warning mb-0">
                <div class="fw-semibold mb-2">
                    Расчетная сумма кредита ${formatMoney(loanAmount)} руб. превышает лимит ${formatMoney(creditLimit)} руб.
                </div>
                <div class="row g-3">
                    <div class="col-md-6">
                        <div class="fw-semibold">Увеличение первоначального взноса</div>
                        <div>Необходимый взнос: ${formatMoney(requiredInitialPayment)} руб. (${formatPercent(requiredInitialPaymentPercent)}%).</div>
                        <div>Дополнительно к текущему взносу: ${formatMoney(additionalInitialPayment)} руб.</div>
                    </div>
                    <div class="col-md-6">
                        <div class="fw-semibold">Комбинированная ипотека</div>
                        <div>Льготная часть: ${formatMoney(creditLimit)} руб. под ${formatPercent(preferentialRate)}%.</div>
                        <div>Рыночная часть: ${formatMoney(marketLoanPart)} руб. под ${formatPercent(marketRate)}%.</div>
                        <div>Итоговая ставка: ${formatPercent(combinedRate)}%.</div>
                    </div>
                </div>
            </div>
        `;
        container.classList.remove('d-none');
    }

    function renderMortgagePrograms() {
        const bankSelect = getMortgageBankSelect();
        const programSelect = getMortgageProgramSelect();
        if (!bankSelect || !programSelect) {
            return;
        }

        const selectedBankId = String(bankSelect.value || '');
        const availablePrograms = (mortgageProgramFormData.programs || [])
            .filter(function (program) {
                return String(program.bank_id) === selectedBankId;
            });

        programSelect.innerHTML = '<option value="">Выберите программу</option>';
        availablePrograms.forEach(function (program) {
            const option = document.createElement('option');
            option.value = String(program.id);
            option.textContent = program.program_name;
            programSelect.appendChild(option);
        });
        programSelect.disabled = !selectedBankId || !availablePrograms.length;
        refreshSearchableSelect(programSelect);
        updateMortgageProgramLimitOptions();
    }

    function applyMortgageProgram() {
        const program = getSelectedMortgageProgram();
        if (!program) {
            updateMortgageProgramLimitOptions();
            return;
        }

        const initialPaymentPercentInput = document.getElementById(
            'initial_payment_percent'
        );
        const mortgageTermYearsInput = document.getElementById(
            'mortgage_term_years'
        );
        const mortgageTermMonthsInput = document.getElementById(
            'mortgage_term_months'
        );
        const annualRateInput = document.getElementById('id_ANNUAL_RATE');

        setInitialPaymentSource('percent');
        if (initialPaymentPercentInput) {
            initialPaymentPercentInput.value = (
                getProgramInitialPaymentPercent(program)
            ).toFixed(2);
        }
        updateInitialPaymentRubles();

        const termYears = getProgramTermYears(program);
        if (mortgageTermYearsInput) {
            mortgageTermYearsInput.value = termYears;
        }
        if (mortgageTermMonthsInput) {
            mortgageTermMonthsInput.value = termYears * 12;
        }

        if (annualRateInput) {
            annualRateInput.value = getProgramAnnualRate(program).toFixed(2);
            syncAnnualRateToAllTrenches(true);
        }

        updateTrenchRows();
        updateMortgageProgramLimitOptions();
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
        } else {
            updateInitialPaymentRubles();
        }
        updateTrenchRows();
    }

    function updateFinalPropertyCost() {
        const finalField = document.getElementById('final_property_cost_display');
        if (!finalField) {
            return;
        }

        const finalCost = getFinalPropertyCostNumber();
        finalField.value = formatMoney(finalCost);
        syncInitialPaymentValues();
        updateMortgageProgramLimitOptions();
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
        updateTrenchRows();
        updateMortgageProgramLimitOptions();
    }

    function handleInitialPaymentRublesInput() {
        setInitialPaymentSource('rubles');
        updateInitialPaymentPercent();
        updateTrenchRows();
        updateMortgageProgramLimitOptions();
    }

    function setInitialPaymentLock(source) {
        setInitialPaymentSource(source);
        syncInitialPaymentValues();
        updateMortgageProgramLimitOptions();
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

    function setCalculationType(type) {
        const input = document.getElementById('calculation_type');
        if (input) {
            input.value = type === 'trench' ? 'trench' : 'market';
        }
    }

    function syncCalculationTypeFromActiveTab() {
        const activeTab = document.querySelector(
            '#mortgage-calculation-tabs .nav-link.active'
        );
        setCalculationType(
            activeTab ? activeTab.dataset.calculationType : 'market'
        );
    }

    function syncFirstTrenchDateFromInitialPayment() {
        const initialPaymentDateInput = document.getElementById(
            'id_INITIAL_PAYMENT_DATE'
        );
        const firstTrenchDateInput = document.getElementById('trench_date_1');
        if (!initialPaymentDateInput || !firstTrenchDateInput) {
            return;
        }

        firstTrenchDateInput.value = initialPaymentDateInput.value || '';
    }

    function syncAnnualRateToAllTrenches(forceUpdate) {
        const baseAnnualRateInput = document.getElementById('id_ANNUAL_RATE');
        if (!baseAnnualRateInput) {
            return;
        }

        document
            .querySelectorAll('.trench-row .annual-rate')
            .forEach(function (rateInput) {
                if (forceUpdate || !rateInput.value) {
                    rateInput.value = baseAnnualRateInput.value || '';
                }
            });
    }

    function getTrenchAmountSource(row) {
        const sourceInput = row.querySelector('.trench-amount-source');
        return sourceInput && sourceInput.value === 'rubles'
            ? 'rubles'
            : 'percent';
    }

    function setTrenchAmountSource(row, source) {
        const normalizedSource = source === 'rubles' ? 'rubles' : 'percent';
        const sourceInput = row.querySelector('.trench-amount-source');
        if (sourceInput) {
            sourceInput.value = normalizedSource;
        }
        updateTrenchLockButtons(row, normalizedSource);
    }

    function updateTrenchLockButtons(row, source) {
        row.querySelectorAll('.trench-lock-button').forEach(function (button) {
            const locked = button.dataset.trenchLockSource === source;
            button.classList.toggle('is-locked', locked);
            button.setAttribute('aria-pressed', locked ? 'true' : 'false');
        });
    }

    function setTrenchLockButtonsDisabled(row, disabled) {
        row.querySelectorAll('.trench-lock-button').forEach(function (button) {
            button.disabled = disabled;
        });
    }

    function updateTrenchRows() {
        const countInput = document.getElementById('id_TRENCH_COUNT');
        const rows = Array.from(document.querySelectorAll('.trench-row'));
        if (!countInput || !rows.length) {
            return;
        }

        const trenchCount = Math.max(
            1,
            Math.min(5, parseInt(countInput.value || '1', 10) || 1)
        );
        const loanAmount = getLoanAmountNumber();
        let usedAmount = 0;

        rows.forEach(function (row, index) {
            const number = index + 1;
            const isActive = number <= trenchCount;
            const isLast = number === trenchCount;
            const dateInput = row.querySelector('.trench-date');
            const percentInput = row.querySelector('.trench-percent');
            const amountInput = row.querySelector('.trench-amount');
            const sourceInput = row.querySelector('.trench-amount-source');
            const annualRateInput = row.querySelector('.annual-rate');

            row.style.display = isActive ? 'block' : 'none';
            if (!dateInput || !percentInput || !amountInput) {
                return;
            }

            if (!isActive) {
                dateInput.required = false;
                percentInput.required = false;
                amountInput.required = false;
                if (annualRateInput) {
                    annualRateInput.required = false;
                }
                percentInput.readOnly = false;
                amountInput.readOnly = false;
                if (sourceInput) {
                    sourceInput.disabled = true;
                }
                setTrenchLockButtonsDisabled(row, true);
                return;
            }

            dateInput.required = true;
            if (annualRateInput) {
                annualRateInput.required = true;
            }
            if (sourceInput) {
                sourceInput.disabled = false;
            }

            if (isLast) {
                const lastAmount = Math.max(0, loanAmount - usedAmount);
                const lastPercent = loanAmount > 0
                    ? lastAmount / loanAmount * 100
                    : 0;
                percentInput.value = lastPercent.toFixed(2);
                amountInput.value = lastAmount.toFixed(2);
                percentInput.readOnly = true;
                amountInput.readOnly = true;
                percentInput.required = false;
                amountInput.required = false;
                setTrenchAmountSource(row, 'rubles');
                setTrenchLockButtonsDisabled(row, true);
                return;
            }

            percentInput.readOnly = false;
            amountInput.readOnly = false;
            percentInput.required = true;
            amountInput.required = true;
            setTrenchLockButtonsDisabled(row, false);

            if (getTrenchAmountSource(row) === 'rubles') {
                const amount = parseNumber(amountInput.value);
                percentInput.value = loanAmount > 0
                    ? (amount / loanAmount * 100).toFixed(2)
                    : '0.00';
                usedAmount += amount;
            } else {
                const percent = parseNumber(percentInput.value);
                const amount = loanAmount * percent / 100;
                amountInput.value = amount.toFixed(2);
                usedAmount += amount;
            }
        });
    }

    function handleTrenchPaneInput(event) {
        const row = event.target.closest('.trench-row');
        if (!row) {
            return;
        }

        if (event.target.classList.contains('trench-percent')) {
            setTrenchAmountSource(row, 'percent');
            updateTrenchRows();
            return;
        }

        if (event.target.classList.contains('trench-amount')) {
            setTrenchAmountSource(row, 'rubles');
            updateTrenchRows();
        }
    }

    function handleTrenchPaneClick(event) {
        const button = event.target.closest('.trench-lock-button');
        if (!button || button.disabled) {
            return;
        }

        const row = button.closest('.trench-row');
        if (!row) {
            return;
        }

        setTrenchAmountSource(row, button.dataset.trenchLockSource);
        updateTrenchRows();
    }

    function setFieldValue(id, value, dispatchChange) {
        const field = document.getElementById(id);
        if (!field) {
            return;
        }

        field.value = value === null || value === undefined ? '' : value;
        if (dispatchChange) {
            field.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    function getSelectedPropertyInput() {
        return document.getElementById('id_PROPERTY');
    }

    function getBuildingSelect() {
        return document.getElementById('id_building');
    }

    function getApartmentNumberInput() {
        return (
            document.getElementById('id_OBJECT_APARTMENT_NUMBER_search')
            || document.getElementById('id_OBJECT_APARTMENT_NUMBER')
        );
    }

    function getApartmentNumberSourceInput() {
        return document.getElementById('id_OBJECT_APARTMENT_NUMBER');
    }

    function getApartmentMenu() {
        return document.getElementById('property-apartment-menu');
    }

    function getSelectedBuildingId() {
        const buildingSelect = getBuildingSelect();
        return buildingSelect ? String(buildingSelect.value || '') : '';
    }

    function getPropertiesForSelectedBuilding() {
        const buildingId = getSelectedBuildingId();
        if (!buildingId || !Array.isArray(propertyFormData.properties)) {
            return [];
        }

        return propertyFormData.properties.filter(function (propertyItem) {
            return String(propertyItem.building_id || '') === buildingId;
        });
    }

    function getPropertyById(propertyId) {
        if (!propertyId || !Array.isArray(propertyFormData.properties)) {
            return null;
        }

        return propertyFormData.properties.find(function (propertyItem) {
            return String(propertyItem.id || '') === String(propertyId);
        }) || null;
    }

    function getSelectedBuildingPropertyByApartmentNumber(apartmentNumber) {
        const normalizedApartmentNumber = String(apartmentNumber || '').trim();
        if (!normalizedApartmentNumber) {
            return null;
        }

        return getPropertiesForSelectedBuilding().find(
            function (propertyItem) {
                const propertyApartmentNumber = String(
                    propertyItem.apartment_number || ''
                ).trim().toLowerCase();
                return (
                    propertyApartmentNumber
                    === normalizedApartmentNumber.toLowerCase()
                );
            }
        ) || null;
    }

    function setSelectedPropertyId(propertyId) {
        const input = getSelectedPropertyInput();
        if (input) {
            input.value = propertyId || '';
        }
    }

    function setApartmentNumberValue(value) {
        const sourceInput = getApartmentNumberSourceInput();
        const visibleInput = getApartmentNumberInput();
        const normalizedValue = value === null || value === undefined
            ? ''
            : value;

        if (sourceInput) {
            sourceInput.value = normalizedValue;
        }
        if (visibleInput && visibleInput !== sourceInput) {
            visibleInput.value = normalizedValue;
        }
    }

    function closeApartmentMenu() {
        const menu = getApartmentMenu();
        if (!menu) {
            return;
        }

        menu.classList.add('d-none');
        activeApartmentMenuIndex = -1;
    }

    function setActiveApartmentOption(index) {
        const menu = getApartmentMenu();
        if (!menu) {
            return;
        }

        const options = Array.from(
            menu.querySelectorAll('[data-apartment-option]')
        );
        activeApartmentMenuIndex = options.length ? index : -1;
        options.forEach(function (option, optionIndex) {
            option.classList.toggle(
                'is-active',
                optionIndex === activeApartmentMenuIndex
            );
        });
    }

    function getApartmentMenuMatches() {
        const input = getApartmentNumberInput();
        const query = input ? String(input.value || '').trim().toLowerCase() : '';
        const properties = getPropertiesForSelectedBuilding();

        if (!query) {
            return properties;
        }

        return properties.filter(function (propertyItem) {
            return String(propertyItem.apartment_number || '')
                .trim()
                .toLowerCase()
                .includes(query);
        });
    }

    function renderApartmentMenu() {
        const menu = getApartmentMenu();
        if (!menu) {
            return;
        }

        apartmentMenuItems = getApartmentMenuMatches();
        menu.innerHTML = '';

        if (!getSelectedBuildingId()) {
            const empty = document.createElement('div');
            empty.className = 'apartment-autocomplete-empty';
            empty.textContent = 'Сначала выберите корпус';
            menu.appendChild(empty);
            return;
        }

        if (!apartmentMenuItems.length) {
            const empty = document.createElement('div');
            empty.className = 'apartment-autocomplete-empty';
            empty.textContent = 'Квартиры не найдены';
            menu.appendChild(empty);
            return;
        }

        apartmentMenuItems.forEach(function (propertyItem, index) {
            const option = document.createElement('div');
            option.className = 'apartment-autocomplete-option';
            option.dataset.apartmentOption = String(index);
            option.setAttribute('role', 'option');
            option.textContent = propertyItem.apartment_number;
            option.addEventListener('mousedown', function (event) {
                event.preventDefault();
                applySelectedProperty(propertyItem);
                closeApartmentMenu();
            });
            menu.appendChild(option);
        });

        setActiveApartmentOption(0);
    }

    function openApartmentMenu() {
        const menu = getApartmentMenu();
        if (!menu) {
            return;
        }

        renderApartmentMenu();
        menu.classList.remove('d-none');
    }

    function syncApartmentSelection() {
        renderApartmentMenu();
        handleApartmentNumberInput();
    }

    function scheduleApartmentSelectionSync() {
        window.setTimeout(syncApartmentSelection, 0);
    }

    function clearPropertySpecificFields(clearApartmentNumber) {
        setSelectedPropertyId('');
        if (clearApartmentNumber) {
            setApartmentNumberValue('');
        }
        setFieldValue('id_OBJECT_AREA', '');
        setFieldValue('id_OBJECT_LAYOUT', '', true);
        setFieldValue('id_OBJECT_FLOOR', '');
        setFieldValue('id_OBJECT_DECORATION', '', true);
    }

    function fillPropertySpecificFields(propertyItem) {
        if (!propertyItem) {
            return;
        }

        setSelectedPropertyId(propertyItem.id);
        setApartmentNumberValue(propertyItem.apartment_number);
        setFieldValue('id_OBJECT_AREA', propertyItem.area);
        setFieldValue('id_OBJECT_LAYOUT', propertyItem.layout_id, true);
        setFieldValue('id_OBJECT_FLOOR', propertyItem.floor);
        setFieldValue(
            'id_OBJECT_DECORATION',
            propertyItem.decoration_id,
            true
        );
    }

    function applySelectedProperty(propertyItem) {
        const costInput = document.getElementById('property_cost_input');
        fillPropertySpecificFields(propertyItem);
        if (costInput && propertyItem.property_cost !== undefined) {
            costInput.value = propertyItem.property_cost;
            handlePropertyCostChange();
        }
    }

    function clearObjectDataFields() {
        closeApartmentMenu();
        setSelectedPropertyId('');
        setFieldValue('city-select', '', true);
        setFieldValue('district-select', '', true);
        setFieldValue('developer-select', '', true);
        setFieldValue('complex-select', '', true);
        setFieldValue('id_building', '', true);
        setApartmentNumberValue('');
        setFieldValue('id_OBJECT_AREA', '');
        setFieldValue('id_OBJECT_LAYOUT', '', true);
        setFieldValue('id_OBJECT_FLOOR', '');
        setFieldValue('id_OBJECT_DECORATION', '', true);
        window.setTimeout(renderApartmentMenu, 0);
    }

    function handleBuildingChange() {
        const costInput = document.getElementById('property_cost_input');
        if (costInput) {
            costInput.value = '';
        }
        window.setTimeout(function () {
            renderApartmentMenu();
            clearPropertySpecificFields(true);
            handlePropertyCostChange();
        }, 0);
    }

    function handleApartmentNumberInput() {
        const input = getApartmentNumberInput();
        if (!input) {
            return;
        }

        const sourceInput = getApartmentNumberSourceInput();
        if (sourceInput && sourceInput !== input) {
            sourceInput.value = input.value;
        }

        renderApartmentMenu();
        const propertyItem = getSelectedBuildingPropertyByApartmentNumber(
            input.value
        );
        if (!propertyItem) {
            setSelectedPropertyId('');
            return;
        }

        applySelectedProperty(propertyItem);
    }

    function handleApartmentNumberFocus() {
        openApartmentMenu();
        handleApartmentNumberInput();
    }

    function handleApartmentNumberKeydown(event) {
        const menu = getApartmentMenu();
        const isOpen = menu && !menu.classList.contains('d-none');
        if (!isOpen && ['ArrowDown', 'ArrowUp'].includes(event.key)) {
            openApartmentMenu();
            event.preventDefault();
            return;
        }

        if (!isOpen) {
            return;
        }

        if (event.key === 'ArrowDown') {
            event.preventDefault();
            setActiveApartmentOption(
                Math.min(
                    activeApartmentMenuIndex + 1,
                    apartmentMenuItems.length - 1
                )
            );
            return;
        }

        if (event.key === 'ArrowUp') {
            event.preventDefault();
            setActiveApartmentOption(
                Math.max(activeApartmentMenuIndex - 1, 0)
            );
            return;
        }

        if (event.key === 'Enter') {
            const propertyItem = apartmentMenuItems[activeApartmentMenuIndex];
            if (propertyItem) {
                event.preventDefault();
                applySelectedProperty(propertyItem);
                closeApartmentMenu();
            }
            return;
        }

        if (event.key === 'Escape') {
            closeApartmentMenu();
        }
    }

    function fillPropertyDetails(data) {
        setFieldValue('city-select', data.city_id, true);
        setFieldValue('district-select', data.district_id, true);
        setFieldValue('developer-select', data.developer_id, true);
        setFieldValue('complex-select', data.complex_id, true);
        setFieldValue('id_building', data.building_id);
        renderApartmentMenu();
        fillPropertySpecificFields(data);
    }

    function clearPropertyDetails() {
        setFieldValue('city-select', '', true);
        setFieldValue('district-select', '', true);
        setFieldValue('developer-select', '', true);
        setFieldValue('complex-select', '', true);
        setFieldValue('id_building', '', true);
        clearPropertySpecificFields(true);
    }

    function updatePropertyCost() {
        const selector = document.getElementById('id_PROPERTY');
        const costInput = document.getElementById('property_cost_input');

        if (!selector || !costInput) {
            return;
        }

        const propertyId = selector.value;
        if (!propertyId) {
            clearPropertyDetails();
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
                fillPropertyDetails(data);
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

    function bindApartmentNumberInput(eventName, handler) {
        const sourceInput = getApartmentNumberSourceInput();
        const visibleInput = getApartmentNumberInput();

        if (sourceInput) {
            sourceInput.addEventListener(eventName, handler);
        }
        if (visibleInput && visibleInput !== sourceInput) {
            visibleInput.addEventListener(eventName, handler);
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
        bindInput(
            'clear-object-data-fields',
            'click',
            clearObjectDataFields
        );
        bindInput('id_building', 'change', handleBuildingChange);
        bindInput('city-select', 'change', scheduleApartmentSelectionSync);
        bindInput('city-select', 'change', updateMortgageProgramLimitOptions);
        bindInput('district-select', 'change', scheduleApartmentSelectionSync);
        bindInput('developer-select', 'change', scheduleApartmentSelectionSync);
        bindInput('complex-select', 'change', scheduleApartmentSelectionSync);
        bindInput('mortgage-bank-select', 'change', renderMortgagePrograms);
        bindInput(
            'mortgage-program-select',
            'change',
            applyMortgageProgram
        );
        bindApartmentNumberInput('input', handleApartmentNumberInput);
        bindApartmentNumberInput('change', handleApartmentNumberInput);
        bindApartmentNumberInput('focus', handleApartmentNumberFocus);
        bindApartmentNumberInput('keydown', handleApartmentNumberKeydown);
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
        bindInput(
            'id_INITIAL_PAYMENT_DATE',
            'change',
            syncFirstTrenchDateFromInitialPayment
        );
        bindInput('id_ANNUAL_RATE', 'input', syncAnnualRateToAllTrenches);
        bindInput('id_ANNUAL_RATE', 'change', syncAnnualRateToAllTrenches);
        bindInput('id_TRENCH_COUNT', 'change', updateTrenchRows);

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

        document
            .querySelectorAll('[data-calculation-type]')
            .forEach(function (button) {
                button.addEventListener('shown.bs.tab', function () {
                    setCalculationType(button.dataset.calculationType);
                });
                button.addEventListener('click', function () {
                    setCalculationType(button.dataset.calculationType);
                });
            });
        document
            .querySelectorAll('[data-submit-calculation-type]')
            .forEach(function (button) {
                button.addEventListener('click', function () {
                    setCalculationType(button.dataset.submitCalculationType);
                });
            });

        const trenchPane = document.getElementById('trench-mortgage-pane');
        if (trenchPane) {
            trenchPane.addEventListener('input', handleTrenchPaneInput);
            trenchPane.addEventListener('click', handleTrenchPaneClick);
        }
    }

    onReady(function () {
        propertyFormData = readJson('#mortgage-property-form-data');
        mortgageProgramFormData = readJson('#mortgage-program-form-data');
        bindEvents();
        document.addEventListener('mousedown', function (event) {
            const menu = getApartmentMenu();
            const input = getApartmentNumberInput();
            if (
                menu
                && !menu.contains(event.target)
                && input
                && event.target !== input
            ) {
                closeApartmentMenu();
            }
        });
        renderApartmentMenu();
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
        syncCalculationTypeFromActiveTab();
        syncFirstTrenchDateFromInitialPayment();
        syncAnnualRateToAllTrenches();
        updateTrenchRows();
        renderMortgagePrograms();
        updateMortgageProgramLimitOptions();
        const selectedPropertyInput = getSelectedPropertyInput();
        const selectedPropertyId = selectedPropertyInput
            ? selectedPropertyInput.value
            : '';
        if (!getPropertyById(selectedPropertyId)) {
            handleApartmentNumberInput();
        }
    });
})();

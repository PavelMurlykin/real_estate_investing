(function () {
  'use strict';

  function initializeDeveloperMortgageProgramForm() {
    const form = document.querySelector(
      '[data-developer-mortgage-program-form]'
    );
    if (!form) {
      return;
    }

    const companyGroupSelect = form.querySelector('#id_company_group');
    const complexSelect = form.querySelector('#id_real_estate_complex');
    const optionsUrl = form.dataset.complexOptionsUrl;
    if (!companyGroupSelect || !complexSelect || !optionsUrl) {
      return;
    }

    let requestController = null;

    function replaceComplexOptions(complexes, selectedValue) {
      complexSelect.replaceChildren();

      const allComplexesOption = document.createElement('option');
      allComplexesOption.value = '';
      allComplexesOption.textContent = 'Все ЖК группы';
      complexSelect.appendChild(allComplexesOption);

      complexes.forEach(function (complex) {
        const option = document.createElement('option');
        option.value = String(complex.id);
        option.textContent = complex.label;
        option.selected = option.value === selectedValue;
        complexSelect.appendChild(option);
      });
    }

    async function loadComplexOptions(preserveSelection) {
      const companyGroupId = companyGroupSelect.value;
      const selectedValue = preserveSelection ? complexSelect.value : '';

      if (requestController) {
        requestController.abort();
      }
      const currentRequestController = new AbortController();
      requestController = currentRequestController;

      replaceComplexOptions([], '');
      if (!companyGroupId) {
        complexSelect.disabled = true;
        return;
      }

      complexSelect.disabled = true;
      const url = new URL(optionsUrl, window.location.origin);
      url.searchParams.set('company_group_id', companyGroupId);

      try {
        const response = await fetch(url, {
          headers: {'X-Requested-With': 'XMLHttpRequest'},
          signal: currentRequestController.signal,
        });
        if (!response.ok) {
          throw new Error('Complex options request failed');
        }

        const payload = await response.json();
        replaceComplexOptions(payload.complexes || [], selectedValue);
      } catch (error) {
        if (error.name !== 'AbortError') {
          replaceComplexOptions([], '');
        }
      } finally {
        if (
          requestController === currentRequestController
          && !currentRequestController.signal.aborted
        ) {
          complexSelect.disabled = false;
        }
      }
    }

    companyGroupSelect.addEventListener('change', function () {
      loadComplexOptions(false);
    });
    complexSelect.disabled = !companyGroupSelect.value;
  }

  if (document.readyState === 'loading') {
    document.addEventListener(
      'DOMContentLoaded',
      initializeDeveloperMortgageProgramForm
    );
  } else {
    initializeDeveloperMortgageProgramForm();
  }
})();

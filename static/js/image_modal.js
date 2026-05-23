(function () {
    function getImageTitle(trigger, image) {
        if (trigger.dataset.imageModalTitle) {
            return trigger.dataset.imageModalTitle;
        }

        if (image && image.getAttribute('alt')) {
            return image.getAttribute('alt');
        }

        return 'Image preview';
    }

    document.addEventListener('click', function (event) {
        const trigger = event.target.closest('[data-image-modal]');

        if (!trigger) {
            return;
        }

        const modalElement = document.getElementById('image-preview-modal');
        if (!modalElement || !window.bootstrap) {
            return;
        }

        const imageUrl = trigger.getAttribute('href');
        if (!imageUrl) {
            return;
        }

        event.preventDefault();

        const sourceImage = trigger.querySelector('img');
        const modalImage = modalElement.querySelector('[data-image-modal-image]');
        const modalTitle = modalElement.querySelector('[data-image-modal-title]');
        const title = getImageTitle(trigger, sourceImage);

        modalImage.setAttribute('src', imageUrl);
        modalImage.setAttribute('alt', title);
        modalTitle.textContent = title;

        window.bootstrap.Modal.getOrCreateInstance(modalElement).show();
    });

    document.addEventListener('hidden.bs.modal', function (event) {
        if (event.target.id !== 'image-preview-modal') {
            return;
        }

        const modalImage = event.target.querySelector('[data-image-modal-image]');
        modalImage.removeAttribute('src');
        modalImage.setAttribute('alt', '');
    });
}());

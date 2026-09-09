from django.views.generic import TemplateView


class ReactAppView(TemplateView):
    """Serve the React application shell for every client-side route."""

    template_name = 'react_frontend/index.html'

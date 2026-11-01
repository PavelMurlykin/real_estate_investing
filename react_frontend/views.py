import json
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.views.generic import TemplateView


@lru_cache(maxsize=8)
def _load_build_manifest(
    manifest_path, _modified_time_nanoseconds, _file_size,
):
    """Cache the build map until its filesystem signature changes."""
    return json.loads(manifest_path.read_text(encoding='utf-8'))


def get_react_assets():
    """Resolve content-hashed entry files from the Vite production manifest."""
    manifest_path = (
        Path(settings.BASE_DIR) / 'static' / 'react' / '.vite' / 'manifest.json'
    )
    try:
        metadata = manifest_path.stat()
        manifest = _load_build_manifest(
            manifest_path, metadata.st_mtime_ns, metadata.st_size,
        )
    except FileNotFoundError:
        return {
            'react_script': 'react/app.js',
            'react_stylesheets': ['react/app.css'],
        }
    entry = manifest['src/main.tsx']
    stylesheets = entry.get('css', [])
    if not stylesheets and 'style.css' in manifest:
        stylesheets = [manifest['style.css']['file']]
    return {
        'react_script': 'react/' + entry['file'],
        'react_stylesheets': ['react/' + name for name in stylesheets],
    }


class ReactAppView(TemplateView):
    """Serve the React application shell for every client-side route."""

    template_name = 'react_frontend/index.html'

    def get_context_data(self, **kwargs):
        """Make a rebuilt script or stylesheet bypass the previous browser cache."""
        context = super().get_context_data(**kwargs)
        context.update(get_react_assets())
        return context

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class ApplicationPageNumberPagination(PageNumberPagination):
    """Return stable pagination metadata for frontend list screens."""

    page_size = 20
    page_size_query_param = 'pageSize'
    max_page_size = 100

    def get_paginated_response(self, data):
        """Return results with explicit current-page metadata."""
        return Response(
            {
                'page': self.page.number,
                'pageSize': self.get_page_size(self.request),
                'totalCount': self.page.paginator.count,
                'totalPages': self.page.paginator.num_pages,
                'results': data,
            }
        )

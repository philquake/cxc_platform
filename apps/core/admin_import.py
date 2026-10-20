from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import path, reverse


class ImportAdminMixin:
    """Adds an "Import" page and changelist button to a ModelAdmin.

    Subclasses set `import_form_class`, `import_title`, `import_help` and implement
    `run_import(request, form)` returning (created_lines, error_lines).
    Optionally set `import_template_csv` (a callable returning CSV text) for a download link.
    """

    import_form_class = None
    import_title = "Import"
    import_help = ""
    import_template_csv = None
    change_list_template = "admin/import_change_list.html"

    def _import_name(self, suffix):
        return f"{self.opts.app_label}_{self.opts.model_name}_{suffix}"

    def get_urls(self):
        extra = [
            path("import/", self.admin_site.admin_view(self.import_view), name=self._import_name("import")),
            path("import/template.csv", self.admin_site.admin_view(self.import_template_view),
                 name=self._import_name("import_template")),
        ]
        return extra + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        if self.has_add_permission(request):
            extra_context["import_url"] = reverse(f"admin:{self._import_name('import')}")
            extra_context["import_label"] = self.import_title
        return super().changelist_view(request, extra_context)

    def import_template_view(self, request):
        if not self.has_add_permission(request) or not self.import_template_csv:
            return HttpResponse(status=404)
        response = HttpResponse(self.import_template_csv(), content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{self.opts.model_name}-template.csv"'
        return response

    def import_view(self, request):
        if not self.has_add_permission(request):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        created, errors = [], []
        if request.method == "POST":
            form = self.import_form_class(request.POST, request.FILES)
            if form.is_valid():
                created, errors = self.run_import(request, form)
                if created:
                    form = self.import_form_class()
        else:
            form = self.import_form_class()
        context = {
            **self.admin_site.each_context(request),
            "opts": self.opts,
            "title": self.import_title,
            "form": form,
            "created": created,
            "errors": errors,
            "import_help": self.import_help,
            "template_url": reverse(f"admin:{self._import_name('import_template')}") if self.import_template_csv else "",
            "changelist_url": reverse(f"admin:{self.opts.app_label}_{self.opts.model_name}_changelist"),
        }
        return TemplateResponse(request, "admin/import_form.html", context)
